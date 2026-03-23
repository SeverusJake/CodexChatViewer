from codex_viewer.config import normalize_config_values
from codex_viewer.ui.app import replace_project_root


def test_normalize_config_values_filters_invalid_chat_project_remaps():
    config = normalize_config_values({
        "appearance_mode": "dark",
        "density": "balanced",
        "sort_mode": "recent",
        "group_mode": "none",
        "chat_project_remaps": {
            "2026/03/20/chat.jsonl": "D:/Projects/CodexChatViewer",
            "bad-empty": "",
            42: "D:/ignored",
            "bad-value": 123,
        },
    })

    assert config["chat_project_remaps"] == {
        "2026/03/20/chat.jsonl": "D:/Projects/CodexChatViewer"
    }


def test_replace_project_root_rewrites_exact_and_child_paths():
    original_root = r"H:\OldProjects\CodexChatViewer"
    new_root = r"D:\Work\CodexChatViewer"

    assert replace_project_root(original_root, original_root, new_root) == new_root
    assert replace_project_root(
        r"H:\OldProjects\CodexChatViewer\codex_viewer\ui\app.py",
        original_root,
        new_root,
    ) == r"D:\Work\CodexChatViewer\codex_viewer\ui\app.py"


def test_replace_project_root_leaves_unmatched_paths_unchanged():
    original_root = r"H:\OldProjects\CodexChatViewer"
    new_root = r"D:\Work\CodexChatViewer"
    other_path = r"C:\SomewhereElse\notes.txt"

    assert replace_project_root(other_path, original_root, new_root) == other_path
