FROM python:3.12-alpine

WORKDIR /app

# Install curl, git and uv
RUN apk add --no-cache curl git && \
    pip install --upgrade pip && \
    pip install uv

# Copy all files into the container
COPY . /app

# Use uv to install the package
RUN uv sync

# Set default command to run the MCP server
CMD ["uv", "run", "src/gitingest_mcp/server.py"]