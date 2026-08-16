import sys
from ctypes import byref, c_uint32, windll, wintypes
from typing import cast


def enable_ansi() -> None:
        if sys.platform != "win32":
                return
        kernel32 = windll.kernel32

        get_handle = kernel32.GetStdHandle
        get_handle.argtypes = [wintypes.DWORD]
        get_handle.restype = wintypes.HANDLE

        get_mode = kernel32.GetConsoleMode
        get_mode.argtypes = [wintypes.HANDLE, wintypes.LPDWORD]
        get_mode.restype = wintypes.BOOL

        set_mode = kernel32.SetConsoleMode
        set_mode.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        set_mode.restype = wintypes.BOOL

        STD_OUTPUT_HANDLE = -11
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

        handle = cast(int, get_handle(STD_OUTPUT_HANDLE))
        mode = c_uint32()
        if not cast(int, get_mode(handle, byref(mode))):
                return
        _ = cast(int, set_mode(handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING))
