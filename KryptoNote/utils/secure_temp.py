import atexit
import ctypes
import errno
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from ctypes import wintypes
from pathlib import Path

if os.name == "nt":
    import msvcrt
else:
    import fcntl


METADATA_TEMP_WATCHDOG_ARG = "--kryptonote-metadata-temp-watchdog"

_DIRECTORY_PREFIX = "kryptonote-meta-"
_FILE_PREFIX = "media-"
_LOCK_FILENAME = ".active.lock"
_READY_FILENAME = ".watchdog-ready"
_SESSION_PATTERN = re.compile(
    rf"^{re.escape(_DIRECTORY_PREFIX)}(?P<pid>[1-9][0-9]*)-(?P<token>[0-9a-f]{{16}})$"
)
_WATCHDOG_READY_TIMEOUT_SECONDS = 5.0
_WATCHDOG_POLL_SECONDS = 0.25
_LEGACY_FILE_MIN_AGE_SECONDS = 24 * 60 * 60

_session_lock = threading.RLock()
_session_directory = None
_session_lock_handle = None


def _metadata_temp_root(temp_root=None):
    root = Path(temp_root or tempfile.gettempdir()).resolve()
    if not root.is_dir():
        raise OSError(f"Temporary directory is unavailable: {root}")
    return root


def _session_details(path):
    match = _SESSION_PATTERN.fullmatch(Path(path).name)
    if match is None:
        return None
    return int(match.group("pid")), match.group("token")


def _open_windows_process(pid):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    open_process = kernel32.OpenProcess
    open_process.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    open_process.restype = wintypes.HANDLE
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = open_process(0x00100000, False, int(pid))  # SYNCHRONIZE
    return kernel32, handle


def _process_is_running(pid):
    try:
        pid = int(pid)
    except (TypeError, ValueError, OverflowError):
        return False
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True

    if os.name == "nt":
        kernel32, handle = _open_windows_process(pid)
        if not handle:
            return ctypes.get_last_error() == 5  # ERROR_ACCESS_DENIED
        try:
            result = kernel32.WaitForSingleObject(handle, 0)
            return result == 0x00000102  # WAIT_TIMEOUT
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return exc.errno == errno.EPERM
    return True


def _validated_session_directory(path, *, temp_root=None, expected_pid=None):
    root = _metadata_temp_root(temp_root)
    candidate = Path(path)
    details = _session_details(candidate)
    if details is None or candidate.is_symlink():
        raise ValueError("Invalid metadata temporary directory")
    resolved = candidate.resolve(strict=False)
    if resolved.parent != root:
        raise ValueError("Metadata temporary directory escaped the temp root")
    if expected_pid is not None and details[0] != int(expected_pid):
        raise ValueError("Metadata temporary directory belongs to another process")
    return resolved


def _validated_temp_file(path, *, expected_pid=None):
    candidate = Path(path)
    if not candidate.name.startswith(_FILE_PREFIX):
        raise ValueError("Invalid metadata temporary filename")
    session = _validated_session_directory(
        candidate.parent,
        expected_pid=expected_pid,
    )
    resolved = candidate.resolve(strict=False)
    if resolved.parent != session:
        raise ValueError("Metadata temporary file escaped its session directory")
    return resolved


def _remove_tree(path, *, temp_root=None):
    try:
        directory = _validated_session_directory(path, temp_root=temp_root)
    except (OSError, ValueError):
        return False
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _try_lock_session(directory, *, create):
    lock_path = Path(directory) / _LOCK_FILENAME
    try:
        handle = open(lock_path, "a+b" if create else "r+b")
    except OSError:
        return None
    try:
        if handle.seek(0, os.SEEK_END) == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_session_lock(handle):
    if handle is None:
        return
    try:
        handle.seek(0)
        if os.name == "nt":
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except OSError:
        pass
    handle.close()


def cleanup_stale_metadata_temp_dirs(temp_root=None):
    """Remove plaintext metadata leftovers owned by processes that have exited."""

    root = _metadata_temp_root(temp_root)
    removed = 0
    try:
        entries = list(root.iterdir())
    except OSError:
        return 0

    now = time.time()
    for entry in entries:
        details = _session_details(entry)
        if details is not None:
            active_directory = _session_directory
            if (
                active_directory is not None
                and entry.resolve(strict=False) == active_directory
            ):
                continue
            lock_path = entry / _LOCK_FILENAME
            lock_handle = _try_lock_session(entry, create=False)
            if lock_path.exists() and lock_handle is None:
                continue
            _release_session_lock(lock_handle)
            if _remove_tree(entry, temp_root=root):
                removed += 1
            continue

        # Releases before 3.10.2 wrote flat kryptonote-meta-* files. Avoid
        # racing an older running process by cleaning only clearly stale ones.
        if not entry.name.startswith(_DIRECTORY_PREFIX) or not entry.is_file():
            continue
        try:
            if now - entry.stat().st_mtime < _LEGACY_FILE_MIN_AGE_SECONDS:
                continue
            entry.unlink()
            removed += 1
        except OSError:
            continue
    return removed


def _cleanup_current_session():
    global _session_directory, _session_lock_handle
    with _session_lock:
        directory = _session_directory
        lock_handle = _session_lock_handle
        _session_directory = None
        _session_lock_handle = None
    _release_session_lock(lock_handle)
    if directory is not None:
        _remove_tree(directory)


def metadata_temp_directory():
    """Return one private, process-scoped directory for plaintext parser files."""

    global _session_directory, _session_lock_handle
    with _session_lock:
        if _session_directory is not None and _session_directory.is_dir():
            return _session_directory

        root = _metadata_temp_root()
        cleanup_stale_metadata_temp_dirs(root)
        for _ in range(10):
            candidate = root / (
                f"{_DIRECTORY_PREFIX}{os.getpid()}-{secrets.token_hex(8)}"
            )
            try:
                candidate.mkdir(mode=0o700)
            except FileExistsError:
                continue
            try:
                candidate.chmod(0o700)
            except OSError:
                pass
            lock_handle = _try_lock_session(candidate, create=True)
            if lock_handle is None:
                _remove_tree(candidate, temp_root=root)
                continue
            try:
                _start_metadata_temp_watchdog(candidate)
            except Exception:
                _release_session_lock(lock_handle)
                _remove_tree(candidate, temp_root=root)
                raise
            _session_directory = candidate
            _session_lock_handle = lock_handle
            atexit.register(_cleanup_current_session)
            return candidate
    raise OSError("Unable to create a private metadata temporary directory")


def _watchdog_command(parent_pid, session_directory):
    args = [
        METADATA_TEMP_WATCHDOG_ARG,
        str(int(parent_pid)),
        str(session_directory),
    ]
    executable = Path(sys.executable).resolve(strict=False)
    launcher = Path(sys.argv[0]).resolve(strict=False)
    if (
        getattr(sys, "frozen", False)
        or "__compiled__" in globals()
        or executable == launcher
    ):
        return [sys.executable, *args]

    main_script = Path(__file__).resolve().parents[2] / "main.py"
    if not main_script.is_file():
        raise OSError("Unable to locate the metadata cleanup watchdog entry point")
    return [sys.executable, str(main_script), *args]


def _stop_process(process):
    if process.poll() is not None:
        return
    try:
        process.terminate()
        process.wait(timeout=1.0)
    except (OSError, subprocess.TimeoutExpired):
        try:
            process.kill()
        except OSError:
            pass


def _start_metadata_temp_watchdog(session_directory):
    directory = _validated_session_directory(
        session_directory,
        expected_pid=os.getpid(),
    )
    ready_path = directory / _READY_FILENAME
    try:
        ready_path.unlink()
    except FileNotFoundError:
        pass

    popen_kwargs = {
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "close_fds": True,
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(
            subprocess,
            "CREATE_NO_WINDOW",
            0,
        )
    else:
        popen_kwargs["start_new_session"] = True

    process = subprocess.Popen(
        _watchdog_command(os.getpid(), directory),
        **popen_kwargs,
    )
    deadline = time.monotonic() + _WATCHDOG_READY_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if ready_path.is_file():
            try:
                ready_path.unlink()
            except OSError:
                pass
            return
        if process.poll() is not None:
            break
        time.sleep(0.02)

    _stop_process(process)
    try:
        ready_path.unlink()
    except OSError:
        pass
    raise OSError("Unable to start the plaintext metadata cleanup watchdog")


def create_guarded_metadata_temp_file(suffix):
    """Create a private temp file guarded by a crash cleanup watchdog."""

    suffix = str(suffix or ".bin")
    if (
        not suffix.startswith(".")
        or len(suffix) > 16
        or not suffix[1:].replace("_", "").isalnum()
    ):
        suffix = ".bin"
    directory = metadata_temp_directory()
    descriptor, temp_path = tempfile.mkstemp(
        prefix=_FILE_PREFIX,
        suffix=suffix,
        dir=directory,
    )
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    return descriptor, temp_path


def discard_guarded_metadata_temp_file(temp_path):
    """Remove a guarded metadata file; its session watchdog is the fallback."""

    try:
        path = _validated_temp_file(temp_path, expected_pid=os.getpid())
    except (OSError, ValueError):
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _wait_for_parent_exit(parent_pid):
    if os.name == "nt":
        kernel32, handle = _open_windows_process(parent_pid)
        if not handle:
            while _process_is_running(parent_pid):
                time.sleep(_WATCHDOG_POLL_SECONDS)
            return
        try:
            result = kernel32.WaitForSingleObject(handle, 0xFFFFFFFF)
            if result != 0x00000000:  # WAIT_OBJECT_0
                while _process_is_running(parent_pid):
                    time.sleep(_WATCHDOG_POLL_SECONDS)
        finally:
            kernel32.CloseHandle(handle)
        return

    while _process_is_running(parent_pid):
        time.sleep(_WATCHDOG_POLL_SECONDS)


def run_metadata_temp_watchdog(parent_pid, session_directory):
    """Watch one parent and delete its plaintext parser directory on exit."""

    try:
        parent_pid = int(parent_pid)
        directory = _validated_session_directory(
            session_directory,
            expected_pid=parent_pid,
        )
    except (OSError, TypeError, ValueError):
        return 2

    ready_path = directory / _READY_FILENAME
    try:
        descriptor = os.open(
            ready_path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL,
            0o600,
        )
        os.close(descriptor)
    except OSError:
        return 3

    try:
        _wait_for_parent_exit(parent_pid)
        if not _remove_tree(directory):
            return 4
    finally:
        try:
            ready_path.unlink()
        except OSError:
            pass
    return 0
