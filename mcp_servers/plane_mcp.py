import asyncio
import socket
import sys
import time
from pathlib import Path
from typing import Annotated, List

import plane_api_client
import requests
from fastmcp import FastMCP
from fastmcp.server.proxy import ProxyClient
from fastmcp.tools import Tool
from pydantic import Field

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

while True:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(
        ("localhost", mcp_configs.ALL_SERVER_PORTS["plane_transport_proxy"])
    )
    sock.close()
    if result != 0:
        print("Waiting for official plane server")
        time.sleep(2)
    else:
        break


mcp = FastMCP("Plane")
proxy = FastMCP.as_proxy(
    ProxyClient(
        f"http://localhost:{mcp_configs.ALL_SERVER_PORTS['plane_transport_proxy']}/sse"
    )
)
asyncio.run(mcp.import_server(proxy))


@mcp.tool
def get_user():
    """Get the information for the current user."""
    with plane_api_client.PlaneAPIClient() as client:
        response = client.session.get(f"{client.base_url}/api/users/me/")
        return response.json()


@mcp.tool
def get_workspace_members():
    """Get all members in a workspace."""
    return plane_api_client.get_workspace_members()


@mcp.tool
def get_workspace_member_by_id(
    member_id: Annotated[
        str, Field(description="UUID of the member to return his/her info.")
    ],
):
    """Get the information for the user with the given UUID."""
    return plane_api_client.get_workspace_member_by_id(member_id=member_id)


@mcp.tool
def get_all_issues_of_project(
    project_uuid: Annotated[str, Field(description="UUID of the project")],
):
    """Get a list of all issues in a project."""
    return plane_api_client.get_all_issues_of_project(project_uuid=project_uuid)


@mcp.tool
def add_member_to_project(
    project_id: Annotated[str, Field(description="UUID of the project")],
    member_id: Annotated[str, Field(description="UUID of the member")],
    member_role: Annotated[
        str,
        Field(
            description="member's intended role in this project. Must be one of admin, member, viewer, or guest."
        ),
    ],
):
    """Add a member to a project.

    Here is a description of possible roles:
        - admin: Full control over project, can manage settings and members
        - member: Can create, edit, and manage issues and project content
        - viewer: Can view and comment on issues, limited editing
        - guest: View-only access to specific issues
    """
    return plane_api_client.add_member_to_project(
        project_id=project_id, member_id=member_id, member_role=member_role
    )


@mcp.tool
def create_issue(
    project_id: Annotated[str, Field(description="UUID of the project")],
    name: Annotated[str, Field(description="name of the issue")],
    description_html: Annotated[
        str, Field(description="Description of the issue. Supports html formatting.")
    ],
    assignees: Annotated[
        List[str] | None,
        Field(description="UUID of the members to assign to this issue (optional)"),
    ] = None,
    state: Annotated[
        str | None, Field(description="UUID of the state for this issue (Optional)")
    ] = None,
):
    """Create an issue in Plane."""
    base_url = mcp_configs.TAC_SERVICES["plane"]["url"].strip("/")
    url = f"{base_url.rstrip('/')}/api/v1/workspaces/tac/projects/{project_id}/issues/"
    headers = {
        "X-API-Key": mcp_configs.TAC_SERVICES["plane"]["token"],
        "Content-Type": "application/json",
    }
    payload = {"name": name, "description_html": description_html}
    if assignees is not None:
        payload["assignees"] = assignees
    if state is not None:
        payload["state"] = state
    resp = requests.post(url, json=payload, headers=headers, timeout=30)
    if not resp.ok:
        try:
            err = resp.json()
        except Exception as e:
            raise e
    return resp.json()


@mcp.tool
def get_analytics_metric_summary():
    """Get the summary of the analytics metrics for the workspace. It returns the following
    metrics: number of total tasks, open tasks, backlog tasks, started tasks, unstarted tasks,
    unassigned issues, pending issues.

    It returns the value of these metrics:
        - total tasks
        - open tasks
        - backlog tasks
        - started tasks
        - unstarted tasks
        - unassigned issues
        - pending issues
    """
    return plane_api_client.get_analytics_metric_summary()


@mcp.tool
def delete_project(
    project_uuid: Annotated[str, Field(description="UUID of the project to delete")],
):
    """Delete the given project."""
    return plane_api_client.delete_project(project_uuid=project_uuid)


@mcp.tool
def get_all_issues_in_workspace(
    due_date_order: Annotated[
        str,
        Field(
            description="Determines the sort order based on due date. It must be one of 'ascending' or 'descending'"
        ),
    ],
    topk: Annotated[
        int | None,
        Field(
            description="Number of results to return. If it is not specified, returns all issues"
        ),
    ] = None,
):
    """Get the issues from all projects in the workspace."""
    return plane_api_client.get_all_issues_in_workspace(
        due_date_order=due_date_order, topk=topk
    )


tool = asyncio.run(mcp.get_tool("get_issue_using_readable_identifier"))
new_tool = Tool.from_tool(
    tool,
    description="Get details of a specific issue in a specific project. It needs the readable identifier of the project and the issue ID.",
)
mcp.add_tool(new_tool)

if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["plane_main"])
