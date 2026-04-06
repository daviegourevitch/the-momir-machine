from __future__ import annotations

import errno
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

if sys.platform == "win32":
    import msvcrt
else:
    import fcntl


def _default_lock_path() -> str:
    env_path = os.environ.get("MOMIR_RUNTIME_LOCK", "").strip()
    if env_path:
        return env_path
    if sys.platform == "win32":
        return str(Path(os.environ.get("TEMP", ".")) / "momir-runtime.lock")
    return "/tmp/momir-runtime.lock"


@dataclass
class RuntimeLock:
    path: str = _default_lock_path()
    _fh: Optional[object] = None
    _locked: bool = False

    def _ensure_parent_dir(self) -> None:
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)

    def acquire(self, blocking: bool = False) -> bool:
        if self._locked:
            return True
        self._ensure_parent_dir()
        self._fh = open(self.path, "a+", encoding="utf-8")
        try:
            if sys.platform == "win32":
                mode = msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK
                try:
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), mode, 1)
                except OSError:
                    self._fh.close()
                    self._fh = None
                    return False
            else:
                flags = fcntl.LOCK_EX
                if not blocking:
                    flags |= fcntl.LOCK_NB
                fcntl.flock(self._fh.fileno(), flags)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                self._fh.close()
                self._fh = None
                return False
            self._fh.close()
            self._fh = None
            raise
        self._locked = True
        return True

    def release(self) -> None:
        if not self._fh:
            self._locked = False
            return
        try:
            if self._locked:
                if sys.platform == "win32":
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None
            self._locked = False

    @property
    def is_held(self) -> bool:
        return self._locked

    def __enter__(self) -> "RuntimeLock":
        if not self.acquire(blocking=False):
            raise RuntimeError("Unable to acquire runtime lock")
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self.release()


def is_momir_running(lock_path: Optional[str] = None) -> bool:
    probe = RuntimeLock(path=lock_path or _default_lock_path())
    acquired = probe.acquire(blocking=False)
    if acquired:
        probe.release()
        return False
    return True
