import json
from pathlib import Path

from codex_viewer.parser import parse_codex_file, parse_date_from_relative_path


def write_jsonl(path: Path, rows):
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_parse_codex_file_extracts_messages_and_preview(tmp_path):
    session_file = tmp_path / "session.jsonl"
    write_jsonl(
        session_file,
        [
            {
                "type": "response_item",
                "timestamp": "2026-03-20T01:00:00Z",
                "payload": {
                    "type": "message",
                    "role": "user",
                    "content": "First user line\nextra context",
                },
            },
            {
                "type": "response_item",
                "created_at": "2026-03-20T01:05:00Z",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": [{"text": "Assistant reply"}],
                },
            },
        ],
    )

    messages, preview, last_message_time, meta = parse_codex_file(session_file)

    assert [message["role"] for message in messages] == ["user", "assistant"]
    assert messages[0]["text"] == "First user line\nextra context"
    assert messages[1]["text"] == "Assistant reply"
    assert preview == "First user line"
    assert last_message_time == "2026-03-20T01:05:00Z"
    assert meta == {"response_items": 2, "message_items": 2, "other_lines": 0}


def test_parse_codex_file_ignores_invalid_non_message_and_empty_content(tmp_path):
    session_file = tmp_path / "session.jsonl"
    session_file.write_text(
        "\n".join(
            [
                "{not valid json}",
                json.dumps({"type": "other_type", "payload": {"type": "message"}}),
                json.dumps({"type": "response_item", "payload": {"type": "tool_call", "role": "assistant"}}),
                json.dumps({"type": "response_item", "payload": {"type": "message", "role": "assistant", "content": []}}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    messages, preview, last_message_time, meta = parse_codex_file(session_file)

    assert messages == []
    assert preview is None
    assert last_message_time is None
    assert meta == {"response_items": 2, "message_items": 1, "other_lines": 1}


def test_parse_codex_file_supports_string_dict_and_mixed_list_content(tmp_path):
    session_file = tmp_path / "session.jsonl"
    write_jsonl(
        session_file,
        [
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": "plain string"},
            },
            {
                "type": "response_item",
                "payload": {"type": "message", "role": "assistant", "content": {"text": "dict text"}},
            },
            {
                "type": "response_item",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "content": ["line one", {"text": "line two"}, {"not_text": "ignored"}, "line three"],
                },
            },
        ],
    )

    messages, _preview, _last_message_time, _meta = parse_codex_file(session_file)

    assert [message["text"] for message in messages] == [
        "plain string",
        "dict text",
        "line one\nline two\nline three",
    ]


def test_parse_codex_file_prefers_timestamp_then_payload_timestamp_then_created_at(tmp_path):
    session_file = tmp_path / "session.jsonl"
    write_jsonl(
        session_file,
        [
            {
                "type": "response_item",
                "timestamp": "top-level-timestamp",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "timestamp": "payload-timestamp",
                    "created_at": "payload-created-at",
                    "content": "message one",
                },
            },
            {
                "type": "response_item",
                "created_at": "top-level-created-at",
                "payload": {
                    "type": "message",
                    "role": "assistant",
                    "created_at": "payload-created-at-two",
                    "content": "message two",
                },
            },
        ],
    )

    messages, _preview, last_message_time, _meta = parse_codex_file(session_file)

    assert messages[0]["timestamp"] == "top-level-timestamp"
    assert messages[1]["timestamp"] == "top-level-created-at"
    assert last_message_time == "top-level-created-at"


def test_parse_date_from_relative_path_handles_expected_and_unknown_shapes():
    assert parse_date_from_relative_path(Path("2026/03/20/session.jsonl")) == "2026-03-20"
    assert parse_date_from_relative_path(Path("misc/session.jsonl")) == "Unknown Date"
