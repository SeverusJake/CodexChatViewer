import json
import re
from pathlib import Path


WRAPPER_LINE_PATTERN = re.compile(r"^<[^>]+>$")
WINDOWS_PATH_PATTERN = re.compile(r"[A-Za-z]:\\(?:[^\\\r\n]+\\)*[^\\\r\n]+")
PREVIEW_MESSAGE_LIMIT = 12


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




def normalize_preview_line(line: str) -> str:
    return re.sub(r"\s+", " ", line.strip())


def iter_preview_lines(text: str):
    for raw_line in text.splitlines():
        line = normalize_preview_line(raw_line)
        if not line:
            continue
        if WRAPPER_LINE_PATTERN.fullmatch(line):
            continue
        if line == "```":
            continue
        yield line


def choose_project_preview(candidates: list[str]) -> str | None:
    lines = []
    for text in candidates:
        lines.extend(iter_preview_lines(text))

    for line in lines:
        match = WINDOWS_PATH_PATTERN.search(line)
        if match:
            return match.group(0)[:120]

    keyword_lines = [
        line for line in lines
        if any(keyword in line.lower() for keyword in ("cwd", "workdir", "project", "repo"))
    ]
    if keyword_lines:
        return keyword_lines[0][:120]

    if lines:
        return lines[0][:120]
    return None

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
    preview_candidates = []
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

            if len(preview_candidates) < PREVIEW_MESSAGE_LIMIT:
                preview_candidates.append(text)

            messages.append(
                {
                    "role": role,
                    "text": text,
                    "line_num": line_num,
                    "timestamp": timestamp,
                }
            )

            if role == "user" and not first_user_line:
                first_user_line = choose_project_preview([text])

            if timestamp:
                last_message_time = timestamp

    preview = choose_project_preview(preview_candidates) or first_user_line
    return messages, preview, last_message_time, meta
