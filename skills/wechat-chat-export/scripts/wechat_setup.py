#!/usr/bin/env python3
"""Risk-gated, zero-to-one setup guidance for local WeChat chat export.

Read-only checks and command generation are the default. Preparing a debug app
copy is available only with both --execute and an exact risk acknowledgement.
The script never runs LLDB or sudo; it prints the reviewed capture command for
the user to execute personally after reading the warnings.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shlex
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
import wechat_export  # noqa: E402


ACKNOWLEDGEMENT = "I_ACCEPT_WECHAT_ACCOUNT_AND_PRIVACY_RISKS"
OFFICIAL_APP = Path("/Applications/WeChat.app")
DEBUG_ROOT = Path("~/.wechat-chat-export").expanduser()
DEBUG_APP = DEBUG_ROOT / "WeChat-debug.app"
DATA_ROOT = Path("~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files").expanduser()
KEY_BUNDLE = Path("~/.wechat-bridge/keys.json").expanduser()
HOOK_SCRIPT = SCRIPT_DIR / "wechat_key_hook.py"

RISKS = [
    "This is a high-risk, unsupported debugging workflow; do not try it unless the export is necessary and authorized.",
    "Attaching LLDB and intercepting cryptographic calls may trigger WeChat account restrictions.",
    "The ad-hoc signed debug copy does not retain the official app's integrity guarantees.",
    "A captured database key can unlock broad private chat history and must remain local and mode 0600.",
    "Group records contain other people's personal information; export only with a lawful, authorized purpose.",
    "The method is version-specific and can stop working after WeChat or macOS changes.",
]


class SetupError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def _print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _tool_status() -> dict[str, bool]:
    return {name: shutil.which(name) is not None for name in ("ditto", "codesign", "lldb", "open", "ps")}


def _account_count() -> int:
    if not DATA_ROOT.is_dir():
        return 0
    return sum(path.is_dir() and (path / "db_storage").is_dir() for path in DATA_ROOT.iterdir())


def setup_check() -> dict[str, Any]:
    export_readiness = wechat_export.doctor(None)
    machine = platform.machine()
    tools = _tool_status()
    wechat_version = export_readiness["platform"].get("wechatVersion")
    reviewed_version = isinstance(wechat_version, str) and wechat_version.startswith("4.1.")
    prerequisites_ready = (
        sys.platform == "darwin"
        and machine == "arm64"
        and OFFICIAL_APP.is_dir()
        and DATA_ROOT.is_dir()
        and reviewed_version
        and all(tools.values())
    )
    if export_readiness["status"] == "ready":
        status = "ready_to_export"
        next_action = "Run wechat_export.py list-chats, then export. Do not capture keys again."
    elif prerequisites_ready:
        status = "manual_risk_setup_available"
        next_action = "Read the risks, inspect the dry-run prepare plan, and decide whether to proceed personally."
    else:
        status = "unsupported_or_incomplete_environment"
        next_action = "Resolve the reported platform, architecture, app, data, or tool prerequisite."
    return {
        "status": status,
        "environment": {
            "macOS": sys.platform == "darwin",
            "architecture": machine,
            "wechatInstalled": OFFICIAL_APP.is_dir(),
            "wechatVersion": wechat_version,
            "reviewedWechatVersion": reviewed_version,
            "dataRootFound": DATA_ROOT.is_dir(),
            "accountCount": _account_count(),
            "tools": tools,
            "debugCopyExists": DEBUG_APP.is_dir(),
        },
        "exportReadiness": {
            "status": export_readiness["status"],
            "keyBundleFound": export_readiness["keyBundle"].get("found", False),
            "contactDecryptable": export_readiness["database"].get("contactDecryptable", False),
            "messageDecryptable": export_readiness["database"].get("messageDecryptable", False),
        },
        "risk": {
            "acknowledgementRequired": status == "manual_risk_setup_available",
            "acknowledgementPhrase": ACKNOWLEDGEMENT,
            "warnings": RISKS,
            "automaticCapture": False,
            "originalAppModified": False,
        },
        "nextAction": next_action,
    }


def _prepare_commands(debug_app: Path) -> list[list[str]]:
    return [
        ["mkdir", "-p", str(debug_app.parent)],
        ["chmod", "700", str(debug_app.parent)],
        ["ditto", str(OFFICIAL_APP), str(debug_app)],
        ["codesign", "--force", "--deep", "--sign", "-", str(debug_app)],
        ["codesign", "--verify", "--deep", "--strict", str(debug_app)],
    ]


def _validate_debug_location(debug_app: Path) -> None:
    root = DEBUG_ROOT.resolve()
    try:
        debug_app.resolve().relative_to(root)
    except ValueError as exc:
        raise SetupError("unsafe_debug_path", f"The debug copy must stay under {root}.") from exc
    if debug_app.suffix != ".app":
        raise SetupError("invalid_debug_path", "The debug copy destination must end in .app.")


def prepare_debug_copy(debug_app: Path, execute: bool, acknowledgement: str | None) -> dict[str, Any]:
    _validate_debug_location(debug_app)
    commands = _prepare_commands(debug_app)
    if not execute:
        return {
            "status": "dry_run",
            "willModifyOriginalApp": False,
            "willCreateDebugCopy": str(debug_app),
            "commands": [shlex.join(command) for command in commands],
            "riskAcknowledgementRequiredForExecution": ACKNOWLEDGEMENT,
            "warnings": RISKS,
        }
    if acknowledgement != ACKNOWLEDGEMENT:
        raise SetupError("risk_not_acknowledged", f"Pass --ack-risk {ACKNOWLEDGEMENT} only after reviewing every warning.")
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SetupError("unsupported_platform", "The reviewed capture path currently supports Apple Silicon macOS only.")
    if not OFFICIAL_APP.is_dir():
        raise SetupError("wechat_not_found", "The official WeChat app was not found.")
    missing_tools = [name for name, available in _tool_status().items() if not available]
    if missing_tools:
        raise SetupError("missing_tools", "Missing required local tools: " + ", ".join(missing_tools))
    if debug_app.exists():
        raise SetupError("debug_copy_exists", "The debug app copy already exists; inspect it instead of overwriting it.")
    debug_app.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(debug_app.parent, 0o700)
    subprocess.run(commands[2], check=True)
    subprocess.run(commands[3], check=True)
    subprocess.run(commands[4], check=True)
    return {
        "status": "debug_copy_ready",
        "debugApp": str(debug_app),
        "originalAppModified": False,
        "nextActions": [
            "Quit the official WeChat app yourself.",
            f"Launch the debug copy yourself: {shlex.join(['open', '-na', str(debug_app)])}",
            "Log in if required, then run capture-command to generate the reviewed LLDB command.",
            "After the manual LLDB command starts, sign out and sign back in yourself to trigger key derivation.",
        ],
        "warnings": RISKS,
    }


def _debug_processes(debug_app: Path) -> list[int]:
    _validate_debug_location(debug_app)
    binary = str((debug_app / "Contents/MacOS/WeChat").resolve())
    try:
        output = subprocess.run(["ps", "-axo", "pid=,command="], check=True, capture_output=True, text=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    result: list[int] = []
    for line in output.splitlines():
        fields = line.strip().split(maxsplit=1)
        if len(fields) == 2 and fields[1].split(maxsplit=1)[0] == binary:
            try:
                result.append(int(fields[0]))
            except ValueError:
                continue
    return result


def build_capture_command(pid: int, timeout: int, machine: str, output: Path = KEY_BUNDLE) -> list[str]:
    hook_command = "command script import " + shlex.quote(str(HOOK_SCRIPT))
    capture_command = shlex.join(
        [
            "capture_wechat_keys",
            "--root",
            str(DATA_ROOT),
            "--output",
            str(output),
            "--timeout",
            str(timeout),
            "--machine",
            machine,
        ]
    )
    return ["sudo", "lldb", "--batch", "-p", str(pid), "-o", hook_command, "-o", capture_command, "-o", "quit"]


def capture_command(debug_app: Path, pid: int | None, timeout: int) -> dict[str, Any]:
    _validate_debug_location(debug_app)
    processes = _debug_processes(debug_app)
    if pid is None:
        if len(processes) != 1:
            raise SetupError(
                "debug_process_not_unique",
                "Launch exactly one prepared debug copy, then retry or pass its PID explicitly.",
            )
        pid = processes[0]
    if pid not in processes:
        raise SetupError("pid_not_debug_copy", "Refusing to generate a command for a process outside the prepared debug copy.")
    command = build_capture_command(pid, timeout, platform.machine())
    return {
        "status": "manual_command_ready",
        "shellCommand": shlex.join(command),
        "runsAutomatically": False,
        "expectedOutput": str(KEY_BUNDLE),
        "manualTrigger": "While LLDB is waiting, sign out and sign back in using the debug copy. Opening chats alone is not sufficient.",
        "afterCapture": "Run wechat_export.py doctor. Continue only when contact and message databases are decryptable.",
        "warnings": RISKS,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Risk-gated setup for authorized local WeChat chat export.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="Read-only environment and export-readiness check")

    prepare = subparsers.add_parser("prepare", help="Dry-run or explicitly create an ad-hoc signed debug app copy")
    prepare.add_argument("--debug-app", type=Path, default=DEBUG_APP)
    prepare.add_argument("--execute", action="store_true", help="Create and sign the copy after exact risk acknowledgement")
    prepare.add_argument("--ack-risk", help="Exact acknowledgement phrase printed by check and dry-run")

    capture = subparsers.add_parser("capture-command", help="Print, but never execute, the reviewed sudo LLDB command")
    capture.add_argument("--debug-app", type=Path, default=DEBUG_APP)
    capture.add_argument("--pid", type=int, help="PID of the prepared debug copy")
    capture.add_argument("--timeout", type=int, default=180)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "check":
            _print(setup_check())
            return 0
        if args.command == "prepare":
            _print(prepare_debug_copy(args.debug_app.expanduser().resolve(), args.execute, args.ack_risk))
            return 0
        if args.command == "capture-command":
            if args.timeout < 30 or args.timeout > 600:
                raise SetupError("invalid_timeout", "Timeout must be between 30 and 600 seconds.")
            _print(capture_command(args.debug_app.expanduser().resolve(), args.pid, args.timeout))
            return 0
    except SetupError as exc:
        _print({"status": "error", "error": {"code": exc.code, "message": exc.message}})
        return 2
    except (OSError, subprocess.CalledProcessError) as exc:
        _print({"status": "error", "error": {"code": "setup_failed", "message": type(exc).__name__}})
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
