import sqlite3
import threading
import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QEventLoop, QObject

from KryptoNote.core.database.operations import DeletionResult
from KryptoNote.core.database.repository import NodeRepository
from KryptoNote.gui.controllers.delete_controller import DeleteController
from KryptoNote.gui.services.operation_coordinator import OperationCoordinator


class FakeNodeModel:
    def __init__(self, *node_types):
        self.nodes = {
            index: {
                "id": index,
                "type": node_type,
                "total_size": 0,
                "is_deleting": False,
            }
            for index, node_type in enumerate(node_types, start=1)
        }
        self.removed = []
        self.mutations_thread_ids = []

    def get_node_data(self, node_id):
        return self.nodes.get(int(node_id))

    def set_deleting(self, node_id, deleting):
        self.mutations_thread_ids.append(threading.get_ident())
        self.nodes[int(node_id)]["is_deleting"] = bool(deleting)

    def remove_node(self, node_id):
        self.mutations_thread_ids.append(threading.get_ident())
        self.removed.append(int(node_id))
        self.nodes.pop(int(node_id), None)

    def get_selected_ids(self):
        return []


class ExplodingNodeModel(FakeNodeModel):
    def remove_node(self, node_id):
        raise RuntimeError("model update failed")


class FakeConnectionModel:
    def __init__(self):
        self.removed = []

    def mark_connections_for_node_deleting(
        self, node_id, deleting=True, finalize=True
    ):
        return None

    def remove_connections_for_node(self, node_id):
        self.removed.append(int(node_id))


class DeferredGraphCommands:
    def __init__(self):
        self.delete_calls = []
        self.vacuum_calls = []

    def delete_node_after_animation(self, node_id, **callbacks):
        self.delete_calls.append((int(node_id), callbacks))

    def delete_nodes_after_animation(self, node_ids, **callbacks):
        self.delete_calls.append((tuple(int(node_id) for node_id in node_ids), callbacks))

    def vacuum_database(self, **callbacks):
        self.vacuum_calls.append(callbacks)

    def complete_delete(self, result=None, error=None, index=0):
        callbacks = self.delete_calls[index][1]
        if error is None:
            callbacks["on_success"](result)
        else:
            callbacks["on_error"](error)
        callbacks["on_finish_vacuum"]()

    def complete_vacuum(self, success=True, payload=None, index=0):
        callbacks = self.vacuum_calls[index]
        if success:
            callbacks["on_success"](payload)
        else:
            callbacks["on_error"](payload or RuntimeError("vacuum failed"))
        callbacks["on_finish"]()


class ReloadParent(QObject):
    def __init__(self):
        super().__init__()
        self.reload_count = 0

    def load_from_db(self):
        self.reload_count += 1


@pytest.fixture(scope="session")
def qt_app(qt_application):
    return qt_application


def wait_for(qt_app, predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
        if predicate():
            return True
        time.sleep(0.001)
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)
    return bool(predicate())


def make_controller(
    node_model,
    graph=None,
    parent=None,
    vacuum_threshold_provider=None,
):
    graph = graph or DeferredGraphCommands()
    coordinator = OperationCoordinator()
    controller = DeleteController(
        node_model,
        FakeConnectionModel(),
        graph,
        parent=parent,
        operation_coordinator=coordinator,
        vacuum_threshold_provider=vacuum_threshold_provider,
    )
    return controller, graph, coordinator


def test_context_delete_confirms_unless_shift_bypasses(monkeypatch):
    node_model = FakeNodeModel("text", "text", "text")
    controller, _graph, _coordinator = make_controller(node_model)
    confirmations = []
    requested = []
    answers = iter((False, True))

    def confirm(count):
        confirmations.append(int(count))
        return next(answers)

    monkeypatch.setattr(controller, "_confirm_selected_delete", confirm)
    monkeypatch.setattr(
        controller,
        "request_animated_delete",
        lambda node_id: requested.append(int(node_id)),
    )

    controller.delete_node_from_context(1, False)
    controller.delete_node_from_context(2, True)
    controller.delete_node_from_context(3, False)

    assert confirmations == [1, 1]
    assert requested == [2, 3]


def test_empty_text_delete_does_not_wait_for_qml_animation(qt_app):
    node_model = FakeNodeModel("text")
    controller, graph, coordinator = make_controller(node_model)

    controller.request_animated_delete(1)

    assert len(graph.delete_calls) == 1
    assert coordinator.is_busy
    assert node_model.nodes[1]["is_deleting"]

    graph.complete_delete(
        DeletionResult(
            item_ids=(1,),
            item_types=("text",),
            deleted_bytes=0,
            requires_vacuum=False,
        )
    )

    assert wait_for(qt_app, lambda: not coordinator.is_busy)
    assert node_model.removed == [1]
    assert not graph.vacuum_calls


def test_worker_terminal_callback_is_applied_on_gui_thread(qt_app):
    node_model = FakeNodeModel("text")
    controller, graph, coordinator = make_controller(node_model)
    gui_thread_id = threading.get_ident()
    controller.request_animated_delete(1)
    callbacks = graph.delete_calls[0][1]

    worker = threading.Thread(
        target=lambda: (
            callbacks["on_success"](
                DeletionResult(
                    item_ids=(1,),
                    item_types=("text",),
                    deleted_bytes=0,
                    requires_vacuum=False,
                )
            ),
            callbacks["on_finish_vacuum"](),
        )
    )
    worker.start()
    worker.join()

    assert node_model.removed == []
    assert wait_for(qt_app, lambda: not coordinator.is_busy)
    assert node_model.removed == [1]
    assert node_model.mutations_thread_ids[-1] == gui_thread_id


def test_late_delete_callback_cannot_finish_new_operation(qt_app):
    node_model = FakeNodeModel("text", "text")
    controller, graph, coordinator = make_controller(node_model)

    controller.request_animated_delete(1)
    old_token = controller._delete_token
    old_callbacks = graph.delete_calls[0][1]
    controller._finish_delete(old_token)

    controller.request_animated_delete(2)
    new_token = controller._delete_token
    old_callbacks["on_success"](
        DeletionResult(
            item_ids=(1,),
            item_types=("text",),
            deleted_bytes=0,
            requires_vacuum=False,
        )
    )
    old_callbacks["on_finish_vacuum"]()
    qt_app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 10)

    assert coordinator.owns(new_token)
    assert node_model.removed == []

    graph.complete_delete(
        DeletionResult(
            item_ids=(2,),
            item_types=("text",),
            deleted_bytes=0,
            requires_vacuum=False,
        ),
        index=1,
    )
    assert wait_for(qt_app, lambda: not coordinator.is_busy)
    assert node_model.removed == [2]


@pytest.mark.parametrize("success", [True, False])
def test_vacuum_success_and_error_always_release_operation(qt_app, success):
    node_model = FakeNodeModel("video")
    controller, graph, coordinator = make_controller(node_model)
    controller.request_animated_delete(1)
    graph.complete_delete(
        DeletionResult(
            item_ids=(1,),
            item_types=("video",),
            deleted_bytes=20 * 1024 * 1024,
            requires_vacuum=True,
        )
    )
    assert wait_for(qt_app, lambda: len(graph.vacuum_calls) == 1)
    assert coordinator.active_kind == "vacuum"

    graph.complete_vacuum(success=success, payload=RuntimeError("broken"))
    assert wait_for(qt_app, lambda: not coordinator.is_busy)


def test_model_reconciliation_exception_still_finishes_and_schedules_resync(qt_app):
    parent = ReloadParent()
    controller, graph, coordinator = make_controller(
        ExplodingNodeModel("text"),
        parent=parent,
    )
    controller.request_animated_delete(1)
    graph.complete_delete(
        DeletionResult(
            item_ids=(1,),
            item_types=("text",),
            deleted_bytes=0,
            requires_vacuum=False,
        )
    )

    assert wait_for(qt_app, lambda: not coordinator.is_busy)
    assert wait_for(qt_app, lambda: parent.reload_count == 1)


def test_vacuum_policy_uses_reusable_space_and_can_be_disabled():
    threshold = 10 * 1024 * 1024
    predicate = NodeRepository._requires_vacuum_for_reusable_space

    assert not predicate(500 * 1024 * 1024, 0)
    assert not predicate(threshold - 1, threshold)
    assert predicate(threshold, threshold)


def test_delete_reports_committed_reusable_space(tmp_path):
    from KryptoNote.core.database.connection import open_sqlite_connection

    db_path = tmp_path / "vacuum-policy.sqlite"
    connection = open_sqlite_connection(str(db_path))
    connection.executescript(
        "CREATE TABLE items ("
        "id INTEGER PRIMARY KEY, type TEXT, total_size INTEGER, "
        "storage_state TEXT);"
        "CREATE TABLE media_chunks ("
        "id INTEGER PRIMARY KEY, item_id INTEGER, data BLOB);"
    )
    connection.execute(
        "INSERT INTO items VALUES (1, 'image', ?, 'ready')",
        (512 * 1024,),
    )
    connection.execute(
        "INSERT INTO media_chunks (item_id, data) VALUES (1, zeroblob(?))",
        (512 * 1024,),
    )
    connection.commit()
    db = SimpleNamespace(
        db_path=str(db_path),
        conn=connection,
        cursor=connection.cursor(),
    )
    repository = NodeRepository(db)
    completed = threading.Event()
    results = []
    errors = []
    try:
        repository.delete_node_cascade(
            1,
            vacuum_threshold_bytes=1,
            on_success=lambda result: (
                results.append(result),
                completed.set(),
            ),
            on_error=lambda error: (errors.append(error), completed.set()),
        )
        assert completed.wait(2.0)
        assert not errors
        assert results[0].reusable_bytes > 0
        assert results[0].requires_vacuum
    finally:
        repository.close()
        db.cursor.close()
        connection.close()


def test_text_delete_does_not_request_vacuum_with_reusable_space(
    tmp_path,
):
    from KryptoNote.core.database.connection import open_sqlite_connection

    db_path = tmp_path / "text-delete-vacuum-policy.sqlite"
    connection = open_sqlite_connection(str(db_path))
    connection.executescript(
        "CREATE TABLE items ("
        "id INTEGER PRIMARY KEY, type TEXT, total_size INTEGER, "
        "storage_state TEXT);"
        "CREATE TABLE media_chunks ("
        "id INTEGER PRIMARY KEY, item_id INTEGER, data BLOB);"
    )
    connection.execute(
        "INSERT INTO items VALUES (1, 'text', 0, 'ready')"
    )
    connection.execute(
        "INSERT INTO items VALUES (2, 'image', ?, 'ready')",
        (512 * 1024,),
    )
    connection.execute(
        "INSERT INTO media_chunks (item_id, data) VALUES (2, zeroblob(?))",
        (512 * 1024,),
    )
    connection.commit()
    connection.execute("DELETE FROM media_chunks WHERE item_id=2")
    connection.execute("DELETE FROM items WHERE id=2")
    connection.commit()
    db = SimpleNamespace(
        db_path=str(db_path),
        conn=connection,
        cursor=connection.cursor(),
    )
    repository = NodeRepository(db)
    completed = threading.Event()
    results = []
    errors = []
    try:
        repository.delete_node_cascade(
            1,
            vacuum_threshold_bytes=1,
            on_success=lambda result: (
                results.append(result),
                completed.set(),
            ),
            on_error=lambda error: (errors.append(error), completed.set()),
        )
        assert completed.wait(2.0)
        assert not errors
        assert results[0].reusable_bytes > 0
        assert not results[0].requires_vacuum
    finally:
        repository.close()
        db.cursor.close()
        connection.close()


def test_delete_passes_global_vacuum_threshold_to_repository():
    node_model = FakeNodeModel("video")
    controller, graph, _coordinator = make_controller(
        node_model,
        vacuum_threshold_provider=lambda: 0,
    )

    controller.request_animated_delete(1)

    assert graph.delete_calls[0][1]["vacuum_threshold_bytes"] == 0


def test_vacuum_threshold_setting_persists_and_validates(tmp_path):
    from PySide6.QtCore import QSettings

    from KryptoNote.gui.theme.theme_manager import ThemeManager

    settings_path = tmp_path / "maintenance.ini"
    manager = ThemeManager(
        store=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    manager.load()
    manager.commit_vacuum_threshold_bytes(5 * 1024 * 1024 * 1024)

    reloaded = ThemeManager(
        store=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    reloaded.load()
    assert reloaded.vacuum_threshold_bytes == 5 * 1024 * 1024 * 1024

    reloaded.commit_vacuum_threshold_bytes(123)
    assert reloaded.vacuum_threshold_bytes == 10 * 1024 * 1024


class MemoryDb:
    db_path = ":memory:"

    def __init__(self):
        self.conn = sqlite3.connect(":memory:")
        self.cursor = self.conn.cursor()


def test_repository_emits_one_terminal_callback_and_always_finishes():
    db = MemoryDb()
    repository = NodeRepository(db)
    try:
        success_events = []
        repository._execute_on_separate_connection(
            lambda _cursor, _conn: None,
            on_success=lambda: success_events.append("success"),
            on_error=lambda _error: success_events.append("error"),
            on_finish=lambda: success_events.append("finish"),
        )
        assert success_events == ["success", "finish"]

        error_events = []
        with pytest.raises(RuntimeError):
            repository._execute_on_separate_connection(
                lambda _cursor, _conn: (_ for _ in ()).throw(
                    RuntimeError("broken")
                ),
                on_success=lambda: error_events.append("success"),
                on_error=lambda _error: error_events.append("error"),
                on_finish=lambda: error_events.append("finish"),
            )
        assert error_events == ["error", "finish"]
    finally:
        repository.close()
        db.conn.close()


def test_close_cooperatively_stops_an_active_media_export(
    qt_app, monkeypatch
):
    from KryptoNote.gui.windows.main_window import ZeroXXWindow

    class CloseEvent:
        ignored = False

        def ignore(self):
            self.ignored = True

    class CanvasController:
        shutdown_calls = 0

        @staticmethod
        def has_active_synchronous_import():
            return False

        @staticmethod
        def has_active_background_jobs():
            return True

        def shutdown_background_jobs(self):
            self.shutdown_calls += 1
            return False

    warnings = []
    monkeypatch.setattr(
        "KryptoNote.gui.windows.main_window.QMessageBox.warning",
        lambda *_args: warnings.append(True),
    )
    statuses = []
    canvas_controller = CanvasController()
    window = SimpleNamespace(
        operation_coordinator=SimpleNamespace(
            active_kind="media_export",
            active_message="Exporting media",
            is_busy=True,
        ),
        canvas_controller=canvas_controller,
        _handle_status_update=lambda *args: statuses.append(args),
    )
    event = CloseEvent()

    ZeroXXWindow.closeEvent(window, event)

    assert canvas_controller.shutdown_calls == 1
    assert event.ignored
    assert warnings == [True]
    assert statuses[-1] == ("Stopping background operation...", "warning")
