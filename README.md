# Codex Chat Viewer

Codex Chat Viewer is a small desktop app for browsing Codex session logs stored as `.jsonl` files under the local Codex sessions directory. It provides a two-pane reader with chat search, grouping, metadata display, message chunking for large sessions, and shortcuts for opening referenced project paths in Windows Explorer.

## What It Does

- Scans `~/.codex/sessions` recursively for session files
- Parses Codex `response_item` message entries from `.jsonl` logs
- Displays sessions in a searchable sidebar
- Renders user, assistant, developer, and system messages with distinct styling
- Detects bracketed file references and opens matching paths in Explorer
- Supports light/dark appearance, accent customization, and reading preferences
- Packages into a single Windows executable through PyInstaller

## Project Layout

```text
codex_chat_viewer.py         App launcher
pyinstaller.py              PyInstaller helper script
codex_viewer/config.py      App defaults, config persistence, path helpers
codex_viewer/parser.py      Session-file parsing and message extraction
codex_viewer/ui/app.py      Main window, session list, viewer rendering
codex_viewer/ui/settings_dialog.py
                            Settings UI and theme controls
```

## Requirements

The project now includes a minimal dependency manifest in `requirements.txt`. The current dependencies are:

- Python 3.x
- `customtkinter`
- `pytest` for tests

Install dependencies from the repository root:

```powershell
pip install -r requirements.txt
```

## Run Locally

Start the desktop app from the repository root:

```powershell
python codex_chat_viewer.py
```

On startup, the app reads session files from:

```text
~/.codex/sessions
```

User settings are stored in:

```text
~/.codex_chat_viewer_config.json
```

If the sessions folder does not exist, the app will open but show an empty-state message until a valid Codex sessions directory is present.

## Build an Executable

The repository includes a helper script that runs PyInstaller with the current packaging options:

```powershell
python pyinstaller.py
```

That script invokes PyInstaller in one-file, no-console mode and collects `customtkinter` data files. Build output is generated under the usual PyInstaller directories such as `build/` and `dist/`.

## Current Behavior Notes

- Session grouping can be switched between `none`, `month`, and `project`
- Chat list sorting supports `recent` and `name`
- Large chats are rendered in chunks, with a button to load older messages
- File and folder links embedded in rendered messages are normalized before Explorer is opened
- Metadata display is optional and controlled by app settings

## Known Gaps

The current repo is intentionally lightweight. It does not define:

- CI workflows
- release automation

For development notes and architecture details, see [docs/DEVELOPMENT.md](/H:/MyProjects/Python/CodexChatViewer/docs/DEVELOPMENT.md). For AI-agent orientation, see [AGENTS.md](/H:/MyProjects/Python/CodexChatViewer/AGENTS.md).
