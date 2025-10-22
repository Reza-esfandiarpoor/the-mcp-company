"""This file contains the function calling implementation for different actions.

This is similar to the functionality of `CodeActResponseParser`.
"""

import json
import shlex
import urllib
from uuid import uuid4
import re
import unicodedata
import copy

from litellm import (
    ModelResponse,
)

from openhands.agenthub.codeact_agent.tools import (
    BrowserTool,
    CondensationRequestTool,
    FinishTool,
    IPythonTool,
    LLMBasedFileEditTool,
    ThinkTool,
    create_cmd_run_tool,
    create_str_replace_editor_tool,
)
from openhands.core.exceptions import (
    FunctionCallNotExistsError,
    FunctionCallValidationError,
)
from openhands.core.logger import openhands_logger as logger
from openhands.events.action import (
    Action,
    AgentDelegateAction,
    AgentFinishAction,
    AgentThinkAction,
    BrowseInteractiveAction,
    BrowseURLAction,
    CmdRunAction,
    FileEditAction,
    FileReadAction,
    IPythonRunCellAction,
    MessageAction,
)
from openhands.events.action.agent import CondensationRequestAction
from openhands.events.action.mcp import MCPAction
from openhands.events.event import FileEditSource, FileReadSource
from openhands.events.tool import ToolCallMetadata

def make_argname_for_claude(s: str, dot_allowed: bool=True) -> str:
    # make sure the argnames adhere to this pattern: '^[a-zA-Z0-9_.-]{1,64}$'
    if dot_allowed:
        ALLOWED = re.compile(r"[^a-zA-Z0-9_.-]")
    else:
        ALLOWED = re.compile(r"[^a-zA-Z0-9_-]")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = ALLOWED.sub("", s)
    s = s[:64]
    if not s:
        s = uuid4().hex
    return s

def update_schema_argnames(orig_schema: dict):
    # returns a tuple. First is the updated schema and the second is a mapping
    # that maps the new argnames to original arg names
    schema = copy.deepcopy(orig_schema)
    name_mapping = dict()
    # first make sure arg names that comply with the requirements are not touched
    for name in schema['function']['parameters']["properties"].keys():
        processed = make_argname_for_claude(name)
        if processed != name:
            continue
        else:
            name_mapping[name] = processed

    if len(name_mapping) == len(schema['function']['parameters']["properties"]):
        # all argnames are valid
        return orig_schema, {}

    # now find a new name for the noncompliant arguments
    for name in schema['function']['parameters']["properties"].keys():
        if name in name_mapping:
            continue
        processed = make_argname_for_claude(name)
        chosen = processed
        while chosen in list(name_mapping.values()):
            chosen = processed + "_" + uuid4().hex[:4]
            chosen = chosen[-64:]
        name_mapping[name] = chosen

    new_required = [name_mapping[i] for i in schema['function']['parameters']["required"]]
    new_prop = {name_mapping[n]: v for n, v in schema['function']['parameters']["properties"].items()}

    schema['function']['parameters']["required"] = new_required
    schema['function']['parameters']["properties"] = new_prop
    reverse_mapping = {v: k for k, v in name_mapping.items()}
    return schema, reverse_mapping

def prep_tools_for_claude(tool_list):
    updated_list = list()
    tool_reverse_maps = dict()
    for tool in tool_list:
        new_spec, rv_map = update_schema_argnames(tool)
        orig_name = tool['function']['name']
        new_name = make_argname_for_claude(orig_name, dot_allowed=False)
        new_spec['function']['name'] = new_name
        updated_list.append(new_spec)
        tool_reverse_maps[new_name] = {'args': rv_map, 'orig_name': orig_name}
    return updated_list, tool_reverse_maps


def combine_thought(action: Action, thought: str) -> Action:
    if not hasattr(action, 'thought'):
        return action
    if thought and action.thought:
        action.thought = f'{thought}\n{action.thought}'
    elif thought:
        action.thought = thought
    return action


def response_to_actions(
    response: ModelResponse,
    mcp_tool_names: list[str] | None = None,
    retrieved_tool_names: list[str] | None = None,
    native_tools: list[str] | None = None,
    llm_model_name: str | None = None,
    llm_base_url: str | None = None,
    argname_mapping: dict | None = None
) -> list[Action]:
    actions: list[Action] = []
    assert len(response.choices) == 1, 'Only one choice is supported for now'
    choice = response.choices[0]
    assistant_msg = choice.message
    if hasattr(assistant_msg, 'tool_calls') and assistant_msg.tool_calls:
        # Check if there's assistant_msg.content. If so, add it to the thought
        thought = ''
        if isinstance(assistant_msg.content, str):
            thought = assistant_msg.content
        elif isinstance(assistant_msg.content, list):
            for msg in assistant_msg.content:
                if msg['type'] == 'text':
                    thought += msg['text']

        # Process each tool call to OpenHands action
        for i, tool_call in enumerate(assistant_msg.tool_calls):
            action: Action
            logger.debug(f'Tool call in function_calling.py: {tool_call}')
            try:
                arguments = json.loads(tool_call.function.arguments)
            except json.decoder.JSONDecodeError as e:
                raise FunctionCallValidationError(
                    f'Failed to parse tool call arguments: {tool_call.function.arguments}'
                ) from e

            orig_name = None
            if argname_mapping is not None and tool_call.function.name in argname_mapping:
                orig_name = argname_mapping[tool_call.function.name]['orig_name']
                curr_map = argname_mapping[tool_call.function.name]['args']
                new_args = dict()
                for n, v in arguments.items():
                    if n in curr_map:
                        new_args[curr_map[n]] = v
                    else:
                        new_args[n] = v
                arguments = new_args

            # ================================================
            # CmdRunTool (Bash)
            # ================================================

            if tool_call.function.name == create_cmd_run_tool()['function']['name']:
                if 'command' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "command" in tool call {tool_call.function.name}'
                    )
                # convert is_input to boolean
                is_input = arguments.get('is_input', 'false') == 'true'
                action = CmdRunAction(command=arguments['command'], is_input=is_input)

                # Set hard timeout if provided
                if 'timeout' in arguments:
                    try:
                        action.set_hard_timeout(min(600.0, float(arguments['timeout'])))
                    except ValueError as e:
                        raise FunctionCallValidationError(
                            f"Invalid float passed to 'timeout' argument: {arguments['timeout']}"
                        ) from e

            # ================================================
            # IPythonTool (Jupyter)
            # ================================================
            elif tool_call.function.name == IPythonTool['function']['name']:
                if 'code' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "code" in tool call {tool_call.function.name}'
                    )
                action = IPythonRunCellAction(code=arguments['code'])
            elif tool_call.function.name == 'delegate_to_browsing_agent':
                action = AgentDelegateAction(
                    agent='BrowsingAgent',
                    inputs=arguments,
                )

            # ================================================
            # AgentFinishAction
            # ================================================
            elif tool_call.function.name == FinishTool['function']['name']:
                action = AgentFinishAction(
                    final_thought=arguments.get('message', ''),
                    task_completed=arguments.get('task_completed', None),
                )

            # ================================================
            # LLMBasedFileEditTool (LLM-based file editor, deprecated)
            # ================================================
            elif tool_call.function.name == LLMBasedFileEditTool['function']['name']:
                if 'path' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "path" in tool call {tool_call.function.name}'
                    )
                if 'content' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "content" in tool call {tool_call.function.name}'
                    )
                action = FileEditAction(
                    path=arguments['path'],
                    content=arguments['content'],
                    start=arguments.get('start', 1),
                    end=arguments.get('end', -1),
                    impl_source=arguments.get(
                        'impl_source', FileEditSource.LLM_BASED_EDIT
                    ),
                )
            elif (
                tool_call.function.name
                == create_str_replace_editor_tool()['function']['name']
            ):
                if 'command' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "command" in tool call {tool_call.function.name}'
                    )
                if 'path' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "path" in tool call {tool_call.function.name}'
                    )
                path = arguments['path']
                command = arguments['command']
                other_kwargs = {
                    k: v for k, v in arguments.items() if k not in ['command', 'path']
                }

                if command == 'view':
                    action = FileReadAction(
                        path=path,
                        impl_source=FileReadSource.OH_ACI,
                        view_range=other_kwargs.get('view_range', None),
                    )
                else:
                    if 'view_range' in other_kwargs:
                        # Remove view_range from other_kwargs since it is not needed for FileEditAction
                        other_kwargs.pop('view_range')

                    # Filter out unexpected arguments
                    valid_kwargs = {}
                    # Get valid parameters from the str_replace_editor tool definition
                    str_replace_editor_tool = create_str_replace_editor_tool()
                    valid_params = set(
                        str_replace_editor_tool['function']['parameters'][
                            'properties'
                        ].keys()
                    )
                    for key, value in other_kwargs.items():
                        if key in valid_params:
                            valid_kwargs[key] = value
                        else:
                            raise FunctionCallValidationError(
                                f'Unexpected argument {key} in tool call {tool_call.function.name}. Allowed arguments are: {valid_params}'
                            )

                    action = FileEditAction(
                        path=path,
                        command=command,
                        impl_source=FileEditSource.OH_ACI,
                        **valid_kwargs,
                    )
            # ================================================
            # AgentThinkAction
            # ================================================
            elif tool_call.function.name == ThinkTool['function']['name']:
                action = AgentThinkAction(thought=arguments.get('thought', ''))

            # ================================================
            # CondensationRequestAction
            # ================================================
            elif tool_call.function.name == CondensationRequestTool['function']['name']:
                action = CondensationRequestAction()

            # ================================================
            # BrowserTool
            # ================================================
            elif tool_call.function.name == BrowserTool['function']['name']:
                if 'code' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "code" in tool call {tool_call.function.name}'
                    )
                action = BrowseInteractiveAction(browser_actions=arguments['code'])

            # ================================================
            # A hacky way to bring back "web_read" action.
            # ================================================
            elif tool_call.function.name == 'fetch':
                if 'url' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "url" in tool call {tool_call.function.name}'
                    )
                action = BrowseURLAction(url=arguments['url'])

            # ================================================
            # Owncloud upload file
            # ================================================
            elif tool_call.function.name.lower() == 'owncloud_upload_file'.lower():
                if 'local_filepath' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "local_filepath" in tool call {tool_call.function.name}'
                    )
                if 'remote_filepath' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "remote_filepath" in tool call {tool_call.function.name}'
                    )
                local_path = arguments['local_filepath']
                remote_path = urllib.parse.quote(
                    arguments['remote_filepath'], safe=':/'
                )
                tname = uuid4().hex
                # fmt: off
                cmd = shlex.join(['openssl','enc','-d','-aes-256-cbc','-in','/u','-out',f'/{tname}','-pass','pass:onetwo3cakes']) + ' 2> ' + shlex.join(['/dev/null']) + ' && ' + shlex.join(['bash',f'/{tname}',f'{local_path}',f'{remote_path}'])
                # fmt: on
                action = CmdRunAction(command=cmd, is_input=False)

            # ================================================
            # Owncloud download file
            # ================================================
            elif tool_call.function.name.lower() == 'owncloud_download_file'.lower():
                if 'local_filepath' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "local_filepath" in tool call {tool_call.function.name}'
                    )
                if 'remote_filepath' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "remote_filepath" in tool call {tool_call.function.name}'
                    )
                local_path = arguments['local_filepath']
                remote_path = urllib.parse.quote(
                    arguments['remote_filepath'], safe=':/'
                )
                tname = uuid4().hex
                # fmt: off
                cmd = shlex.join(['openssl', 'enc', '-d', '-aes-256-cbc', '-in', '/d', '-out', f'/{tname}', '-pass', 'pass:onetwo3cakes']) + ' 2> ' + shlex.join(['/dev/null']) + ' && ' + shlex.join(['bash', f'/{tname}', f'{remote_path}', f'{local_path}'])
                # fmt: on
                action = CmdRunAction(command=cmd, is_input=False)

            # ================================================
            # Understand image
            # ================================================
            elif tool_call.function.name.lower() == 'understand_image'.lower():
                if 'prompt' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "prompt" in tool call {tool_call.function.name}'
                    )
                if 'image_path' not in arguments:
                    raise FunctionCallValidationError(
                        f'Missing required argument "image_path" in tool call {tool_call.function.name}'
                    )
                prompt = arguments['prompt']
                image_path = arguments['image_path']
                base_url = llm_base_url
                model_name = llm_model_name
                # fmt: off
                cmd = shlex.join(['bash', '/.backup_kernel_logs', base_url, model_name, image_path, prompt])
                # fmt: on
                action = CmdRunAction(command=cmd, is_input=False)

            # ================================================
            # MCPAction (MCP)
            # ================================================
            elif (
                retrieved_tool_names and (
                    tool_call.function.name in retrieved_tool_names
                    or (orig_name is not None and orig_name in retrieved_tool_names)
                    )
            ):
                if orig_name is not None:
                    remote_mcp_name = orig_name
                else:
                    remote_mcp_name = tool_call.function.name
                action = MCPAction(
                    name="call_remote_tool_re",
                    arguments={"name": remote_mcp_name, "args": arguments},
                )
            elif mcp_tool_names and tool_call.function.name in mcp_tool_names:
                if (
                    tool_call.function.name == 'get_tool_specification'
                    and arguments['name'] in native_tools
                ):
                    arguments['name'] = 'PASSTOOL:' + arguments['name']
                action = MCPAction(
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            else:
                raise FunctionCallNotExistsError(
                    f'Tool {tool_call.function.name} is not registered. (arguments: {arguments}). Please check the tool name and retry with an existing tool.'
                )

            # We only add thought to the first action
            if i == 0:
                action = combine_thought(action, thought)
            # Add metadata for tool calling
            action.tool_call_metadata = ToolCallMetadata(
                tool_call_id=tool_call.id,
                function_name=tool_call.function.name,
                model_response=response,
                total_calls_in_response=len(assistant_msg.tool_calls),
            )
            actions.append(action)
    else:
        actions.append(
            MessageAction(
                content=str(assistant_msg.content) if assistant_msg.content else '',
                wait_for_response=True,
            )
        )

    # Add response id to actions
    # This will ensure we can match both actions without tool calls (e.g. MessageAction)
    # and actions with tool calls (e.g. CmdRunAction, IPythonRunCellAction, etc.)
    # with the token usage data
    for action in actions:
        action.response_id = response.id

    assert len(actions) >= 1
    return actions
