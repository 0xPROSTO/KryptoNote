from dataclasses import dataclass
import os
import sqlite3
from pathlib import Path


@dataclass(frozen=True, slots=True)
class DatabaseOperationProgress:
    """Thread-safe progress snapshot for a database operation."""

    kind: str
    phase: str
    determinate: bool
    current_bytes: int = 0
    total_bytes: int = 0
    message: str = ""
    cancellable: bool = False

    @property
    def fraction(self):
        if not self.determinate or self.total_bytes <= 0:
            return 0.0
        return max(
            0.0,
            min(1.0, float(self.current_bytes) / float(self.total_bytes)),
        )


@dataclass(frozen=True, slots=True)
class DeletionResult:
    """Authoritative result of a node deletion read from the database."""

    item_ids: tuple[int, ...]
    item_types: tuple[str, ...]
    deleted_bytes: int = 0
    requires_vacuum: bool = False


@dataclass(frozen=True, slots=True)
class DatabaseSpaceStats:
    main_bytes: int = 0
    wal_bytes: int = 0
    shm_bytes: int = 0
    physical_bytes: int = 0
    reusable_bytes: int = 0


@dataclass(frozen=True, slots=True)
class MaintenanceResult:
    status: str
    before: DatabaseSpaceStats
    after: DatabaseSpaceStats
    message: str = ""


def read_database_space_stats(db_path, connection=None):
    if not db_path or db_path == ":memory:":
        return DatabaseSpaceStats()

    path = Path(db_path).resolve()

    def file_size(candidate):
        try:
            return int(os.path.getsize(candidate))
        except OSError:
            return 0

    main_bytes = file_size(path)
    wal_bytes = file_size(f"{path}-wal")
    shm_bytes = file_size(f"{path}-shm")
    owned_connection = None
    reusable_bytes = 0
    try:
        current = connection
        if current is None:
            owned_connection = sqlite3.connect(
                f"{path.as_uri()}?mode=ro", uri=True, timeout=2.0
            )
            current = owned_connection
        page_size = int(current.execute("PRAGMA page_size").fetchone()[0])
        freelist_count = int(
            current.execute("PRAGMA freelist_count").fetchone()[0]
        )
        reusable_bytes = page_size * freelist_count
    except sqlite3.Error:
        reusable_bytes = 0
    finally:
        if owned_connection is not None:
            owned_connection.close()

    return DatabaseSpaceStats(
        main_bytes=main_bytes,
        wal_bytes=wal_bytes,
        shm_bytes=shm_bytes,
        physical_bytes=main_bytes + wal_bytes + shm_bytes,
        reusable_bytes=reusable_bytes,
    )
