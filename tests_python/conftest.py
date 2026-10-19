import sys

if sys.platform == "win32":
    import ctypes
    import msvcrt
    import os

    import _winapi

    # pytest swaps fd 0 for its capture, but the Windows stdin handle can keep pointing at the closed
    # original (or be missing in agent shells); subprocesses started without stdin= then fail with
    # WinError 6 while duplicating it. Point the handle at whatever fd 0 is now.
    try:
        _stdin = msvcrt.get_osfhandle(0)
    except OSError:
        _stdin = msvcrt.get_osfhandle(os.open(os.devnull, os.O_RDONLY))
    ctypes.windll.kernel32.SetStdHandle(_winapi.STD_INPUT_HANDLE, _stdin)
