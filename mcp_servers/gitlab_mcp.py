import asyncio
import socket
import sys
import time
import urllib
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Any, Literal, Optional, Sequence, Union

import requests
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from fastmcp.tools import Tool
from fastmcp.tools.tool_transform import ArgTransform, forward
from pydantic import Field

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

for n in ["gitlab_openapi", "gitlab_transport_proxy"]:
    p = mcp_configs.ALL_SERVER_PORTS[n]
    while True:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(("localhost", p))
        sock.close()
        if result != 0:
            print(f"Waiting for GitLab {n} server")
            time.sleep(2)
        else:
            break

mcp = FastMCP("GitLab")


BASE_URL = mcp_configs.TAC_SERVICES["gitlab"]["url"].strip("/")
PRIVATE_TOKEN = mcp_configs.TAC_SERVICES["gitlab"]["token"]


def _url_encode_str(x) -> str:
    if not isinstance(x, str):
        return x
    return urllib.parse.quote(urllib.parse.unquote(x), safe="")


@mcp.tool
def get_project_issues_statistics(
    project_id: Annotated[Union[int, str], "Project ID or path"],
    labels: Annotated[
        Optional[Union[str, Sequence[str]]],
        "Label filter. Pass a comma-separated string or a list; accepts special values 'None' (no labels) and 'Any' (at least one label).",
    ] = None,
    milestone: Annotated[
        Optional[str],
        "Milestone title. Accepts 'None' (no milestone) or 'Any' (any milestone).",
    ] = None,
    scope: Annotated[
        Optional[Literal["created_by_me", "assigned_to_me", "all"]],
        "Issue scope filter. Defaults to GitLab's API default when omitted.",
    ] = None,
    author_id: Annotated[
        Optional[int],
        "Filter by author user ID. Mutually exclusive with author_username.",
    ] = None,
    author_username: Annotated[
        Optional[str],
        "Filter by author username. Mutually exclusive with author_id.",
    ] = None,
    assignee_id: Annotated[
        Optional[Union[int, Literal["None", "Any"]]],
        "Filter by assignee user ID, or use the strings 'None' (unassigned) / 'Any' (has assignee). Mutually exclusive with assignee_username.",
    ] = None,
    assignee_username: Annotated[
        Optional[Sequence[str]],
        "Filter by one or more assignee usernames. In GitLab CE only a single value is allowed.",
    ] = None,
    epic_id: Annotated[
        Optional[Union[int, Literal["None", "Any"]]],
        "Filter by Epic ID, or the strings 'None'/'Any'. (Premium/Ultimate only on GitLab).",
    ] = None,
    my_reaction_emoji: Annotated[
        Optional[Union[str, Literal["None", "Any"]]],
        "Filter by an emoji the authenticated user reacted with, or 'None'/'Any'.",
    ] = None,
    iids: Annotated[
        Optional[Sequence[int]],
        "Return only issues with these IIDs. Encoded as repeated iids[] parameters.",
    ] = None,
    search: Annotated[
        Optional[str],
        "Full-text search string for title/description.",
    ] = None,
    search_in: Annotated[
        Optional[Literal["title", "description", "title,description"]],
        "Restrict where 'search' is applied. Defaults to 'title,description' when omitted.",
    ] = None,
    state: Annotated[
        Optional[Literal["opened", "closed", "all"]],
        "Issue state filter (supported by the official examples).",
    ] = None,
    created_after: Annotated[
        Optional[datetime],
        "Return issues created on or after this timestamp (UTC ISO-8601).",
    ] = None,
    created_before: Annotated[
        Optional[datetime],
        "Return issues created on or before this timestamp (UTC ISO-8601).",
    ] = None,
    updated_after: Annotated[
        Optional[datetime],
        "Return issues updated on or after this timestamp (UTC ISO-8601).",
    ] = None,
    updated_before: Annotated[
        Optional[datetime],
        "Return issues updated on or before this timestamp (UTC ISO-8601).",
    ] = None,
    confidential: Annotated[
        Optional[bool],
        "If set, filter by confidential (True) or public (False) issues.",
    ] = None,
):
    """Get issues count statistics for a project.

    Returns the JSON response as a Python `dict`. The response includes counts for `all`, `opened`, and `closed` issues.

    Returns:
        JSON dictionary parsed from the API response. Example:
        `{"statistics": {"counts": {"all": 20, "closed": 5, "opened": 15}}}`.

    Raises:
        ValueError: If mutually exclusive parameters are provided together.
        requests.HTTPError: For non-2xx responses (with response text included).
    """

    def _iso(dt: datetime) -> str:
        # Convert datetimes to strict UTC Z format expected by GitLab examples.
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Validate mutual exclusivity
    if author_id is not None and author_username is not None:
        raise ValueError("author_id and author_username are mutually exclusive.")
    if assignee_id is not None and assignee_username:
        raise ValueError("assignee_id and assignee_username are mutually exclusive.")

    base = BASE_URL.rstrip("/")
    encoded_id = _url_encode_str(project_id)
    # encoded_id = quote_plus(str(project_id))
    url = f"{base}/api/v4/projects/{encoded_id}/issues_statistics"

    # Build headers
    headers: dict[str, str] = {"Accept": "application/json"}
    headers["PRIVATE-TOKEN"] = PRIVATE_TOKEN

    # Build params (use list of tuples to support repeated keys like iids[])
    params: list[tuple[str, str]] = []

    def add(name: str, value: Optional[Union[str, int, bool]]):
        if value is None:
            return
        params.append((name, str(value)))

    # Simple scalars
    add("milestone", milestone)
    add("scope", scope)
    add("author_id", author_id)
    add("author_username", author_username)
    # assignee_id allows strings 'None'/'Any' in addition to int
    if assignee_id is not None:
        add("assignee_id", assignee_id)  # str or int
    # epic_id allows strings 'None'/'Any' or int
    if epic_id is not None:
        add("epic_id", epic_id)
    # reaction allows 'None'/'Any' too
    if my_reaction_emoji is not None:
        add("my_reaction_emoji", my_reaction_emoji)
    add("search", search)
    add("in", search_in)
    add("state", state)
    if confidential is not None:
        add("confidential", "true" if confidential else "false")

    # Date filters
    if created_after:
        add("created_after", _iso(created_after))
    if created_before:
        add("created_before", _iso(created_before))
    if updated_after:
        add("updated_after", _iso(updated_after))
    if updated_before:
        add("updated_before", _iso(updated_before))

    # Labels can be str or list[str]
    if labels is not None:
        if isinstance(labels, str):
            add("labels", labels)
        else:
            add("labels", ",".join(labels))

    # Repeated array params
    if assignee_username:
        for uname in assignee_username:
            params.append(("assignee_username[]", uname))
    if iids:
        for iid in iids:
            params.append(("iids[]", str(iid)))

    resp = requests.get(url, headers=headers, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Include response body for easier debugging
        raise requests.HTTPError(f"{e}\nBody: {resp.text}") from None
    return resp.json()


@mcp.tool
def search_in_project(
    project_id: Annotated[
        str | int,
        Field(description="Project ID or Path"),
    ],
    scope: Annotated[
        Literal[
            "issues",
            "merge_requests",
            "milestones",
            "users",
            "wiki_blobs",
            "commits",
            "blobs",
            "notes",
        ],
        Field(description="Resource scope to search within the project."),
    ],
    search: Annotated[
        str,
        Field(
            description="Search term. For 'blobs', you may include filters like 'path:', 'filename:' (deprecated), or 'extension:'."
        ),
    ],
    confidential: Annotated[
        bool | None,
        Field(
            description="Filter by confidentiality; only applies to 'issues' scope. Others ignore it."
        ),
    ] = None,
    ref: Annotated[
        str | None,
        Field(
            description="Branch or tag name to search; only applies to 'blobs', 'commits', and 'wiki_blobs'. Defaults to the project's default branch if omitted."
        ),
    ] = None,
    order_by: Annotated[
        Literal["created_at"] | None,
        Field(
            description="Sort column (basic search). If omitted, results are sorted by relevance (advanced) or created_at (basic)."
        ),
    ] = None,
    sort: Annotated[
        Literal["asc", "desc"] | None,
        Field(
            description="Sort direction when 'order_by' is used or for basic search."
        ),
    ] = None,
    state: Annotated[
        Literal["opened", "closed", "merged", "locked"] | None,
        Field(
            description="Filter by state; supported for 'issues' (opened/closed) and 'merge_requests' (opened/closed/merged/locked). Others ignore it."
        ),
    ] = None,
    page: Annotated[
        int | None, Field(ge=1, description="Offset-based page number.")
    ] = None,
    per_page: Annotated[
        int | None, Field(ge=1, le=100, description="Items per page (max 100).")
    ] = None,
):
    """Search within a specific project using GitLab's Search API.

    Returns
    -------
    dict
        {
          "results": <list>,             # JSON array returned by GitLab
          "scope": <str>,                # Echoes the scope used
          "pagination": {                # Parsed pagination headers (when present)
              "x_next_page": int | None,
              "x_page": int | None,
              "x_per_page": int | None,
              "x_prev_page": int | None,
              "x_total": int | None,
              "x_total_pages": int | None
          }
        }
    """
    # Normalize and encode
    base = BASE_URL.rstrip("/")
    pid = _url_encode_str(project_id)

    url = f"{base}/api/v4/projects/{pid}/search"

    # Build query parameters
    params: dict[str, Any] = {
        "scope": scope,
        "search": search,
    }
    if confidential is not None:
        params["confidential"] = str(confidential).lower()
    if ref is not None:
        params["ref"] = ref
    if order_by is not None:
        params["order_by"] = order_by
    if sort is not None:
        params["sort"] = sort
    if state is not None:
        params["state"] = state
    if page is not None:
        params["page"] = page
    if per_page is not None:
        params["per_page"] = per_page

    # Auth headers
    headers: dict[str, str] = {}
    headers["PRIVATE-TOKEN"] = PRIVATE_TOKEN

    # Perform request
    resp = requests.get(url, headers=headers, params=params, timeout=30, verify=False)
    resp.raise_for_status()

    data = resp.json()

    # Parse pagination headers (offset-based)
    def _to_int(h: str) -> int | None:
        val = resp.headers.get(h) or ""
        return int(val) if val.isdigit() else None

    pagination = {
        "x_next_page": _to_int("X-Next-Page"),
        "x_page": _to_int("X-Page"),
        "x_per_page": _to_int("X-Per-Page"),
        "x_prev_page": _to_int("X-Prev-Page"),
        "x_total": _to_int("X-Total"),
        "x_total_pages": _to_int("X-Total-Pages"),
    }

    return {
        "results": data,
        "scope": scope,
        "pagination": pagination,
    }


def _iso8601(dt: datetime) -> str:
    """Convert a datetime to an ISO 8601 UTC string with trailing 'Z'."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


@mcp.tool
def create_issue_note(
    project: Annotated[
        int | str, Field(description="Project ID or name with namespace")
    ],
    issue_iid: Annotated[int, Field(description="The IID of the target issue.")],
    body: Annotated[
        str, Field(description="The content of the note (1 to 1,000,000 characters).")
    ],
    internal: Annotated[
        bool | None,
        Field(
            description=(
                "If true, creates an internal note (visible only to users with the "
                "appropriate permissions). "
                "Default is false on the server."
            )
        ),
    ] = None,
    created_at: Annotated[
        datetime | str | None,
        Field(
            description=(
                "Creation timestamp (ISO 8601, e.g., '2016-03-11T03:45:40Z'). "
                "If a datetime is provided, it will be converted to UTC ISO-8601. "
                "Must be after 1970-01-01. Requires administrator or project/group owner rights."
            )
        ),
    ] = None,
):
    """Create a new note on a single project issue."""
    # Normalize project ref
    project_ref = _url_encode_str(project)
    project_ref = str(project_ref)

    # Validate/normalize created_at
    payload: dict[str, Any] = {"body": body}
    if internal is not None:
        payload["internal"] = internal
    if created_at is not None:
        if isinstance(created_at, datetime):
            iso = _iso8601(created_at)
        else:
            # Assume caller provided a valid ISO-8601 string
            iso = created_at
        # Simple sanity check vs Unix epoch
        if iso < "1970-01-01T00:00:00Z":
            raise ValueError("created_at must be after 1970-01-01T00:00:00Z")
        payload["created_at"] = iso

    # Build URL and headers
    base_url = BASE_URL.rstrip("/")
    url = (
        f"{base_url.rstrip('/')}/api/v4/projects/{project_ref}/issues/{issue_iid}/notes"
    )
    headers: dict[str, str] = {
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    headers["PRIVATE-TOKEN"] = PRIVATE_TOKEN

    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


proxy = FastMCP.as_proxy(
    ProxyClient(
        f"http://localhost:{mcp_configs.ALL_SERVER_PORTS['gitlab_openapi']}/sse"
    )
)
asyncio.run(mcp.import_server(proxy))


def _npx_url_encode_str(x) -> str:
    if not isinstance(x, str):
        return x
    return urllib.parse.quote(urllib.parse.unquote(x), safe=":/")


async def npx_url_encode_wrapper(**kwargs):
    if "project_id" in kwargs:
        kwargs["project_id"] = _npx_url_encode_str(kwargs["project_id"])
    res = await forward(**kwargs)
    res.structured_content = None
    return res


npx_proxy = FastMCP.as_proxy(
    ProxyClient(
        f"http://localhost:{mcp_configs.ALL_SERVER_PORTS['gitlab_transport_proxy']}/sse"
    )
)


async def add_tool_from_npx_proxy(name: str):
    tool = await npx_proxy.get_tool(name)
    from_tool_kwargs = dict()
    from_tool_kwargs["transform_args"] = dict()
    from_tool_kwargs["transform_fn"] = npx_url_encode_wrapper

    if "project_id" in tool.model_dump()["parameters"]["properties"]:
        from_tool_kwargs["transform_args"]["project_id"] = ArgTransform(
            required=True, description="The global ID or path of the project."
        )

    if name == "list_issues":
        from_tool_kwargs["name"] = "list_project_issues"
        from_tool_kwargs["transform_args"]["scope"] = ArgTransform(default="all")
    elif name == "delete_issue":
        from_tool_kwargs["transform_args"]["issue_iid"] = ArgTransform(required=True)
    elif name == "get_issue":
        from_tool_kwargs["name"] = "get_specific_issue"
        from_tool_kwargs["transform_args"]["issue_iid"] = ArgTransform(required=True)
    elif name == "update_issue":
        from_tool_kwargs["transform_args"]["issue_iid"] = ArgTransform(required=True)
    elif name == "list_issue_discussions":
        from_tool_kwargs["transform_args"]["issue_iid"] = ArgTransform(required=True)
    elif name == "mr_discussions":
        from_tool_kwargs["transform_args"]["merge_request_iid"] = ArgTransform(
            required=True
        )
    elif name == "edit_milestone":
        from_tool_kwargs["transform_args"]["milestone_id"] = ArgTransform(required=True)

    if len(from_tool_kwargs["transform_args"]) == 0:
        from_tool_kwargs.pop("transform_args")
    new_tool = Tool.from_tool(tool, **from_tool_kwargs)
    mcp.add_tool(new_tool)


npx_useful_tool_names = [
    "list_issues",
    "create_issue",
    "delete_issue",
    "get_issue",
    "update_issue",
    "list_issue_discussions",
    "mr_discussions",
    "edit_milestone",
    "list_milestones",
    "create_milestone",
]
for n in npx_useful_tool_names:
    asyncio.run(add_tool_from_npx_proxy(n))

if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["gitlab_main"])
