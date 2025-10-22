import os
import sys
from collections import deque
from typing import TYPE_CHECKING
from pathlib import Path
from datetime import datetime
from uuid import uuid4

if TYPE_CHECKING:
    from litellm import ChatCompletionToolParam

    from openhands.events.action import Action
    from openhands.llm.llm import ModelResponse

import openhands.agenthub.codeact_agent.function_calling as codeact_function_calling
from openhands.agenthub.codeact_agent.tools.bash import create_cmd_run_tool
from openhands.agenthub.codeact_agent.tools.browser import BrowserTool
from openhands.agenthub.codeact_agent.tools.condensation_request import (
    CondensationRequestTool,
)
from openhands.agenthub.codeact_agent.tools.finish import FinishTool
from openhands.agenthub.codeact_agent.tools.ipython import IPythonTool
from openhands.agenthub.codeact_agent.tools.llm_based_edit import LLMBasedFileEditTool
from openhands.agenthub.codeact_agent.tools.str_replace_editor import (
    create_str_replace_editor_tool,
)
from openhands.agenthub.codeact_agent.tools.think import ThinkTool
from openhands.controller.agent import Agent
from openhands.controller.state.state import State
from openhands.core.config import AgentConfig
from openhands.core.logger import openhands_logger as logger
from openhands.core.message import Message
from openhands.events.action import AgentFinishAction, MessageAction
from openhands.events.event import Event
from openhands.llm.llm import LLM
from openhands.llm.llm_utils import check_tools
from openhands.memory.condenser import Condenser
from openhands.memory.condenser.condenser import Condensation, View
from openhands.memory.conversation_memory import ConversationMemory
from openhands.runtime.plugins import (
    AgentSkillsRequirement,
    JupyterRequirement,
    PluginRequirement,
)
from openhands.utils.prompt import PromptManager

########################################################################################
## Chagnes for dynamic tool parsing
########################################################################################
import json

from litellm import ChatCompletionToolParam
from openhands.events.observation.mcp import MCPObservation
from openhands.mcp.tool import MCPClientTool

TOOL_FINDER_FUNCTIONS=['find_tools', 'get_tool_specification']

########################################################################################
########################################################################################


class CodeActAgent(Agent):
    VERSION = '2.2'
    """
    The Code Act Agent is a minimalist agent.
    The agent works by passing the model a list of action-observation pairs and prompting the model to take the next step.

    ### Overview

    This agent implements the CodeAct idea ([paper](https://arxiv.org/abs/2402.01030), [tweet](https://twitter.com/xingyaow_/status/1754556835703751087)) that consolidates LLM agents' **act**ions into a unified **code** action space for both *simplicity* and *performance* (see paper for more details).

    The conceptual idea is illustrated below. At each turn, the agent can:

    1. **Converse**: Communicate with humans in natural language to ask for clarification, confirmation, etc.
    2. **CodeAct**: Choose to perform the task by executing code
    - Execute any valid Linux `bash` command
    - Execute any valid `Python` code with [an interactive Python interpreter](https://ipython.org/). This is simulated through `bash` command, see plugin system below for more details.

    ![image](https://github.com/All-Hands-AI/OpenHands/assets/38853559/92b622e3-72ad-4a61-8f41-8c040b6d5fb3)

    """

    sandbox_plugins: list[PluginRequirement] = [
        # NOTE: AgentSkillsRequirement need to go before JupyterRequirement, since
        # AgentSkillsRequirement provides a lot of Python functions,
        # and it needs to be initialized before Jupyter for Jupyter to use those functions.
        AgentSkillsRequirement(),
        JupyterRequirement(),
    ]

    def __init__(
        self,
        llm: LLM,
        config: AgentConfig,
    ) -> None:
        """Initializes a new instance of the CodeActAgent class.

        Parameters:
        - llm (LLM): The llm to be used by this agent
        - config (AgentConfig): The configuration for this agent
        """
        super().__init__(llm, config)
        self.pending_actions: deque['Action'] = deque()
        self.reset()
        self.tools = self._get_tools()
        self.native_tool_names = [t['function']['name'] for t in self.tools]
        self.retrieved_tools = dict()

        # Create a ConversationMemory instance
        self.conversation_memory = ConversationMemory(self.config, self.prompt_manager)

        self.condenser = Condenser.from_config(self.config.condenser)
        logger.debug(f'Using condenser: {type(self.condenser)}')

        # the number of times we have called the LLM
        self._llm_call_idx = 0
        self._curr_time = datetime.now()
        self._uuid = uuid4().hex

    @property
    def prompt_manager(self) -> PromptManager:
        if self._prompt_manager is None:
            self._prompt_manager = PromptManager(
                prompt_dir=os.path.join(os.path.dirname(__file__), 'prompts'),
                system_prompt_filename=self.config.system_prompt_filename,
            )

        return self._prompt_manager

    def _get_tools(self) -> list['ChatCompletionToolParam']:
        # For these models, we use short tool descriptions ( < 1024 tokens)
        # to avoid hitting the OpenAI token limit for tool descriptions.
        SHORT_TOOL_DESCRIPTION_LLM_SUBSTRS = ['gpt-', 'o3', 'o1', 'o4']

        use_short_tool_desc = False
        if self.llm is not None:
            use_short_tool_desc = any(
                model_substr in self.llm.config.model
                for model_substr in SHORT_TOOL_DESCRIPTION_LLM_SUBSTRS
            )

        tools = []
        if self.config.enable_cmd:
            tools.append(create_cmd_run_tool(use_short_description=use_short_tool_desc))
        if self.config.enable_think:
            tools.append(ThinkTool)
        if self.config.enable_finish:
            tools.append(FinishTool)
        if self.config.enable_condensation_request:
            tools.append(CondensationRequestTool)
        if self.config.enable_browsing:
            if sys.platform == 'win32':
                logger.warning('Windows runtime does not support browsing yet')
            else:
                tools.append(BrowserTool)
        if self.config.enable_jupyter:
            tools.append(IPythonTool)
        if self.config.enable_llm_editor:
            tools.append(LLMBasedFileEditTool)
        elif self.config.enable_editor:
            tools.append(
                create_str_replace_editor_tool(
                    use_short_description=use_short_tool_desc
                )
            )
        return tools

    def reset(self) -> None:
        """Resets the CodeAct Agent's internal state."""
        super().reset()
        # Only clear pending actions, not LLM metrics
        self.pending_actions.clear()
        self.retrieved_tools = dict()

    def step(self, state: State) -> 'Action':
        """Performs one step using the CodeAct Agent.

        This includes gathering info on previous steps and prompting the model to make a command to execute.

        Parameters:
        - state (State): used to get updated info

        Returns:
        - CmdRunAction(command) - bash command to run
        - IPythonRunCellAction(code) - IPython code to run
        - AgentDelegateAction(agent, inputs) - delegate action for (sub)task
        - MessageAction(content) - Message action to run (e.g. ask for clarification)
        - AgentFinishAction() - end the interaction
        """
        # Continue with pending actions if any
        if self.pending_actions:
            return self.pending_actions.popleft()

        ###########################################
        ###########################################
        ## Modify history to chagne the output of
        ## the MCP gateway function
        ###########################################
        ###########################################
        for hist_idx in range(len(state.history)):
            if isinstance(state.history[hist_idx], MCPObservation):
                obs_content = json.loads(state.history[hist_idx].content)
                obs_content.pop('structuredContent', None)
                obs_content.pop('data', None)
                obs_content.pop('structured_content', None)
                obs_content.pop('annotations', None)
                obs_content.pop('meta', None)
                obs_content.pop('_meta', None)
                if (
                    isinstance(obs_content.get("content", None), list)
                    and len(obs_content["content"]) == 1
                    and isinstance(obs_content["content"][0], dict)
                    and "text" in obs_content["content"][0]
                ):
                    inner_cnt = obs_content['content'][0]['text']
                    try:
                        inner_obj = json.loads(inner_cnt)
                        if isinstance(inner_obj, dict):
                            inner_obj.pop('structuredContent', None)
                            inner_obj.pop('data', None)
                            inner_obj.pop('structured_content', None)
                            inner_obj.pop('annotations', None)
                            inner_obj.pop('meta', None)
                            inner_obj.pop('_meta', None)
                        inner_cnt = json.dumps(inner_obj)
                    except:
                        pass
                    obs_content['content'][0]['text'] = inner_cnt

                state.history[hist_idx].content = json.dumps(obs_content)

        TOOL_FINDER_FUNCTION = None
        for tn in TOOL_FINDER_FUNCTIONS:
            if tn in self.mcp_tools:
                TOOL_FINDER_FUNCTION = tn
                break
        if TOOL_FINDER_FUNCTION in self.mcp_tools:
            for hist_idx in range(len(state.history)):
                if isinstance(state.history[hist_idx], MCPObservation) and state.history[hist_idx].name == TOOL_FINDER_FUNCTION:
                    obs_content = state.history[hist_idx].content
                    obs_content = json.loads(obs_content)
                    assert len(obs_content['content']) == 1
                    try:
                        fn_res = json.loads(obs_content['content'][0]['text'])
                    except:
                        fn_res = obs_content['content'][0]['text']

                    if isinstance(fn_res[0], dict) and 'inputSchema' in fn_res[0]:
                        new_fn_res = [r['name'] for r in fn_res]
                        obs_content['content'][0]['text'] = json.dumps(new_fn_res, indent=2)
                        state.history[hist_idx].content = json.dumps(obs_content)

                        for _tool_spec in fn_res:
                            if _tool_spec['name'] in self.native_tool_names:
                                continue
                            _new_tool = MCPClientTool(name=_tool_spec['name'],
                                description=_tool_spec['description'],
                                inputSchema=_tool_spec['inputSchema']
                                )
                            _new_tool = _new_tool.to_param()
                            _new_tool = ChatCompletionToolParam(**_new_tool)
                            if _new_tool['function']['name'] in self.retrieved_tools:
                                logger.warning(f'Tool {_new_tool["function"]["name"]} already exists, skipping')
                                continue
                            self.retrieved_tools[_new_tool['function']['name']] = _new_tool
        ###########################################
        ###########################################
        ###########################################
        ###########################################

        # if we're done, go back
        latest_user_message = state.get_last_user_message()
        if latest_user_message and latest_user_message.content.strip() == '/exit':
            return AgentFinishAction()

        # Condense the events from the state. If we get a view we'll pass those
        # to the conversation manager for processing, but if we get a condensation
        # event we'll just return that instead of an action. The controller will
        # immediately ask the agent to step again with the new view.
        condensed_history: list[Event] = []
        match self.condenser.condensed_history(state):
            case View(events=events):
                condensed_history = events

            case Condensation(action=condensation_action):
                return condensation_action

        logger.debug(
            f'Processing {len(condensed_history)} events from a total of {len(state.history)} events'
        )
        #######
        log_dir = None
        if self.llm.config.log_completions and self.llm.config.log_completions_folder:
            log_dir = Path(self.llm.config.log_completions_folder, "raw_llm_io")
            subdir_name = state.session_id + "_" + self._curr_time.strftime("%d-%m-%y_%H-%M-%S-%f")
            if os.environ.get('RE_TRACE_NAME', None) is not None:
                subdir_name = os.environ['RE_TRACE_NAME'] + '_' + subdir_name
            log_dir = log_dir.joinpath(subdir_name)
        ########

        initial_user_message = self._get_initial_user_message(state.history)
        messages = self._get_messages(condensed_history, initial_user_message)
        params: dict = {
            'messages': self.llm.format_messages_for_llm(messages),
        }
        tools_in_prompt = check_tools(self.tools + list(self.retrieved_tools.values()), self.llm.config)
        rv_map = None
        if any(v.lower() in self.llm.config.model.lower() for v in ['claude', 'sonnet', 'opus']):
            tools_in_prompt, rv_map = codeact_function_calling.prep_tools_for_claude(tools_in_prompt)
        params['tools'] = tools_in_prompt
        params['extra_body'] = {'metadata': state.to_llm_metadata(agent_name=self.name)}
        trace_name = None
        if os.environ.get('RE_TRACE_NAME', None) is not None:
            trace_name = os.environ['RE_TRACE_NAME'] + '_' + self._curr_time.strftime("%d-%m-%y_%H-%M")
            if 'session_id' in params['extra_body']['metadata']:
                trace_name = trace_name + '-' + params['extra_body']['metadata']['session_id'].split('-')[0].strip()
            params['extra_body']['metadata']['re_trace_name'] = trace_name

        _logging_kwargs = {
                'experiment': trace_name if trace_name is not None else state.session_id,
                'span': str(self._llm_call_idx),
                'log_dir': log_dir.absolute().resolve().as_posix(),
                'prompt_filename': f"{self._llm_call_idx}_prompt.json",
                'response_filename': f"{self._llm_call_idx}_response.json",
                }
        response = self.llm.completion(logging_kwargs=_logging_kwargs, **params)
        self._llm_call_idx += 1
        # just make sure we have called the correct function
        assert _logging_kwargs['visited'] == 'true'

        logger.debug(f'Response from LLM: {response}')
        actions = self.response_to_actions(response, rv_map=rv_map)
        logger.debug(f'Actions after response_to_actions: {actions}')
        for action in actions:
            self.pending_actions.append(action)
        return self.pending_actions.popleft()

    def _get_initial_user_message(self, history: list[Event]) -> MessageAction:
        """Finds the initial user message action from the full history."""
        initial_user_message: MessageAction | None = None
        for event in history:
            if isinstance(event, MessageAction) and event.source == 'user':
                initial_user_message = event
                break

        if initial_user_message is None:
            # This should not happen in a valid conversation
            logger.error(
                f'CRITICAL: Could not find the initial user MessageAction in the full {len(history)} events history.'
            )
            # Depending on desired robustness, could raise error or create a dummy action
            # and log the error
            raise ValueError(
                'Initial user message not found in history. Please report this issue.'
            )
        return initial_user_message

    def _get_messages(
        self, events: list[Event], initial_user_message: MessageAction
    ) -> list[Message]:
        """Constructs the message history for the LLM conversation.

        This method builds a structured conversation history by processing events from the state
        and formatting them into messages that the LLM can understand. It handles both regular
        message flow and function-calling scenarios.

        The method performs the following steps:
        1. Checks for SystemMessageAction in events, adds one if missing (legacy support)
        2. Processes events (Actions and Observations) into messages, including SystemMessageAction
        3. Handles tool calls and their responses in function-calling mode
        4. Manages message role alternation (user/assistant/tool)
        5. Applies caching for specific LLM providers (e.g., Anthropic)
        6. Adds environment reminders for non-function-calling mode

        Args:
            events: The list of events to convert to messages

        Returns:
            list[Message]: A list of formatted messages ready for LLM consumption, including:
                - System message with prompt (from SystemMessageAction)
                - Action messages (from both user and assistant)
                - Observation messages (including tool responses)
                - Environment reminders (in non-function-calling mode)

        Note:
            - In function-calling mode, tool calls and their responses are carefully tracked
              to maintain proper conversation flow
            - Messages from the same role are combined to prevent consecutive same-role messages
            - For Anthropic models, specific messages are cached according to their documentation
        """
        if not self.prompt_manager:
            raise Exception('Prompt Manager not instantiated.')

        # Use ConversationMemory to process events (including SystemMessageAction)
        messages = self.conversation_memory.process_events(
            condensed_history=events,
            initial_user_action=initial_user_message,
            max_message_chars=self.llm.config.max_message_chars,
            vision_is_active=self.llm.vision_is_active(),
        )

        if self.llm.is_caching_prompt_active():
            self.conversation_memory.apply_prompt_caching(messages)

        return messages

    def response_to_actions(self, response: 'ModelResponse', rv_map: None | dict = None) -> list['Action']:
        return codeact_function_calling.response_to_actions(
            response,
            mcp_tool_names=list(self.mcp_tools.keys()),
            retrieved_tool_names=list(self.retrieved_tools.keys()),
            native_tools=self.native_tool_names,
            llm_model_name=self.llm.config.model.removeprefix('litellm_proxy/'),
            llm_base_url=None if self.llm.config.base_url is None else self.llm.config.base_url.rstrip('/'),
            argname_mapping=rv_map,
        )
