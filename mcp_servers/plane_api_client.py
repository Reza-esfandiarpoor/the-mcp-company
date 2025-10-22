import sys
from pathlib import Path

import requests

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs


class PlaneAPIClient:
    """Self-contained Plane API client that handles authentication and API calls."""

    def __init__(
        self,
        base_url=mcp_configs.TAC_SERVICES["plane"]["url"],
        email=mcp_configs.TAC_SERVICES["plane"]["email"],
        password=mcp_configs.TAC_SERVICES["plane"]["password"],
    ):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.csrf_token = None
        self.authenticated = False
        self.email = email
        self.password = password

    def _get_csrf_token(self):
        """Get CSRF token from the server."""
        try:
            response = self.session.get(f"{self.base_url}/auth/get-csrf-token/")
            response.raise_for_status()

            data = response.json()
            self.csrf_token = data.get("csrf_token")
            return self.csrf_token is not None
        except (requests.RequestException, ValueError, KeyError) as e:
            print(f"Failed to get CSRF token: {e}")
            return False

    def login(self, email=None, password=None):
        """Authenticate with Plane using email and password.

        Args:
            email (str): User's email address
            password (str): User's password

        Returns:
            bool: True if authentication successful, False otherwise
        """
        # Step 1: Get CSRF token
        if not self._get_csrf_token():
            raise RuntimeError("count not get csrf token")

        # Step 2: Set up headers for login
        self.session.headers.update(
            {
                "X-CSRFToken": self.csrf_token,
                "Referer": self.base_url,
                "Content-Type": "application/x-www-form-urlencoded",
            }
        )

        if email is None:
            email = self.email
        if password is None:
            password = self.password

        # Step 3: Attempt login
        login_data = {"email": email.strip().lower(), "password": password}

        try:
            response = self.session.post(
                f"{self.base_url}/auth/sign-in/",
                data=login_data,
                allow_redirects=False,  # Don't follow redirects to catch auth success
            )

            # Check if login was successful
            # Successful login typically returns 302 (redirect) or 200
            if response.status_code in [200, 302]:
                self.authenticated = True
                # Update headers for API calls
                self.session.headers.update({"Content-Type": "application/json"})
                return True
            else:
                print(f"Login failed with status code: {response.status_code}")
                if response.text:
                    print(f"Response: {response.text[:200]}")
                return False

        except requests.RequestException as e:
            raise e

    def logout(self):
        """Logout and clear session."""
        try:
            self.session.post(f"{self.base_url}/auth/sign-out/")
        except:
            pass  # Ignore logout errors
        finally:
            self.authenticated = False
            self.csrf_token = None
            self.session.close()

    def __enter__(self):
        self.login()
        return self

    def __exit__(self, *args, **kwargs):
        self.logout()


def get_workspace_members():
    with PlaneAPIClient() as client:
        response = client.session.get(f"{client.base_url}/api/workspaces/tac/members/")
        members = response.json()
    for i in range(len(members)):
        if (
            "id" in members[i]
            and "member" in members[i]
            and "id" in members[i]["member"]
        ):
            del members[i]["id"]
    return members


def get_workspace_member_by_id(member_id: str):
    members = get_workspace_members()
    for m in members:
        if m["member"]["id"].lower() == member_id.lower():
            return m
    raise RuntimeError("Did not find a user with this ID")


def get_all_issues_of_project(project_uuid: str):
    base = mcp_configs.TAC_SERVICES["plane"]["url"].strip("/")
    resp = requests.get(
        f"{base}/api/v1/workspaces/tac/projects/{project_uuid}/issues/",
        headers={"x-api-key": mcp_configs.TAC_SERVICES["plane"]["token"]},
    )
    return resp.json()


def add_member_to_project(project_id: str, member_id: str, member_role: str):
    role_to_idx = {"admin": 20, "member": 15, "viewer": 10, "guest": 5}
    if member_role.lower() not in role_to_idx:
        raise ValueError("member role should be one of admin, member, viewer, guest")
    member_role = role_to_idx[member_role]

    payload = {"members": [{"member_id": member_id, "role": member_role}]}
    with PlaneAPIClient() as client:
        response = client.session.post(
            f"{client.base_url}/api/workspaces/tac/projects/{project_id}/members/",
            json=payload,
        )

        if response.status_code == 201:
            return response.json()
        response.raise_for_status()


def get_analytics_metric_summary():
    with PlaneAPIClient() as client:
        response = client.session.get(
            f"{client.base_url}/api/workspaces/tac/default-analytics/"
        )
        obj = response.json()
    metrics = dict()
    metrics["total tasks"] = obj["total_issues"]
    metrics["open tasks"] = obj["open_issues"]
    for item in obj["open_issues_classified"]:
        state = item["state_group"]
        count = item["state_count"]
        metrics[state + " tasks"] = count
    pending_cnt = 0
    unassigned_cnt = 0
    for item in obj["pending_issue_user"]:
        pending_cnt += item["count"]
        if item["assignees__id"] is None:
            unassigned_cnt += item["count"]
    metrics["unassigned issues"] = unassigned_cnt
    metrics["pending issues"] = pending_cnt

    return metrics


def delete_project(project_uuid: str):
    base = mcp_configs.TAC_SERVICES["plane"]["url"].strip("/")
    resp = requests.get(
        f"{base}/api/v1/workspaces/tac/projects/{project_uuid}/",
        headers={"x-api-key": mcp_configs.TAC_SERVICES["plane"]["token"]},
    )
    resp.raise_for_status()
    return resp.json()


def get_all_issues_in_workspace(
    due_date_order: str = "descending", topk: int | None = None
):
    url_params = "?"
    if due_date_order == "descending":
        url_params += "order_by=-target_date"
    elif due_date_order == "ascending":
        url_params += "order_by=target_date"
    else:
        raise ValueError('due_date_order should be one of "descending" or "ascending')

    if topk is not None:
        url_params += f"&per_page={topk}"

    with PlaneAPIClient() as client:
        url = f"{client.base_url}/api/workspaces/tac/issues/{url_params}"
        response = client.session.get(url)
    response.raise_for_status()
    res = response.json()
    if "results" in res:
        return res["results"]
    else:
        return res


def main():
    pass


if __name__ == "__main__":
    main()
