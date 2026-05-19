import json
from pathlib import Path

_encoder = None


def _get_encoder():
    global _encoder
    if _encoder is None:
        import tiktoken

        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    if not text:
        return 0
    return len(_get_encoder().encode(text))


def _extract_text_from_message(message: dict) -> str:
    content = message.get("content", [])
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for block in content:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
        elif "text" in block:
            parts.append(str(block["text"]))
    return "\n".join(parts)


def _copilot_role(record: dict) -> str:
    role = record.get("role", "")
    if isinstance(role, str) and role:
        return role
    record_type = record.get("type", "")
    if record_type in ("user", "assistant", "system"):
        return record_type
    message = record.get("message")
    if isinstance(message, dict):
        msg_role = message.get("role", "")
        if isinstance(msg_role, str):
            return msg_role
    return ""


def _extract_copilot_text(record: dict) -> str:
    """Best-effort text extraction; Copilot JSONL schema varies by version."""
    content = record.get("content")
    if isinstance(content, str):
        return content

    message = record.get("message")
    if isinstance(message, dict):
        text = _extract_text_from_message(message)
        if text:
            return text
        if isinstance(message.get("content"), str):
            return message["content"]
        if isinstance(message.get("text"), str):
            return message["text"]

    for key in ("text", "body", "messageText"):
        val = record.get(key)
        if isinstance(val, str) and val:
            return val

    return ""


def analyze_copilot_transcript(path: Path) -> dict:
    """Parse a Copilot Chat JSONL transcript (defensive, schema-tolerant)."""
    turns = 0
    total_tokens = 0
    user_tokens = 0
    assistant_tokens = 0
    max_turn_tokens = 0
    max_turn_role = ""

    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(record, dict):
                continue

            role = _copilot_role(record)
            if role == "system":
                continue

            text = _extract_copilot_text(record)
            turn_tokens = count_tokens(text)
            if turn_tokens == 0 and not text:
                continue

            turns += 1
            total_tokens += turn_tokens

            if role == "user":
                user_tokens += turn_tokens
            elif role == "assistant":
                assistant_tokens += turn_tokens

            if turn_tokens > max_turn_tokens:
                max_turn_tokens = turn_tokens
                max_turn_role = role

    ratio = assistant_tokens / user_tokens if user_tokens > 0 else 0.0

    return {
        "turns": turns,
        "total_tokens": total_tokens,
        "user_tokens": user_tokens,
        "assistant_tokens": assistant_tokens,
        "max_turn_tokens": max_turn_tokens,
        "max_turn_role": max_turn_role,
        "assistant_user_ratio": ratio,
    }


def analyze_transcript(path: Path) -> dict:
    """Parse a JSONL transcript and return token usage statistics."""
    turns = 0
    total_tokens = 0
    user_tokens = 0
    assistant_tokens = 0
    max_turn_tokens = 0
    max_turn_role = ""

    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            message = record.get("message", {})
            if not isinstance(message, dict):
                continue

            role = record.get("role", "")
            if not role:
                record_type = record.get("type", "")
                if record_type in ("user", "assistant"):
                    role = record_type
                else:
                    role = message.get("role", "")

            text = _extract_text_from_message(message)
            turn_tokens = count_tokens(text)
            if turn_tokens == 0 and not text:
                continue

            turns += 1
            total_tokens += turn_tokens

            if role == "user":
                user_tokens += turn_tokens
            elif role == "assistant":
                assistant_tokens += turn_tokens

            if turn_tokens > max_turn_tokens:
                max_turn_tokens = turn_tokens
                max_turn_role = role

    ratio = assistant_tokens / user_tokens if user_tokens > 0 else 0.0

    return {
        "turns": turns,
        "total_tokens": total_tokens,
        "user_tokens": user_tokens,
        "assistant_tokens": assistant_tokens,
        "max_turn_tokens": max_turn_tokens,
        "max_turn_role": max_turn_role,
        "assistant_user_ratio": ratio,
    }


def analyze_terminal(path: Path) -> dict:
    """Count tokens in a plain text terminal or tool output file."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    total_tokens = count_tokens(text)
    file_size_kb = path.stat().st_size / 1024.0
    return {
        "total_tokens": total_tokens,
        "file_size_kb": round(file_size_kb, 2),
    }
