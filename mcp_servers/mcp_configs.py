TAC_SERVICES = {
    "gitlab": {
        "url": "http://localhost:8929",
        "token": "root-token",
    },
    "plane": {
        "url": "http://localhost:8091",
        "email": "agent@company.com",
        "password": "theagentcompany",
        "token": "plane_api_83f868352c6f490aba59b869ffdae1cf",
    },
    "rocketchat": {
        "url": "http://localhost:3000",
        "username": "theagentcompany",
        "password": "theagentcompany",
    },
    "owncloud": {
        "url": "http://localhost:8092",
        "username": "theagentcompany",
        "password": "theagentcompany",
    },
}

ALL_SERVER_PORTS = {
    "gateway": 7879,
    "proxy": 7878,
    "school": 51463,
    "calculator": 51464,
    "rocketchat": 51465,
    "owncloud": 51466,
    "gitlab_main": 51467,
    "azure": 51468,
    "plane_transport_proxy": 51469,
    "plane_main": 51470,
    "common_tools": 51471,
    "gitlab_openapi": 51472,
    "gitlab_transport_proxy": 51473,
}


# fmt: off
SERVER_CONFIGS = {
    "mcpServers": {
        "plane": {"transport": "sse", "url": f"http://localhost:{ALL_SERVER_PORTS['plane_main']}/sse"},
        "RocketChat": {"transport": "sse", "url": f"http://localhost:{ALL_SERVER_PORTS['rocketchat']}/sse"},
        "owncloud": {"transport": "sse", "url": f"http://localhost:{ALL_SERVER_PORTS['owncloud']}/sse"},
        "gitlab": {"transport": "sse", "url": f"http://localhost:{ALL_SERVER_PORTS['gitlab_main']}/sse"},
        "azure": {"transport": "sse", "url": f"http://localhost:{ALL_SERVER_PORTS['azure']}/sse"}
    }
}
# fmt: on
