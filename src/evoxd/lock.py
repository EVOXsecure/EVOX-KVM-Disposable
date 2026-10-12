"""Exklusive Sperre über flock (T9)."""
import fcntl
import os
import time
from contextlib import contextmanager
from pathlib import Path

from .errors import LockBusy


@contextmanager
def exclusive(path: Path, timeout: float = 30.0):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise LockBusy("Another EVOX operation is still running.") from None
                time.sleep(0.1)
        yield
    finally:
        os.close(fd)  # gibt die Sperre frei
