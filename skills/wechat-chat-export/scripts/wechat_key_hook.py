#!/usr/bin/env python3
"""LLDB command for explicitly authorized WeChat 4.1.x key capture.

This module is imported by LLDB. It captures the 32-byte passphrase supplied
to CommonCrypto during login, derives per-database AES-256 keys, and accepts
them only after SQLCipher 4 page-one HMAC verification. Full secrets are never
printed; verified keys are written atomically to a local mode-0600 bundle.
"""

from __future__ import annotations

import glob
import hashlib
import hmac
import json
import os
import shlex
import struct
import sys
import tempfile
import time
from pathlib import Path


PAGE_SIZE = 4096
SALT_SIZE = 16
KEY_SIZE = 32
RESERVE_SIZE = 80
HMAC_SIZE = 64
KDF_ITERATIONS = 256_000
DEFAULT_ROOT = "~/Library/Containers/com.tencent.xinWeChat/Data/Documents/xwechat_files"
DEFAULT_OUTPUT = "~/.wechat-bridge/keys.json"


def _log(message: str) -> None:
    print(f"[wechat-key-capture] {message}", file=sys.stderr, flush=True)


def _emit(payload: dict[str, object]) -> None:
    print("WECHAT_KEY_STATUS " + json.dumps(payload, ensure_ascii=False), flush=True)


def verify_sqlcipher4_key(encryption_key: bytes, page_one: bytes) -> bool:
    """Verify a candidate key against a SQLCipher 4 first page."""
    if len(encryption_key) != KEY_SIZE or len(page_one) < PAGE_SIZE:
        return False
    salt = page_one[:SALT_SIZE]
    mac_salt = bytes(value ^ 0x3A for value in salt)
    mac_key = hashlib.pbkdf2_hmac("sha512", encryption_key, mac_salt, 2, dklen=KEY_SIZE)
    mac = hmac.new(mac_key, page_one[SALT_SIZE:PAGE_SIZE - RESERVE_SIZE + SALT_SIZE], hashlib.sha512)
    mac.update(struct.pack("<I", 1))
    return hmac.compare_digest(mac.digest(), page_one[PAGE_SIZE - HMAC_SIZE:PAGE_SIZE])


def derive_sqlcipher4_key(passphrase: bytes, page_one: bytes) -> bytes:
    """Derive the per-database SQLCipher 4 key used by WeChat 4.1.x."""
    if len(passphrase) != KEY_SIZE or len(page_one) < SALT_SIZE:
        raise ValueError("passphrase and database page are invalid")
    return hashlib.pbkdf2_hmac(
        "sha512",
        passphrase,
        page_one[:SALT_SIZE],
        KDF_ITERATIONS,
        dklen=KEY_SIZE,
    )


def encrypted_page_ones(root: str) -> dict[str, bytes]:
    """Read page one from encrypted SQLite-looking databases under root."""
    page_ones: dict[str, bytes] = {}
    expanded = os.path.realpath(os.path.expanduser(root))
    for database in glob.glob(os.path.join(expanded, "**", "*.db"), recursive=True):
        try:
            with open(database, "rb") as handle:
                page = handle.read(PAGE_SIZE)
        except OSError:
            continue
        if (
            len(page) >= PAGE_SIZE
            and not page.startswith(b"SQLite format 3")
            and page[:SALT_SIZE] != b"\x00" * SALT_SIZE
        ):
            page_ones[os.path.realpath(database)] = page
    return page_ones


def _account_for_database(database: str, root: str) -> str | None:
    try:
        relative = Path(database).resolve().relative_to(Path(root).expanduser().resolve())
    except ValueError:
        return None
    return relative.parts[0] if len(relative.parts) >= 2 else None


def ready_account(keys: dict[str, str], root: str) -> str | None:
    """Return one account whose contact and message databases both verified."""
    names_by_account: dict[str, set[str]] = {}
    for database in keys:
        account = _account_for_database(database, root)
        if account:
            names_by_account.setdefault(account, set()).add(Path(database).name.lower())
    for account, names in sorted(names_by_account.items()):
        if "contact.db" in names and any(name.startswith("message_") and name.endswith(".db") for name in names):
            return account
    return None


def write_key_bundle(keys: dict[str, str], destination: str = DEFAULT_OUTPUT) -> Path:
    """Write verified keys atomically without a world-readable permission window."""
    output = Path(destination).expanduser().resolve()
    output.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(output.parent, 0o700)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            descriptor = -1
            json.dump(
                {
                    "schemaVersion": 1,
                    "method": "lldb-commoncrypto-explicit-consent",
                    "keys": dict(sorted(keys.items())),
                },
                handle,
                ensure_ascii=False,
                indent=2,
            )
            handle.write("\n")
        os.replace(temporary, output)
        os.chmod(output, 0o600)
        sudo_uid = os.environ.get("SUDO_UID")
        sudo_gid = os.environ.get("SUDO_GID")
        if sudo_uid and sudo_gid:
            try:
                os.chown(output, int(sudo_uid), int(sudo_gid))
                os.chown(output.parent, int(sudo_uid), int(sudo_gid))
            except OSError:
                pass
        return output
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def _breakpoint_specs(machine: str) -> list[tuple[str, str, str, str, str]]:
    if machine == "arm64":
        return [
            # CCKeyDerivationPBKDF(alg, password, passwordLen, salt, saltLen,
            #                       prf, rounds, derivedKey, derivedKeyLen)
            ("CCKeyDerivationPBKDF", "x1", "x2", "x5", "x6"),
        ]
    return []


def _capture_impl(debugger, command: str) -> None:
    import lldb

    arguments = shlex.split(command or "")
    root = DEFAULT_ROOT
    output = DEFAULT_OUTPUT
    timeout = 180
    machine = "arm64"
    iterator = iter(arguments)
    for argument in iterator:
        if argument == "--root":
            root = next(iterator, root)
        elif argument == "--output":
            output = next(iterator, output)
        elif argument == "--timeout":
            timeout = int(next(iterator, str(timeout)))
        elif argument == "--machine":
            machine = next(iterator, machine)

    specs = _breakpoint_specs(machine)
    if not specs:
        _emit({"status": "unsupported", "reason": "key-capture-register-map-is-arm64-only"})
        return
    page_ones = encrypted_page_ones(root)
    if not page_ones:
        _emit({"status": "error", "reason": "no-encrypted-databases-found"})
        return

    target = debugger.GetSelectedTarget()
    process = target.GetProcess() if target else None
    if not process or not process.IsValid():
        _emit({"status": "error", "reason": "lldb-is-not-attached"})
        return

    register_map: dict[str, tuple[str, str, str, str]] = {}
    for function, passphrase_register, length_register, prf_register, rounds_register in specs:
        breakpoint = target.BreakpointCreateByName(function)
        locations = breakpoint.GetNumLocations() if breakpoint.IsValid() else 0
        if locations:
            register_map[function] = (passphrase_register, length_register, prf_register, rounds_register)
            _log(f"breakpoint ready: {function} ({locations} locations)")
    if not register_map:
        _emit({"status": "unsupported", "reason": "commoncrypto-breakpoints-not-found"})
        return

    verified: dict[str, str] = {}
    seen: set[bytes] = set()
    hits = 0
    started = time.time()
    _log(
        "Capture started. During the consented window, personally sign out and sign back in "
        f"using the debug copy of WeChat. Timeout: {timeout}s."
    )
    previous_async = debugger.GetAsync()
    debugger.SetAsync(True)
    try:
        process.Continue()
        while time.time() - started < timeout and not ready_account(verified, root):
            state = process.GetState()
            if state == lldb.eStateExited or not process.IsValid():
                break
            if state != lldb.eStateStopped:
                time.sleep(0.05)
                continue
            thread = process.GetSelectedThread()
            if thread and thread.GetStopReason() == lldb.eStopReasonBreakpoint:
                frame = thread.GetFrameAtIndex(0)
                function_name = frame.GetFunctionName() or ""
                registers = next((value for name, value in register_map.items() if name in function_name), None)
                if registers:
                    hits += 1
                    passphrase_register, length_register, prf_register, rounds_register = registers
                    length = frame.FindRegister(length_register).GetValueAsUnsigned()
                    prf = frame.FindRegister(prf_register).GetValueAsUnsigned()
                    rounds = frame.FindRegister(rounds_register).GetValueAsUnsigned()
                    if length == KEY_SIZE and prf == 5 and rounds == KDF_ITERATIONS:
                        address = frame.FindRegister(passphrase_register).GetValueAsUnsigned()
                        error = lldb.SBError()
                        candidate = process.ReadMemory(address, KEY_SIZE, error)
                        if error.Success() and candidate and candidate not in seen:
                            seen.add(candidate)
                            for database, page in page_ones.items():
                                derived_key = derive_sqlcipher4_key(candidate, page)
                                if database not in verified and verify_sqlcipher4_key(derived_key, page):
                                    verified[database] = derived_key.hex()
                                    _log(
                                        f"verified key for {Path(database).name}; "
                                        f"verified database count={len(verified)}"
                                    )
            if not ready_account(verified, root):
                process.Continue()
    finally:
        if process.IsValid() and process.GetState() == lldb.eStateRunning:
            process.Stop()
        if process.IsValid() and process.GetState() != lldb.eStateExited:
            detach_error = process.Detach()
            if detach_error and not detach_error.Success():
                _log("warning: LLDB did not confirm a clean detach")
        debugger.SetAsync(previous_async)

    if not verified:
        _emit(
            {
                "status": "no_match",
                "breakpointHits": hits,
                "candidateCount": len(seen),
                "fullKeysPrinted": False,
            }
        )
        return

    account = ready_account(verified, root)
    if not account:
        _emit(
            {
                "status": "partial",
                "matchedDatabaseCount": len(verified),
                "requiredDatabaseTypesCaptured": False,
                "keyBundleWritten": False,
                "fullKeysPrinted": False,
            }
        )
        return
    account_keys = {
        database: key
        for database, key in verified.items()
        if _account_for_database(database, root) == account
    }
    destination = write_key_bundle(account_keys, output)
    _emit(
        {
            "status": "ok",
            "matchedDatabaseCount": len(account_keys),
            "requiredDatabaseTypesCaptured": True,
            "keyBundle": str(destination),
            "fullKeysPrinted": False,
        }
    )


def capture_wechat_keys(debugger, command, result, internal_dict) -> None:
    try:
        _capture_impl(debugger, command)
    except Exception as exc:  # noqa: BLE001 - LLDB must return a structured local failure
        _emit({"status": "error", "reason": type(exc).__name__, "fullKeysPrinted": False})


def __lldb_init_module(debugger, internal_dict) -> None:
    debugger.HandleCommand(f"command script add -f {__name__}.capture_wechat_keys capture_wechat_keys")
