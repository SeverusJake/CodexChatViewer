# AGENTS.md

## Purpose

This repository contains a small local desktop app for browsing Codex session logs. Agents should optimize for clarity and low-risk edits. Most behavior is concentrated in a few files, and changes usually have visible UI impact.

## Fast Context

- Runtime entrypoint: `codex_chat_viewer.py`
- Packaging helper: `pyinstaller.py`
- Core package: `codex_viewer`
- Session source directory: `~/.codex/sessions`
- User config file: `~/.codex_chat_viewer_config.json`
- Main third-party dependency visible in source: `customtkinter`

## Code Map

### `codex_viewer/config.py`

Owns defaults, theme palettes, config persistence, and the sessions/config paths. Add new persisted settings here first.

### `codex_viewer/parser.py`

Owns `.jsonl` parsing. It extracts readable message text from `response_item` entries whose payload type is `message`. Update this file first if session schema or content extraction changes.

### `codex_viewer/ui/app.py`

Owns the main window and nearly all runtime behavior:

- session discovery and refresh
- parsed-file cache
- sidebar grouping and search
- chat selection and rendering
- inline formatting for markdown-like path links and code spans
- Windows Explorer integration
- chunked loading for long conversations

Most feature work lands here.

### `codex_viewer/ui/settings_dialog.py`

Owns user-editable settings. Changes to persisted preferences usually need coordinated updates here, in `config.py`, and in the main app.

## Working Rules

- Prefer minimal, targeted edits because the codebase is small and tightly coupled
- Do not change the sessions directory or config file locations unless the request explicitly requires it
- Treat `~/.codex/sessions` as external user data, not repo data
- Keep legacy config compatibility in mind when adding new settings
- Be careful with Windows-specific path behavior and Explorer launching

## High-Value Change Paths

- New parser behavior: update `parser.py`, then verify preview extraction and rendered message text still make sense
- New settings: update defaults, dialog controls, and application of the setting in the main UI
- Chat list behavior: update file discovery, grouping, or filtering in `ui/app.py`
- Message rendering behavior: update formatting logic and verify links, code spans, and aborted-token handling

## Verification Checklist

After code changes, prefer this manual validation sequence:

1. Launch with `python codex_chat_viewer.py`
2. Confirm the app opens even if the sessions folder is missing
3. Confirm real sessions load from `~/.codex/sessions`
4. Open at least one session and verify role-colored rendering
5. Test settings changes if any config-related behavior changed
6. Test Explorer opening if path-link behavior changed
7. Re-run `python pyinstaller.py` only when packaging behavior was intentionally changed

## Current Gaps

- No automated tests
- No dependency lockfile or requirements file
- No CI configuration
- Packaging is script-based rather than declarative
