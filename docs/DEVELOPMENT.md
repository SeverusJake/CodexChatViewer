# Development Guide

## Overview

Codex Chat Viewer is a local Python desktop application built with `tkinter` and `customtkinter`. Its job is narrow: discover Codex session logs, parse readable message content from those logs, and render the result in a UI optimized for fast browsing.

The codebase is small and organized by responsibility rather than layers or packages. Most changes will fall into one of four areas: config, parsing, main UI behavior, or settings.

## Architecture

### Entry and Packaging

- `codex_chat_viewer.py` is the only runtime launcher. It imports `main()` from the UI module and starts the app.
- `pyinstaller.py` is a helper script for producing a Windows executable with PyInstaller.

### Configuration

`codex_viewer/config.py` owns:

- application title and window defaults
- the default theme palette for dark and light modes
- config file persistence at `~/.codex_chat_viewer_config.json`
- the Codex sessions root at `~/.codex/sessions`
- merging saved user config over the app defaults

If you add a new persisted setting, this is the first file to update. Keep defaults in `DEFAULT_CONFIG`, ensure `load_config()` can merge older saved files safely, and make sure the UI can handle missing keys from legacy configs.

### Parsing

`codex_viewer/parser.py` is responsible for:

- loading `.jsonl` session files line by line
- reading only `response_item` records
- filtering to payloads whose type is `message`
- extracting text from several content shapes
- returning parsed messages plus lightweight metadata

Important parser assumptions:

- unreadable lines are skipped quietly
- only text-like message content is rendered
- the first user line is used as a lightweight preview source
- date labels are inferred from the relative path structure `year/month/day/...`

If Codex session schema changes, this module is the boundary to update first.

### Main UI

`codex_viewer/ui/app.py` contains almost all user-facing behavior:

- app startup and window composition
- sidebar search, grouping, selection, and refresh
- parsed-file caching keyed by file path, mtime, and size
- chat rendering with per-role styling
- inline formatting for code spans, bracket links, and angle-bracket tokens
- project-folder detection and Explorer integration
- chunked loading for long conversations

The UI is stateful and event-driven. Most visible behavior changes, especially around list rendering or message display, will happen here.

### Settings UI

`codex_viewer/ui/settings_dialog.py` manages editable settings such as:

- appearance mode
- accent and advanced theme colors
- density
- font family and size
- refresh timing
- sorting defaults
- metadata visibility

When adding a setting:

1. Add a default in `config.py`
2. Surface it in the settings dialog if it is user-editable
3. Apply it in `ui/app.py`
4. Verify older configs still load without errors

## Data Flow

The main runtime flow is:

1. Resolve the sessions directory from `config.py`
2. Discover `*.jsonl` files recursively
3. Parse each file through `parse_codex_file()`
4. Build lightweight sidebar items from parsed preview data and file metadata
5. Cache parsed results until file size or mtime changes
6. Render the selected chat into the main text viewer

The app polls periodically when auto-refresh is enabled. Refresh affects the session list first, then reloads the selected chat only if its signature changed.

## Manual Development Workflow

## Setup

- Use Python 3.x
- Install `customtkinter`
- Start the app with `python codex_chat_viewer.py`
- Use real session logs under `~/.codex/sessions` to validate behavior

The project does not currently define a formal environment manager, dependency lockfile, or test runner.

## How To Validate Changes

For parser or UI work, manual testing is the primary verification path:

- launch the app successfully
- confirm the chat list loads from the expected sessions directory
- select a session and verify role labels and message content render correctly
- test search and grouping behavior
- toggle theme and open settings to confirm config persistence still works
- use a message containing a bracketed path and verify Explorer opens correctly on Windows
- test a large conversation and confirm older-message loading still works

## Platform Notes

- The app contains Windows-specific behavior through `explorer` and `os.startfile()`
- Path normalization is intentionally defensive because rendered paths may contain whitespace, markdown formatting, or line/column suffixes
- The UI should still be readable without a sessions directory, but Explorer-related features are Windows-oriented

## Known Constraints

- No automated tests are present
- No dependency manifest is checked in
- No CI or release workflow is defined
- Packaging assumptions currently live in `pyinstaller.py`, not in a reusable build config

## Recommended Editing Strategy

- Parser bug or schema change: start in `codex_viewer/parser.py`
- Theme, layout, refresh, grouping, or rendering change: start in `codex_viewer/ui/app.py`
- User-editable preference change: update `config.py`, `settings_dialog.py`, and the affected UI behavior together
- Packaging change: update `pyinstaller.py` and then verify the app still launches from source
