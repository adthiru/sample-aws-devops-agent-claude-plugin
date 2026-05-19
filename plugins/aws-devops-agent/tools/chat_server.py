"""Local MCP server for AWS DevOps Agent chat.

Provides a single `send_message` tool that handles CreateChat + SendMessage +
EventStream parsing internally. Eliminates the need for the LLM to generate
raw call_boto3 Python or parse streaming responses.

Usage (via .mcp.json — handled automatically by the plugin):
    uv run --with "mcp[cli]" --with boto3 mcp run tools/chat_server.py
"""

from mcp.server.fastmcp import FastMCP
from botocore.config import Config
import boto3
import os

mcp = FastMCP("devops-agent-chat")

BOTO_CONFIG = Config(read_timeout=180, retries={"max_attempts": 1})


@mcp.tool()
def send_message(
    agent_space_id: str,
    content: str,
    execution_id: str = "",
    user_id: str = "",
    region: str = "us-east-1",
) -> dict:
    """Send a message to the AWS DevOps Agent and return the full response.

    Creates a new chat session if execution_id is omitted. Handles EventStream
    parsing internally — returns plain text, no raw stream handling needed.

    Use this tool for ALL conversational interactions with the DevOps Agent:
    cost optimization, architecture review, topology mapping, knowledge discovery,
    quick diagnostics, and follow-up questions.

    For investigations (create-backlog-task, get-backlog-task, list-journal-records),
    use aws___call_aws instead — those are simple request/response APIs.

    Args:
        agent_space_id: Target AgentSpace ID (from list-agent-spaces).
        content: Message to send. Include local context (IaC, git log, errors)
                 for better answers.
        execution_id: Reuse an existing chat session. Omit to create a new one.
                      The agent retains full context within a session.
        user_id: Operator identity. Defaults to $USER or "claude".
        region: AWS region where the AgentSpace lives. Defaults to us-east-1.

    Returns:
        dict with:
          - execution_id: Session ID for follow-up messages.
          - response: Fully assembled agent response text.
          - warning: Present only on partial/degraded responses (stream error,
                     timeout, or responseFailed event).
    """
    client = boto3.client("devops-agent", region_name=region, config=BOTO_CONFIG)
    user_id = user_id or os.environ.get("USER", "claude")
    warning = None

    # Create chat session if needed
    if not execution_id:
        try:
            chat = client.create_chat(
                agentSpaceId=agent_space_id, userId=user_id, userType="IAM"
            )
            execution_id = chat["executionId"]
        except Exception as e:
            return {
                "execution_id": "",
                "response": f"CreateChat failed: {e}",
                "warning": "chat_creation_failed",
            }

    # Send message and parse EventStream
    try:
        response = client.send_message(
            agentSpaceId=agent_space_id,
            executionId=execution_id,
            userId=user_id,
            content=content,
        )
    except Exception as e:
        return {
            "execution_id": execution_id,
            "response": f"SendMessage failed: {e}",
            "warning": "send_failed",
        }

    text = []
    block_type = None
    events_seen = 0
    try:
        for event in response["events"]:
            events_seen += 1
            if "contentBlockStart" in event:
                block_type = event["contentBlockStart"].get("type")
            elif "contentBlockDelta" in event:
                if block_type in (None, "text"):
                    delta = event["contentBlockDelta"].get("delta", {})
                    if "textDelta" in delta:
                        text.append(delta["textDelta"]["text"])
            elif "contentBlockStop" in event:
                block_type = None
            elif "responseFailed" in event:
                err = event["responseFailed"].get("errorMessage", "unknown error")
                warning = f"Agent error after {events_seen} events: {err}"
                break
    except Exception as e:
        # Partial stream — return whatever text was collected
        warning = f"Stream interrupted after {events_seen} events: {e}"

    result = {"execution_id": execution_id, "response": "".join(text)}
    if warning:
        result["warning"] = warning
    return result
