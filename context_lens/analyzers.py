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


def _empty_transcript_result() -> dict:
    return {
        "turns": 0,
        "total_tokens": 0,
        "user_tokens": 0,
        "assistant_tokens": 0,
        "max_turn_tokens": 0,
        "max_turn_role": "",
        "assistant_user_ratio": 0.0,
    }


def _load_copilot_session(path: Path) -> dict | None:
    if path.suffix == ".json":
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                session_obj = json.load(handle)
            return session_obj if isinstance(session_obj, dict) else None
        except (json.JSONDecodeError, OSError):
            return None

    if path.suffix == ".jsonl":
        try:
            with path.open(encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(record, dict) and record.get("kind") == 0:
                        snapshot = record.get("v", {})
                        return snapshot if isinstance(snapshot, dict) else None
        except OSError:
            return None

    return None


def _copilot_user_text(req: dict) -> str:
    message = req.get("message", {})
    if isinstance(message, dict):
        text = message.get("text", "") or message.get("content", "")
        return text if isinstance(text, str) else ""
    if isinstance(message, str):
        return message
    return ""


def _copilot_response_part_text(resp: object) -> str:
    if isinstance(resp, str):
        return resp
    if not isinstance(resp, dict):
        return ""

    value = resp.get("value")
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_copilot_response_part_text(item) for item in value)

    message = resp.get("message")
    if isinstance(message, dict):
        text = message.get("text", "") or message.get("content", "")
        if isinstance(text, str):
            return text

    text = resp.get("text", "")
    return text if isinstance(text, str) else ""


def _copilot_assistant_text(response: object) -> str:
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        response = [response]
    if not isinstance(response, list):
        return ""

    parts: list[str] = []
    for resp in response:
        text = _copilot_response_part_text(resp)
        if text:
            parts.append(text)
    return "".join(parts)


def analyze_copilot_transcript(path: Path) -> dict:
    """Parse a Copilot Chat session (.json snapshot or .jsonl kind=0 snapshot)."""
    session_obj = _load_copilot_session(path)
    if not session_obj:
        return _empty_transcript_result()

    requests = session_obj.get("requests", [])
    if not isinstance(requests, list):
        return _empty_transcript_result()

    turns = 0
    total_tokens = 0
    user_tokens = 0
    assistant_tokens = 0
    max_turn_tokens = 0
    max_turn_role = ""

    for req in requests:
        if not isinstance(req, dict):
            continue

        user_text = _copilot_user_text(req)
        asst_text = _copilot_assistant_text(req.get("response", []))

        if not user_text and not asst_text:
            continue

        if user_text:
            t = count_tokens(user_text)
            turns += 1
            total_tokens += t
            user_tokens += t
            if t > max_turn_tokens:
                max_turn_tokens = t
                max_turn_role = "user"

        if asst_text:
            t = count_tokens(asst_text)
            turns += 1
            total_tokens += t
            assistant_tokens += t
            if t > max_turn_tokens:
                max_turn_tokens = t
                max_turn_role = "assistant"

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
