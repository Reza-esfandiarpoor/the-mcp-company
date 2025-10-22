FROM nikolaik/python-nodejs:python3.10-nodejs22-slim

WORKDIR /app
RUN pip install --no-cache-dir 'fastmcp==2.11.2' 'PyYAML==6.0.2' 'webdav4==0.10.0'

RUN mkdir -p data/api_specs
COPY data/api_specs/gitlab_api data/api_specs/gitlab_api
COPY data/api_specs/rocket_chat_openapi_specs /app/data/api_specs/rocket_chat_openapi_specs
COPY mcp_servers mcp_servers

ENV PYTHONUNBUFFERED=1

CMD ["bash"]

