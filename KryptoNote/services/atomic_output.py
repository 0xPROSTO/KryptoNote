import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from ..core.database.connection import (
    OPERATION_LOCK_SUFFIX,
    SESSION_LOCK_SUFFIX,
)


def database_related_paths(database_path):
    """Return database files that an export must never replace."""
    if not database_path or str(database_path) == ":memory:":
        return ()
    database_path = Path(database_path).resolve()
    return (
        database_path,
        Path(f"{database_path}-wal"),
        Path(f"{database_path}-shm"),
        Path(f"{database_path}-journal"),
        Path(f"{database_path}{OPERATION_LOCK_SUFFIX}"),
        Path(f"{database_path}{SESSION_LOCK_SUFFIX}"),
    )


def _paths_match(first, second):
    first = Path(first)
    second = Path(second)
    try:
        if first.exists() and second.exists() and os.path.samefile(first, second):
            return True
    except OSError:
        pass
    first_key = os.path.normcase(os.path.realpath(os.path.abspath(first)))
    second_key = os.path.normcase(os.path.realpath(os.path.abspath(second)))
    return first_key == second_key


def ensure_safe_output_path(output_path, forbidden_paths=()):
    for forbidden_path in forbidden_paths:
        if forbidden_path and _paths_match(output_path, forbidden_path):
            raise ValueError(
                "Export destination cannot overwrite the open project database "
                "or one of its runtime files."
            )


@contextmanager
def atomic_output_path(output_path, *, forbidden_paths=()):
    """Yield a unique sibling temp path and replace the destination on success."""
    output_path = Path(output_path)
    ensure_safe_output_path(output_path, forbidden_paths)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".kryptonote-",
        suffix=".part",
        dir=output_path.parent,
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    replaced = False
    try:
        yield temp_path
        os.replace(temp_path, output_path)
        replaced = True
    finally:
        if not replaced:
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
