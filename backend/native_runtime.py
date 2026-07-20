from __future__ import annotations

import os
from pathlib import Path
import sys
import threading

_DLL_DIRECTORY_HANDLES: list[object] = []
_STDIO_HANDLES: list[object] = []


def configure_bundled_native_libraries() -> None:
    """Make PyInstaller-bundled WeasyPrint DLLs discoverable before import."""
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    native_dir = bundle_root / "weasyprint-native"
    if not native_dir.is_dir():
        return
    os.environ["PATH"] = f"{native_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    if hasattr(os, "add_dll_directory"):
        _DLL_DIRECTORY_HANDLES.append(os.add_dll_directory(native_dir))


def start_parent_process_watchdog() -> None:
    """Exit the frozen worker if its Tauri parent exits or crashes."""
    parent_value = os.getenv("SPED_PACKET_PARENT_PID", "").strip()
    if os.name != "nt" or not parent_value.isdigit():
        return
    import ctypes
    from ctypes import wintypes

    synchronize = 0x00100000
    infinite = 0xFFFFFFFF
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    handle = kernel32.OpenProcess(synchronize, False, int(parent_value))
    if not handle:
        return

    def watch() -> None:
        kernel32.WaitForSingleObject(handle, infinite)
        kernel32.CloseHandle(handle)
        os._exit(0)

    threading.Thread(target=watch, name="tauri-parent-watchdog", daemon=True).start()


def configure_frozen_stdio() -> None:
    """Preserve diagnostics for a windowed PyInstaller sidecar."""
    if not getattr(sys, "frozen", False):
        return
    log_value = os.getenv("SPED_PACKET_LOG_DIR", "").strip()
    if not log_value:
        return
    log_dir = Path(log_value)
    log_dir.mkdir(parents=True, exist_ok=True)
    stdout = (log_dir / "backend-sidecar.stdout.log").open("a", encoding="utf-8", buffering=1)
    stderr = (log_dir / "backend-sidecar.stderr.log").open("a", encoding="utf-8", buffering=1)
    _STDIO_HANDLES.extend((stdout, stderr))
    sys.stdout = stdout
    sys.stderr = stderr
