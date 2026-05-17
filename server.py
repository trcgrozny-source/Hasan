"""MCP server for Bitrix24 tasks via incoming webhook."""

import os
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

WEBHOOK_URL = os.environ.get("BITRIX24_WEBHOOK_URL", "").rstrip("/")

mcp = FastMCP("bitrix24-tasks")


def _call(method: str, params: dict | None = None) -> dict:
    """Call a Bitrix24 REST API method via webhook URL."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "BITRIX24_WEBHOOK_URL is not set. "
            "Add it to your .env file: https://your-domain.bitrix24.ru/rest/1/<token>/"
        )
    url = f"{WEBHOOK_URL}/{method}.json"
    with httpx.Client(timeout=30) as client:
        response = client.post(url, json=params or {})
        response.raise_for_status()
        data = response.json()
    if "error" in data:
        raise RuntimeError(f"Bitrix24 error [{data['error']}]: {data.get('error_description', '')}")
    return data.get("result", data)


# ── Task tools ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_tasks(
    responsible_id: int | None = None,
    created_by: int | None = None,
    status: int | None = None,
    group_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Return a list of tasks with optional filters.

    Args:
        responsible_id: Filter by assigned user ID.
        created_by: Filter by creator user ID.
        status: Task status: 1=new, 2=pending, 3=in-progress, 4=supposedly-completed,
                5=completed, 6=deferred, 7=declined.
        group_id: Filter by project/group ID.
        limit: Maximum number of tasks to return (default 50, max 50).
    """
    filter_: dict = {}
    if responsible_id is not None:
        filter_["RESPONSIBLE_ID"] = responsible_id
    if created_by is not None:
        filter_["CREATED_BY"] = created_by
    if status is not None:
        filter_["STATUS"] = status
    if group_id is not None:
        filter_["GROUP_ID"] = group_id

    params: dict = {
        "select": ["ID", "TITLE", "STATUS", "RESPONSIBLE_ID", "CREATED_BY",
                   "DEADLINE", "CREATED_DATE", "DESCRIPTION", "GROUP_ID"],
        "params": {"NAV_PARAMS": {"nPageSize": min(limit, 50), "iNumPage": 1}},
    }
    if filter_:
        params["filter"] = filter_

    result = _call("tasks.task.list", params)
    tasks = result.get("tasks", result) if isinstance(result, dict) else result
    return tasks


@mcp.tool()
def get_task(task_id: int) -> dict:
    """Return full details of a single task.

    Args:
        task_id: Numeric ID of the task.
    """
    result = _call("tasks.task.get", {"taskId": task_id})
    return result.get("task", result) if isinstance(result, dict) else result


@mcp.tool()
def create_task(
    title: str,
    responsible_id: int,
    description: str = "",
    deadline: str = "",
    priority: int = 1,
    group_id: int | None = None,
) -> dict:
    """Create a new task in Bitrix24.

    Args:
        title: Task title (required).
        responsible_id: User ID of the person responsible for the task (required).
        description: Task description (plain text or BB-code).
        deadline: Deadline in ISO 8601 format, e.g. "2025-12-31T18:00:00+03:00".
        priority: 0=low, 1=normal (default), 2=high.
        group_id: Project/group ID to attach the task to.
    """
    fields: dict = {
        "TITLE": title,
        "RESPONSIBLE_ID": responsible_id,
        "PRIORITY": priority,
    }
    if description:
        fields["DESCRIPTION"] = description
    if deadline:
        fields["DEADLINE"] = deadline
    if group_id is not None:
        fields["GROUP_ID"] = group_id

    result = _call("tasks.task.add", {"fields": fields})
    return result.get("task", result) if isinstance(result, dict) else result


@mcp.tool()
def update_task(task_id: int, fields: dict) -> dict:
    """Update fields of an existing task.

    Args:
        task_id: Numeric ID of the task to update.
        fields: Dictionary of fields to update. Common keys:
                TITLE, DESCRIPTION, DEADLINE, PRIORITY, RESPONSIBLE_ID, STATUS.
                STATUS values: 1=new, 2=pending, 3=in-progress, 4=supposedly-completed,
                5=completed, 6=deferred, 7=declined.
    """
    result = _call("tasks.task.update", {"taskId": task_id, "fields": fields})
    return result.get("task", result) if isinstance(result, dict) else result


@mcp.tool()
def complete_task(task_id: int) -> str:
    """Mark a task as completed.

    Args:
        task_id: Numeric ID of the task to complete.
    """
    _call("tasks.task.complete", {"taskId": task_id})
    return f"Task {task_id} marked as completed."


@mcp.tool()
def delete_task(task_id: int) -> str:
    """Delete a task permanently.

    Args:
        task_id: Numeric ID of the task to delete.
    """
    _call("tasks.task.delete", {"taskId": task_id})
    return f"Task {task_id} deleted."


# ── Comment tools ────────────────────────────────────────────────────────────

@mcp.tool()
def list_comments(task_id: int) -> list[dict]:
    """Return all comments for a task.

    Args:
        task_id: Numeric ID of the task.
    """
    result = _call("task.commentitem.getlist", {"TASKID": task_id})
    return result if isinstance(result, list) else result.get("comments", [])


@mcp.tool()
def add_comment(task_id: int, text: str) -> dict:
    """Add a comment to a task.

    Args:
        task_id: Numeric ID of the task.
        text: Comment text (plain text or BB-code).
    """
    result = _call(
        "task.commentitem.add",
        {"TASKID": task_id, "FIELDS": {"POST_MESSAGE": text}},
    )
    return {"comment_id": result} if not isinstance(result, dict) else result


# ── User helper ──────────────────────────────────────────────────────────────

@mcp.tool()
def list_users(name_filter: str = "") -> list[dict]:
    """Return portal users (to look up IDs for task assignment).

    Args:
        name_filter: Optional partial name to filter results.
    """
    params: dict = {"select": ["ID", "NAME", "LAST_NAME", "EMAIL", "WORK_POSITION"]}
    if name_filter:
        params["filter"] = {"%NAME": name_filter}
    result = _call("user.get", params)
    return result if isinstance(result, list) else []


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
