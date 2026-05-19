import json
import os
from pathlib import Path
from typing import Literal
from urllib.parse import unquote, urlparse

Tool = Literal["cursor", "claude_code", "copilot"]
SessionType = Literal["transcript", "terminal", "tools"]


def _cursor_root() -> Path:
    return Path.home() / ".cursor"


def _claude_root() -> Path:
    return Path.home() / ".claude"


def get_copilot_candidate_paths() -> list[Path]:
    """Return all possible VS Code workspaceStorage paths for Copilot chat sessions."""
    return [path for path, _ in _copilot_path_candidates()]


def _copilot_path_candidates() -> list[tuple[Path, str]]:
    """(workspaceStorage path, source_base label) in scan order."""
    home = Path.home()
    candidates: list[tuple[Path, str]] = [
        # macOS local
        (
            home / "Library/Application Support/Code/User/workspaceStorage",
            "vscode-local",
        ),
        (
            home
            / "Library/Application Support/Code - Insiders/User/workspaceStorage",
            "vscode-insiders",
        ),
        # Linux local
        (home / ".config/Code/User/workspaceStorage", "vscode-local"),
        (
            home / ".config/Code - Insiders/User/workspaceStorage",
            "vscode-insiders",
        ),
        # VS Code Server (remote/SSH)
        (
            home / ".vscode-server/data/User/workspaceStorage",
            "vscode-server",
        ),
        (
            home / ".vscode-server-insiders/data/User/workspaceStorage",
            "vscode-server",
        ),
    ]

    appdata = os.environ.get("APPDATA")
    if appdata:
        base = Path(appdata)
        candidates.append(
            (base / "Code/User/workspaceStorage", "vscode-local")
        )
        candidates.append(
            (base / "Code - Insiders/User/workspaceStorage", "vscode-insiders")
        )

    server_dir = os.environ.get("VSCODE_SERVER_DIR")
    if server_dir:
        candidates.append(
            (
                Path(server_dir) / "data/User/workspaceStorage",
                "vscode-server",
            )
        )

    return candidates


def _project_from_workspace_hash(hash_dir: Path) -> str:
    workspace_json = hash_dir / "workspace.json"
    if not workspace_json.is_file():
        return hash_dir.name
    try:
        data = json.loads(workspace_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return hash_dir.name

    folder = data.get("folder")
    if not isinstance(folder, str) or not folder:
        return hash_dir.name

    if folder.startswith("file://"):
        parsed = urlparse(folder)
        path_str = unquote(parsed.path)
        if path_str:
            name = Path(path_str.rstrip("/")).name
            if name:
                return name
    return hash_dir.name


def _scan_copilot_at_base(workspace_storage: Path, source_base: str) -> list[dict]:
    sessions: list[dict] = []
    if not workspace_storage.is_dir():
        return sessions

    for hash_dir in workspace_storage.iterdir():
        if not hash_dir.is_dir():
            continue
        chat_dir = hash_dir / "chatSessions"
        if not chat_dir.is_dir():
            continue
        project = _project_from_workspace_hash(hash_dir)
        for pattern in ("*.jsonl", "*.json"):
            for path in chat_dir.glob(pattern):
                if not path.is_file():
                    continue
                sessions.append(
                    {
                        "tool": "copilot",
                        "type": "transcript",
                        "project": project,
                        "path": path,
                        "source_base": source_base,
                    }
                )
    return sessions


def _scan_copilot_sessions() -> list[dict]:
    sessions: list[dict] = []
    seen_paths: set[Path] = set()

    for workspace_storage, source_base in _copilot_path_candidates():
        for entry in _scan_copilot_at_base(workspace_storage, source_base):
            resolved = entry["path"].resolve()
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            sessions.append(entry)

    return sessions


def _scan_cursor_transcripts(root: Path) -> list[dict]:
    sessions: list[dict] = []
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        transcripts_dir = project_dir / "agent-transcripts"
        if not transcripts_dir.is_dir():
            continue
        for session_dir in transcripts_dir.iterdir():
            if not session_dir.is_dir():
                continue
            for path in session_dir.glob("*.jsonl"):
                sessions.append(
                    {
                        "tool": "cursor",
                        "type": "transcript",
                        "project": project_dir.name,
                        "path": path,
                    }
                )
    return sessions


def _scan_cursor_terminals(root: Path) -> list[dict]:
    sessions: list[dict] = []
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        terminals_dir = project_dir / "terminals"
        if not terminals_dir.is_dir():
            continue
        for path in terminals_dir.glob("*.txt"):
            sessions.append(
                {
                    "tool": "cursor",
                    "type": "terminal",
                    "project": project_dir.name,
                    "path": path,
                }
            )
    return sessions


def _scan_cursor_tools(root: Path) -> list[dict]:
    sessions: list[dict] = []
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        tools_dir = project_dir / "agent-tools"
        if not tools_dir.is_dir():
            continue
        for path in tools_dir.glob("*.txt"):
            sessions.append(
                {
                    "tool": "cursor",
                    "type": "tools",
                    "project": project_dir.name,
                    "path": path,
                }
            )
    return sessions


def _scan_claude_transcripts(root: Path) -> list[dict]:
    sessions: list[dict] = []
    projects_dir = root / "projects"
    if not projects_dir.is_dir():
        return sessions

    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue
        for path in project_dir.glob("*.jsonl"):
            sessions.append(
                {
                    "tool": "claude_code",
                    "type": "transcript",
                    "project": project_dir.name,
                    "path": path,
                }
            )
    return sessions


def find_all_sessions() -> list[dict]:
    """Find all local session files for Cursor, Claude Code, and Copilot Chat."""
    sessions: list[dict] = []

    cursor_root = _cursor_root()
    if cursor_root.is_dir():
        sessions.extend(_scan_cursor_transcripts(cursor_root))
        sessions.extend(_scan_cursor_terminals(cursor_root))
        sessions.extend(_scan_cursor_tools(cursor_root))

    claude_root = _claude_root()
    if claude_root.is_dir():
        sessions.extend(_scan_claude_transcripts(claude_root))

    sessions.extend(_scan_copilot_sessions())

    return sessions
