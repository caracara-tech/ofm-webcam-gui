"""Session logging: an in-memory history that is always on, plus an optional log file.

No Qt in here (like the rest of `core/`), so the command line and the GUI
share one implementation.

Design
- Every record goes to a bounded in-memory `LogHistory` (what the GUI's log
  viewer shows) and to a temporary file that holds the *whole* session. The
  temporary file is deleted when the program ends.
- Saving a log is optional and can be switched on and off while the program
  runs (`--save-log` on the command line, the "Save log to file" checkbox in
  the GUI). Switching it on creates the log file with the whole session so far
  and keeps writing to it; switching it off deletes that file again. Recording
  continues in the temporary file either way, so switching it back on creates
  a complete file once more.
- One verbosity (`--log-level`) governs the console, the history and the file.
  The viewer can filter further, but it can never show what was not captured.
- A console handler is only added when a console exists (the Windows
  executable is built windowed: there is no stderr to write to).
"""

from __future__ import annotations

import atexit
import logging
import os
import sys
import tempfile
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

LOG_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
HISTORY_LIMIT = 5000  # lines kept in memory (oldest dropped first)
LOG_FILE_PREFIX = "ofm-webcam-gui"
LEVEL_NAMES = ("DEBUG", "INFO", "WARNING", "ERROR")

logger = logging.getLogger(__name__)

_OWNED_ATTR = "_ofm_owned"  # marks handlers installed here, so configuring twice does not stack them


@dataclass(frozen=True)
class LogEntry:
    levelno: int
    text: str  # fully formatted, may span several lines (tracebacks)


Listener = Callable[[LogEntry], None]
PathLike = Union[str, os.PathLike]


class LogHistory(logging.Handler):
    """Keeps the last `limit` formatted records and notifies subscribers.

    Listeners are called from whichever thread logged, while the handler lock
    is held: they must be quick and must not log. (The GUI's listener only
    emits a Qt signal, which Qt queues over to the GUI thread.)
    """

    def __init__(self, limit: int = HISTORY_LIMIT) -> None:
        super().__init__()
        self._entries: deque[LogEntry] = deque(maxlen=limit)
        self._listeners: list[Listener] = []
        self.limit = limit

    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry = LogEntry(record.levelno, self.format(record))
        except Exception:
            self.handleError(record)
            return
        self._entries.append(entry)
        for listener in list(self._listeners):
            try:
                listener(entry)
            except Exception:
                pass  # a broken viewer must never break logging

    def entries(self) -> list[LogEntry]:
        self.acquire()
        try:
            return list(self._entries)
        finally:
            self.release()

    def subscribe(self, listener: Listener) -> list[LogEntry]:
        """Register `listener` for new entries and return the entries so far.

        Both happen under one lock, so nothing is missed or delivered twice
        between the snapshot and the first notification.
        """
        self.acquire()
        try:
            self._listeners.append(listener)
            return list(self._entries)
        finally:
            self.release()

    def is_subscribed(self, listener: Listener) -> bool:
        self.acquire()
        try:
            return listener in self._listeners
        finally:
            self.release()

    def unsubscribe(self, listener: Listener) -> None:
        self.acquire()
        try:
            if listener in self._listeners:
                self._listeners.remove(listener)
        finally:
            self.release()


def resolve_log_path(path: Optional[PathLike], default_dir: Path, now: Optional[datetime] = None) -> Path:
    """Turn what the user gave into a concrete log file path.

    - nothing                      -> `<default_dir>/ofm-webcam-gui_<timestamp>.log`
    - an existing folder, or text
      ending in a path separator   -> the same timestamped name inside that folder
    - anything else                -> used as the file path, as given

    `path` may be the raw text typed by the user: a `Path` would already have
    dropped the trailing separator that says "this is a folder".
    """
    stamp = (now or datetime.now()).strftime("%Y%m%d_%H%M%S")
    auto_name = f"{LOG_FILE_PREFIX}_{stamp}.log"
    if path is None:
        return default_dir / auto_name
    text = os.fspath(path)
    target = Path(text)
    if text.endswith(("/", "\\")) or target.is_dir():
        return target / auto_name
    return target


class LogSession:
    """The running log: the history, the optional file, and the console."""

    def __init__(
        self,
        level: int,
        history: LogHistory,
        default_dir: Path,
        temp_handler: Optional[logging.FileHandler] = None,
    ) -> None:
        self.level = level
        self.history = history
        self.default_dir = default_dir
        self._temp_handler = temp_handler  # records the whole session; None if no temp file could be made
        self._file_handler: Optional[logging.FileHandler] = None
        self._last_path: Optional[Path] = None
        self._lock = threading.Lock()

    @property
    def saving(self) -> bool:
        return self._file_handler is not None

    @property
    def file_path(self) -> Optional[Path]:
        """The file being written right now, or None."""
        return self._last_path if self.saving else None

    @property
    def last_path(self) -> Optional[Path]:
        """The file used most recently (kept after saving is switched off, so
        switching it back on continues the same file instead of making another)."""
        return self._last_path

    @property
    def folder(self) -> Path:
        """Where the log files are: the current file's folder, else the default one."""
        return self._last_path.parent if self._last_path is not None else self.default_dir

    def read_full_log(self) -> str:
        """The whole session so far: from the temporary file (unbounded) or,
        if there is none, from the in-memory history (its last lines)."""
        handler = self._temp_handler
        if handler is not None:
            handler.acquire()
            try:
                handler.flush()
                return Path(handler.baseFilename).read_text(encoding="utf-8")
            except OSError:
                pass
            finally:
                handler.release()
        return "".join(entry.text + "\n" for entry in self.history.entries())

    def start_saving(self, path: Optional[PathLike] = None) -> Path:
        """Create the log file with the whole session so far, keep writing to it,
        and return its path.

        Refuses (OSError) to touch a file that already exists, so switching
        saving off can always safely delete exactly what was created here. On
        any failure the session is left exactly as it was.
        """
        with self._lock:
            if self._file_handler is not None:
                return self._last_path  # type: ignore[return-value]
            target = resolve_log_path(path if path is not None else self._last_path, self.default_dir)
            target.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(target, mode="x", encoding="utf-8")  # "x": fail if it exists
            handler.setLevel(self.level)
            handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
            setattr(handler, _OWNED_ATTR, True)

            # Records are emitted under this handler's lock, so while we hold it
            # nothing can slip between "copy the backlog" and "start streaming".
            gate = self._temp_handler or self.history
            gate.acquire()
            try:
                handler.stream.write(self.read_full_log())
                handler.flush()
                logging.getLogger().addHandler(handler)
            except OSError:
                handler.close()
                target.unlink(missing_ok=True)
                raise
            finally:
                gate.release()
            self._file_handler = handler
            self._last_path = target
        logger.info("Saving the session log to %s", target)
        return target

    def stop_saving(self) -> None:
        """Stop writing and delete the log file. The session keeps being
        recorded in the temporary file, so saving can be switched on again."""
        with self._lock:
            handler = self._file_handler
            if handler is None:
                return
            self._file_handler = None
            logging.getLogger().removeHandler(handler)
            handler.close()
            path = Path(handler.baseFilename)
            try:
                path.unlink()
            except OSError as exc:
                logger.warning("Could not delete the log file %s: %s", path, exc)
                return
        logger.info("Deleted the log file %s; the session is still being recorded", path)

    def close(self) -> None:
        """End of the program: release the log file (kept, the user asked for it)
        and delete the temporary recording. Safe to call more than once."""
        with self._lock:
            if self._file_handler is not None:
                logging.getLogger().removeHandler(self._file_handler)
                self._file_handler.close()
                self._file_handler = None
            if self._temp_handler is not None:
                logging.getLogger().removeHandler(self._temp_handler)
                self._temp_handler.close()
                try:
                    Path(self._temp_handler.baseFilename).unlink()
                except OSError:
                    pass
                self._temp_handler = None


def _make_temp_handler(level: int, formatter: logging.Formatter) -> Optional[logging.FileHandler]:
    """The temporary file that records the whole session (None if none can be made)."""
    try:
        fd, name = tempfile.mkstemp(prefix=f"{LOG_FILE_PREFIX}_", suffix=".log")
        os.close(fd)
        handler = logging.FileHandler(name, mode="w", encoding="utf-8")
    except OSError as exc:
        print(f"Could not create a temporary log file: {exc}", file=sys.stderr if sys.stderr else None)
        return None
    handler.setLevel(level)
    handler.setFormatter(formatter)
    setattr(handler, _OWNED_ATTR, True)
    return handler


def configure_logging(
    level_name: str,
    default_dir: Path,
    save: bool = False,
    path: Optional[PathLike] = None,
) -> LogSession:
    """Install the handlers on the root logger and return the session.

    `save`/`path` mirror `--save-log`: the file is opened right away. A file
    that cannot be opened is reported in the log and the program carries on.
    """
    level = getattr(logging, level_name.upper())
    root = logging.getLogger()
    for handler in list(root.handlers):
        if getattr(handler, _OWNED_ATTR, False):
            root.removeHandler(handler)
            handler.close()
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    history = LogHistory()
    history.setLevel(level)
    history.setFormatter(formatter)
    setattr(history, _OWNED_ATTR, True)
    root.addHandler(history)

    if sys.stderr is not None:  # a windowed executable has no console
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(level)
        console.setFormatter(formatter)
        setattr(console, _OWNED_ATTR, True)
        root.addHandler(console)

    temp_handler = _make_temp_handler(level, formatter)
    if temp_handler is not None:
        root.addHandler(temp_handler)

    session = LogSession(level, history, default_dir, temp_handler)
    atexit.register(session.close)  # a crash must not leave the temporary file behind
    if save:
        try:
            session.start_saving(path)
        except OSError as exc:
            logger.error("Could not open the log file: %s", exc)
    return session


def install_excepthook() -> None:
    """Send uncaught exceptions (main thread and worker threads) to the log.

    Without this a crash in a windowed executable leaves no trace anywhere.
    The default hook still runs afterwards.
    """
    default_hook = sys.excepthook

    def _log_and_forward(exc_type, exc, tb) -> None:
        if not issubclass(exc_type, KeyboardInterrupt):
            logging.getLogger("uncaught").critical("Uncaught exception", exc_info=(exc_type, exc, tb))
        default_hook(exc_type, exc, tb)

    def _log_thread(args: threading.ExceptHookArgs) -> None:
        logging.getLogger("uncaught").critical(
            "Uncaught exception in thread %s", getattr(args.thread, "name", "?"),
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _log_and_forward
    threading.excepthook = _log_thread


def describe_environment() -> str:
    """One line for the top of every log: enough to reproduce a report."""
    return f"python {sys.version.split()[0]} | pid {os.getpid()} | {'frozen executable' if getattr(sys, 'frozen', False) else 'source'}"
