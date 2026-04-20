import sys
import logging
import json
import contextlib
from mcp.server.fastmcp import FastMCP

from src.integrations.servicenow import create_incident
from src.integrations.github import create_github_pull_request
from src.integrations.dynatrace.logger import log_error_to_dynatrace

# Initialize the MCP Server
mcp = FastMCP("Enterprise SRE Tools")

@mcp.tool()
def open_servicenow_incident(short_description: str, description: str, app_key: str) -> str:
    """Creates a high-priority incident in ServiceNow."""
    # We redirect stdout to stderr during tool execution to avoid corrupting the MCP JSON-RPC protocol
    with contextlib.redirect_stdout(sys.stderr):
        try:
            result = create_incident(short_description, description, app_key)
            inc_number = result.get('number', 'INC-ERROR')
            return json.dumps({"status": "success", "incident_id": inc_number})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def raise_github_pr(app_key: str, issue_title: str, rca_description: str, file_patches_json: str) -> str:
    """Automatically creates a branch and opens a Pull Request in GitHub for multiple files."""
    with contextlib.redirect_stdout(sys.stderr):
        try:
            patches = json.loads(file_patches_json)
            pr_url = create_github_pull_request(app_key, issue_title, rca_description, file_patches=patches)
            return json.dumps({"status": "success", "pr_url": pr_url})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

@mcp.tool()
def push_dynatrace_log(error_message: str, origin_id: str, app_name: str) -> str:
    """Pushes an error stack trace upstream to Dynatrace."""
    with contextlib.redirect_stdout(sys.stderr):
        try:
            log_error_to_dynatrace(error_message, origin_id, app_name)
            return json.dumps({"status": "success", "origin_id": origin_id})
        except Exception as e:
            return json.dumps({"status": "error", "message": str(e)})

if __name__ == "__main__":
    # MCP communicates over stdout/stdin. We should NOT redirect stdout globally.
    mcp.run()
