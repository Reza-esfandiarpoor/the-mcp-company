import posixpath
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Annotated
from urllib.parse import quote, unquote
from uuid import uuid4

import requests
from fastmcp import FastMCP
from pydantic import Field
from webdav4.client import Client as WebDavClient

sys.path.append(Path(__file__).parent.as_posix())
import mcp_configs

webdav_client = WebDavClient(
    f"{mcp_configs.TAC_SERVICES['owncloud']['url'].strip('/')}/remote.php/webdav",
    auth=(
        mcp_configs.TAC_SERVICES["owncloud"]["username"],
        mcp_configs.TAC_SERVICES["owncloud"]["password"],
    ),
)

mcp = FastMCP("Owncloud Filesystem")


class OwnCloudShareError(Exception):
    pass


@mcp.tool
def create_public_share_link(
    path: Annotated[
        str,
        Field(
            description="The path of the file or folder in your ownCloud, e.g. '/Documents/report.pdf'"
        ),
    ],
):
    """Create a publicly accessible sharing link for a file/folder in ownCloud.

    Parameters
    ----------
    path : str
        The path of the file or folder in your ownCloud, e.g. "/Documents/report.pdf".

    Returns
    -------
    str
        The public URL for the created share.
    """
    base_url = mcp_configs.TAC_SERVICES["owncloud"]["url"].strip("/")
    username = mcp_configs.TAC_SERVICES["owncloud"]["username"]
    password = mcp_configs.TAC_SERVICES["owncloud"]["password"]
    password_protect = None
    expire_days = None
    permissions = "all"
    # Normalize permissions
    perm_map = {
        "read": 1,
        "update": 2,
        "create": 4,
        "delete": 8,
        "share": 16,
        "all": 31,
    }
    if isinstance(permissions, str):
        if permissions not in perm_map:
            raise ValueError(
                f'Unknown permissions "{permissions}". Use one of {list(perm_map.keys())} or an int bitmask.'
            )
        permissions_value = perm_map[permissions]
    elif isinstance(permissions, int) or permissions is None:
        permissions_value = 1 if permissions is None else permissions
    else:
        raise ValueError("permissions must be an int, a known string, or None.")

    # Build request
    endpoint = f"{base_url.rstrip('/')}/ocs/v1.php/apps/files_sharing/api/v1/shares"
    headers = {
        "OCS-APIREQUEST": "true",
        "Accept": "application/json",
    }
    data = {
        "path": path,
        "shareType": 3,  # 3 = public link
        "permissions": permissions_value,
    }

    if password_protect:
        data["password"] = password_protect

    if expire_days is not None and expire_days > 0:
        # ownCloud expects YYYY-MM-DD
        expire_date = (datetime.utcnow() + timedelta(days=expire_days)).strftime(
            "%Y-%m-%d"
        )
        data["expireDate"] = expire_date

    # Call API
    resp = requests.post(
        endpoint,
        headers=headers,
        data=data,
        auth=(username, password),
        timeout=30,
        verify=False,
    )

    # Network / HTTP errors
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Try to surface OCS error info if present
        try:
            j = resp.json()
            msg = j.get("ocs", {}).get("meta", {}).get("message", "")
            raise OwnCloudShareError(
                f"HTTP {resp.status_code}: {msg or resp.text}"
            ) from e
        except Exception:
            raise OwnCloudShareError(f"HTTP {resp.status_code}: {resp.text}") from e
    root = ET.fromstring(resp.content)
    url = root.find("./data/url").text
    url = url.replace("localhost:8092", "the-agent-company.com:8092")
    return url


@mcp.tool
def get_private_web_url(
    file_path: Annotated[
        str,
        Field(
            description="Path to the file relative to root, e.g. '/Documents/Data Analysis/28.xlsx'"
        ),
    ],
):
    """Return the ownCloud web UI 'private' URL for a given file path.

    Example output:
      http://localhost:8092/index.php/apps/files/?dir=/Documents/Data%20Analysis&fileid=178

    Returns
    -------
    str : constructed private UI URL
    """

    base_url = mcp_configs.TAC_SERVICES["owncloud"]["url"].strip("/")
    # Normalize and encode the WebDAV path
    clean_path = "/" + file_path.lstrip("/")
    dav_path = quote(unquote(clean_path))  # encodes spaces -> %20 etc., keeps slashes

    propfind_body = """<?xml version="1.0"?>
<d:propfind xmlns:d="DAV:" xmlns:oc="http://owncloud.org/ns">
  <d:prop>
    <oc:fileid/>
  </d:prop>
</d:propfind>
""".strip()
    url = f"{base_url.rstrip('/')}/remote.php/webdav{dav_path}"
    headers = {
        "Depth": "0",
        "Content-Type": "application/xml; charset=utf-8",
    }

    resp = requests.request(
        "PROPFIND",
        url,
        data=propfind_body.encode("utf-8"),
        headers=headers,
        auth=(
            mcp_configs.TAC_SERVICES["owncloud"]["username"],
            mcp_configs.TAC_SERVICES["owncloud"]["password"],
        ),
        verify=False,
        timeout=30,
    )

    if resp.status_code not in (200, 207):
        raise RuntimeError(f"PROPFIND failed ({resp.status_code}): {resp.text[:300]}")

    # Parse XML for oc:fileid
    try:
        ns = {"d": "DAV:", "oc": "http://owncloud.org/ns"}
        root = ET.fromstring(resp.content)
        fileid_el = root.find(".//oc:fileid", ns)
        if fileid_el is None or not fileid_el.text:
            raise RuntimeError("oc:fileid not found in response.")
        fileid = fileid_el.text.strip()
    except ET.ParseError as e:
        raise RuntimeError(f"Failed to parse WebDAV XML: {e}") from e

    # Build the UI URL. dir is the parent directory of the file
    dir_path = posixpath.dirname(clean_path) or "/"
    dir_param = quote(dir_path)  # encode spaces etc.

    private_url = (
        f"{base_url.rstrip('/')}/index.php/apps/files/?dir={dir_param}&fileid={fileid}"
    )
    return private_url


def _read_remote_file(path):
    with webdav_client.open(str(path), "r") as f:
        res = f.read()
    return res


def _write_to_remote_file(path, content):
    pardir, _ = str(path).rsplit("/", maxsplit=1)

    if pardir != "/" and pardir != "":
        print(pardir)
        if webdav_client.exists(str(pardir)):
            if not webdav_client.isdir(str(path)):
                raise RuntimeError("The given path is not valid.")
        else:
            webdav_client.mkdir(pardir)

    temp_dir = Path("./_webdav_temp_files")
    temp_dir.mkdir(exist_ok=True, parents=True)
    temp_file = temp_dir.joinpath(uuid4().hex)
    with open(temp_file, "w") as f:
        f.write(content)

    webdav_client.upload_file(
        from_path=temp_file.as_posix(), to_path=path, overwrite=True
    )
    temp_file.unlink()
    return


@mcp.tool
def remote_path_exists(
    path: Annotated[
        str, Field(description="the path to check if it exists on owncloud")
    ],
):
    """Check if the given path exists on owncloud.

    Returns True if the given path exists, otherwise returns False.
    """
    res = webdav_client.exists(str(path))
    return res


@mcp.tool
def create_remote_directory(
    path: Annotated[str, Field(description="the path to create")],
):
    """Create a directory with the given path on owncloud."""
    if webdav_client.exists(str(path)):
        if webdav_client.isdir(str(path)):
            return
        else:
            raise RuntimeError(
                "The given path exists on owncloud and is not a directory."
            )
    webdav_client.mkdir(str(path))


@mcp.tool
def remove_remote_path(
    path: Annotated[str, Field(description="path to remove on owncloud")],
):
    """Remove the directory or file with the given path on owncloud."""
    if not webdav_client.exists(str(path)):
        return

    webdav_client.remove(str(path))


@mcp.tool
def list_remote_directory(
    path: Annotated[str, Field(description="path to directory to list its content")],
    detail: Annotated[
        bool,
        Field(
            description="If detail = True, additional information is returned in a dictionary"
        ),
    ] = False,
):
    """List the files and directories in the given path on owncloud."""
    if not webdav_client.exists(str(path)):
        raise RuntimeError("The given directory does not exist.")
    if not webdav_client.isdir(str(path)):
        raise RuntimeError("The given path is not a directory")
    res = webdav_client.ls(path, True)
    if detail:
        return res
    else:
        res = [f"[{item['type']}] '{item['name']}'" for item in res]
        res = "\n".join(res)
    return res


@mcp.tool
def copy_remote_path(
    source: Annotated[str, Field(description="the source path on owncloud")],
    destination: Annotated[str, Field(description="the destination path on owncloud")],
):
    """Copy the content of the remote source path on owncloud to the remote destination path on
    owncloud."""
    if not webdav_client.exists(str(source)):
        raise RuntimeError("The given source path does not exist.")
    webdav_client.copy(from_path=source, to_path=destination, overwrite=True)


@mcp.tool
def move_remote_path(
    source: Annotated[str, Field(description="the source path on owncloud")],
    destination: Annotated[str, Field(description="the destination path on owncloud")],
    overwrite: Annotated[
        bool,
        Field(
            description="if overwrite = True, overwrite the content of the destination path if it exists"
        ),
    ] = True,
):
    """Move the content of the remote source path on owncloud to the remote destination path on
    owncloud."""
    if not webdav_client.exists(str(source)):
        raise RuntimeError("The given source path does not exist.")
    webdav_client.move(from_path=source, to_path=destination, overwrite=overwrite)


@mcp.tool
def recursive_path_search(
    pardir: Annotated[
        str, Field(description="The remote search directory on owncloud")
    ],
    name: Annotated[str | None, Field(description="The name to look for")] = None,
):
    """Search a path on owncloud recursively (Optionally) looking for ``name``.

    It recursively lists ``pardir`` on owncloud. If ``name`` is given, it filters the results and only keeps the ones that contain ``name``.

    Example:

        >> owncloud_recursive_path_search('/')
        ... ['/', '/Docs', '/Docs/file.xlsx', '/Photos', '/Photos/dog.png']

        >> owncloud_recursive_path_search('/', name='Docs')
        ... ['/Docs', '/Docs/file.xlsx']

    Returns:
        A list of paths, each being a string.
    """

    res = webdav_client.propfind(pardir, headers={"Depth": "infinity"})
    path_list = list()
    for item in res.responses.values():
        path_list.append(item.path.removeprefix("/remote.php/webdav"))
    if name is not None:
        path_list = [p for p in path_list if name.lower() in p.lower()]
    return path_list


@mcp.tool
def upload_file(
    local_filepath: Annotated[
        str, Field(description="Path to local file that should be uploaded to owncloud")
    ],
    remote_filepath: Annotated[
        str, Field(description="The remote destination path on owncloud")
    ],
):
    """Upload a local file at ``local_filepath`` to owncloud with ``remote_filepath`` path."""
    pass


@mcp.tool
def download_file(
    remote_filepath: Annotated[
        str, Field(description="Path to file on remote owncloud")
    ],
    local_filepath: Annotated[
        str, Field(description="Local path to download the file into")
    ],
):
    """Downloads the file at ``remote_filepath`` location on owncloud to ``local_filepath`` on
    local disk."""
    pass


if __name__ == "__main__":
    mcp.run(transport="sse", port=mcp_configs.ALL_SERVER_PORTS["owncloud"])
