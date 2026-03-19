import json
from pathlib import Path


def safe_json_loads(line: str):
    try:
        return json.loads(line)
    except Exception:
        return None


def extract_text_from_content(content):
    parts = []

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()
        return ""

    if not isinstance(content, list):
        return ""

    for item in content:
        if isinstance(item, str) and item.strip():
            parts.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

    return "\n".join(parts).strip()


def parse_date_from_relative_path(relative_path: Path) -> str:
    parts = relative_path.parts
    if len(parts) >= 3:
        year, month, day = parts[0], parts[1], parts[2]
        if all(part.isdigit() for part in (year, month, day)):
            return f"{year}-{month}-{day}"
    return "Unknown Date"


def parse_codex_file(file_path: Path):
    messages = []
    first_user_line = None
    last_message_time = None
    meta = {
        "response_items": 0,
        "message_items": 0,
        "other_lines": 0,
    }

    with file_path.open("r", encoding="utf-8") as handle:
        for line_num, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue

            obj = safe_json_loads(line)
            if not obj:
                continue

            obj_type = obj.get("type")
            if obj_type == "response_item":
                meta["response_items"] += 1
            else:
                meta["other_lines"] += 1

            if obj_type != "response_item":
                continue

            payload = obj.get("payload", {})
            if payload.get("type") != "message":
                continue

            meta["message_items"] += 1

            role = payload.get("role", "unknown")
            content = payload.get("content", [])
            text = extract_text_from_content(content)
            if not text:
                continue

            timestamp = (
                obj.get("timestamp")
                or payload.get("timestamp")
                or obj.get("created_at")
                or payload.get("created_at")
            )

            messages.append(
                {
                    "role": role,
                    "text": text,
                    "line_num": line_num,
                    "timestamp": timestamp,
                }
            )

            if role == "user" and not first_user_line:
                first_user_line = text.splitlines()[0][:120]

            if timestamp:
                last_message_time = timestamp

    return messages, first_user_line, last_message_time, meta
