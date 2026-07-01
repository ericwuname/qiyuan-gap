# -*- coding: utf-8 -*-
"""Cross-process file lock using msvcrt or portalocker."""

import io, os, time

try:
    import msvcrt
    _HAS_MSVCRT = True
except ImportError:
    _HAS_MSVCRT = False

try:
    import portalocker
    _HAS_PORTALOCKER = True
except ImportError:
    _HAS_PORTALOCKER = False

if not _HAS_MSVCRT and not _HAS_PORTALOCKER:
    import warnings
    warnings.warn("file_lock: no msvcrt/portalocker, locking is no-op")


def acquire_lock(filepath, timeout=10.0):
    """Acquire exclusive file lock. Returns file handle."""
    parent = os.path.dirname(filepath)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    if not os.path.isfile(filepath):
        with io.open(filepath, "w", encoding="utf-8") as f:
            pass
    fh = open(filepath, "rb+")
    deadline = time.time() + timeout
    if _HAS_PORTALOCKER:
        while True:
            try:
                portalocker.lock(fh, portalocker.LOCK_EX | portalocker.LOCK_NB)
                return fh
            except portalocker.exceptions.LockException:
                if time.time() > deadline:
                    fh.close()
                    raise TimeoutError("lock timeout: " + filepath)
                time.sleep(0.01)
    elif _HAS_MSVCRT:
        while True:
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
                return fh
            except IOError:
                if time.time() > deadline:
                    fh.close()
                    raise TimeoutError("lock timeout: " + filepath)
                time.sleep(0.01)
    else:
        return fh


def release_lock(fh):
    """Release lock and close file handle."""
    try:
        if _HAS_PORTALOCKER:
            portalocker.unlock(fh)
        elif _HAS_MSVCRT:
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
    except Exception:
        pass
    finally:
        try:
            fh.close()
        except Exception:
            pass


class FileLock:
    """Cross-process file lock context manager."""

    def __init__(self, filepath, timeout=10.0):
        self.filepath = filepath
        self.timeout = timeout
        self._fh = None

    def __enter__(self):
        self._fh = acquire_lock(self.filepath, self.timeout)
        return self._fh

    def __exit__(self, *args):
        if self._fh is not None:
            release_lock(self._fh)
            self._fh = None
        return False


__all__ = ["FileLock", "acquire_lock", "release_lock"]