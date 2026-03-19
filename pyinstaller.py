import subprocess

command = [
    "pyinstaller",
    "--noconsole",
    "--onefile",
    "--collect-data",
    "customtkinter",
    "--name",
    "CodexChatViewer",
    "codex_chat_viewer.py",
]

subprocess.run(command)
