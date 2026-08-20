from __future__ import annotations

import re
import sys
import time
from dataclasses import dataclass, field
from typing import Callable

from PySide6.QtCore import QObject, Signal, Slot, Qt

from ...core.constants import MEDIA_NODE_TYPES


_WORD_RE = re.compile(r"[\w]+", re.UNICODE)


@dataclass
class _CommandEntry:
    command_id: str
    label: str | Callable[[], str]
    shortcut: str = ""
    icon: str = ""
    aliases: tuple[str, ...] = field(default_factory=tuple)
    keywords: tuple[str, ...] = field(default_factory=tuple)
    favorite: bool = False
    safe_while_surface_open: bool = False
    action: object | None = None
    callback: Callable[[], object] | None = None
    applicable: Callable[[], bool] | None = None
    unavailable_reason: str = "Unavailable right now"
    order: int = 0


class RightShiftDoublePressDetector:
    """Recognize two physical Right Shift presses with a release between them."""

    WINDOW_MS = 350

    def __init__(self, clock_ms: Callable[[], float] | None = None):
        self._clock_ms = clock_ms or (lambda: time.monotonic_ns() / 1_000_000.0)
        self._last_press_ms: float | None = None
        self._released_after_press = True

    def reset(self):
        self._last_press_ms = None
        self._released_after_press = True

    @staticmethod
    def is_right_shift_event(event, platform_name: str | None = None) -> bool:
        if event.key() != Qt.Key.Key_Shift:
            return False
        try:
            scan_code = int(event.nativeScanCode())
        except (AttributeError, TypeError, ValueError):
            scan_code = 0
        try:
            virtual_key = int(event.nativeVirtualKey())
        except (AttributeError, TypeError, ValueError):
            virtual_key = 0

        platform_name = (platform_name or sys.platform).lower()
        if platform_name.startswith("win"):
            return virtual_key == 0xA1 or (scan_code & 0xFF) == 0x36
        if platform_name.startswith("linux") or platform_name in {"xcb", "wayland"}:
            return virtual_key == 0xFFE2 or scan_code in {54, 62}
        if platform_name in {"darwin", "macos", "cocoa"}:
            return virtual_key == 0x3C
        return virtual_key in {0xA1, 0xFFE2}

    def handle_press(self, event, platform_name: str | None = None) -> bool:
        try:
            if event.isAutoRepeat():
                return False
        except AttributeError:
            pass

        if not self.is_right_shift_event(event, platform_name):
            self.reset()
            return False
        if not self._released_after_press:
            return False

        now_ms = float(self._clock_ms())
        matched = (
            self._last_press_ms is not None
            and 0.0 <= now_ms - self._last_press_ms <= self.WINDOW_MS
        )
        self._released_after_press = False
        if matched:
            self._last_press_ms = None
            return True
        self._last_press_ms = now_ms
        return False

    def handle_release(self, event, platform_name: str | None = None):
        try:
            if event.isAutoRepeat():
                return
        except AttributeError:
            pass
        if self.is_right_shift_event(event, platform_name):
            self._released_after_press = True


class CommandPaletteController(QObject):
    """QML-facing command catalog that reuses window actions and canvas slots."""

    tagsRequested = Signal(int)

    def __init__(self, node_model, canvas_controller, operations, window, parent=None):
        super().__init__(parent)
        self._node_model = node_model
        self._canvas = canvas_controller
        self._operations = operations
        self._window = window
        self._entries: dict[str, _CommandEntry] = {}
        self._next_order = 0

    def register_action(
        self,
        command_id,
        action,
        *,
        label,
        shortcut="",
        icon="",
        aliases=(),
        keywords=(),
        favorite=False,
        safe_while_surface_open=False,
    ):
        self._register(
            _CommandEntry(
                command_id=str(command_id),
                label=label,
                shortcut=str(shortcut),
                icon=str(icon),
                aliases=tuple(aliases),
                keywords=tuple(keywords),
                favorite=bool(favorite),
                safe_while_surface_open=bool(safe_while_surface_open),
                action=action,
            )
        )

    def register_command(
        self,
        command_id,
        callback,
        *,
        label,
        shortcut="",
        icon="",
        aliases=(),
        keywords=(),
        favorite=False,
        safe_while_surface_open=False,
        applicable=None,
        unavailable_reason="Unavailable right now",
    ):
        self._register(
            _CommandEntry(
                command_id=str(command_id),
                label=label,
                shortcut=str(shortcut),
                icon=str(icon),
                aliases=tuple(aliases),
                keywords=tuple(keywords),
                favorite=bool(favorite),
                safe_while_surface_open=bool(safe_while_surface_open),
                callback=callback,
                applicable=applicable,
                unavailable_reason=str(unavailable_reason),
            )
        )

    def register_context_commands(self):
        self.register_command(
            "dashboard",
            self._window.open_dashboard,
            label="Open dashboard",
            icon="database",
            aliases=("statistics", "stats"),
            keywords=("nodes", "links", "project"),
            safe_while_surface_open=True,
        )
        self.register_command(
            "undo",
            self._canvas.undo_graph,
            label="Undo graph action",
            shortcut="Ctrl+Z",
            icon="reset",
            aliases=("undo",),
            keywords=("history", "revert"),
        )
        self.register_command(
            "redo",
            self._canvas.redo_graph,
            label="Redo graph action",
            shortcut="Ctrl+Y",
            icon="reset",
            aliases=("redo",),
            keywords=("history", "repeat"),
        )
        self.register_command(
            "copy-internal",
            lambda: self._canvas.copy_nodes(0),
            label="Copy selected nodes",
            shortcut="Ctrl+C",
            icon="export",
            aliases=("copy",),
            keywords=("clipboard", "selection"),
            applicable=self._has_selection,
        )
        self.register_command(
            "paste-internal",
            self._canvas.paste_nodes,
            label="Paste nodes",
            shortcut="Ctrl+V",
            icon="open",
            aliases=("paste",),
            keywords=("clipboard", "internal"),
        )
        self.register_command(
            "copy-system",
            lambda: self._canvas.copy_to_system_clipboard(0),
            label="Copy to system clipboard",
            shortcut="Ctrl+Shift+C",
            icon="export",
            aliases=("system copy",),
            keywords=("clipboard", "text", "image"),
            applicable=self._has_system_copy_selection,
        )
        self.register_command(
            "paste-system",
            self._canvas.paste_from_system_clipboard,
            label="Paste from system clipboard",
            shortcut="Ctrl+Shift+V",
            icon="open",
            aliases=("system paste",),
            keywords=("clipboard", "text", "image"),
        )
        self.register_command(
            "duplicate-selection",
            lambda: self._canvas.duplicate_node(0),
            label="Duplicate selected nodes",
            icon="add",
            aliases=("duplicate", "clone"),
            keywords=("copy", "selection"),
            applicable=self._has_selection,
        )
        self.register_command(
            "clear-selection",
            self._canvas.clear_selection,
            label="Clear selection",
            shortcut="Esc",
            icon="remove",
            aliases=("deselect all",),
            keywords=("canvas", "selection"),
            applicable=self._has_selection,
        )
        self.register_command(
            "delete-selection",
            self._canvas.delete_selected_nodes,
            label="Delete selected nodes",
            shortcut="Delete",
            icon="delete",
            aliases=("delete", "remove"),
            keywords=("selection", "trash"),
            applicable=self._has_selection,
        )
        self.register_command(
            "edit-selected-text",
            self._open_selected,
            label="Edit selected text node",
            icon="edit",
            aliases=("edit note", "open note"),
            keywords=("text", "content"),
            applicable=lambda: self._single_type() == "text",
        )
        self.register_command(
            "open-selected-media",
            self._open_selected,
            label="Open selected media",
            icon="open",
            aliases=("open image", "open video", "open audio"),
            keywords=("viewer", "photo", "media"),
            applicable=lambda: self._single_type() in MEDIA_NODE_TYPES,
        )
        self.register_command(
            "rename-selected",
            self._rename_selected,
            label="Rename selected node",
            icon="rename",
            aliases=("rename",),
            keywords=("title", "name"),
            applicable=lambda: self._single_type() not in {None, "frame"},
        )
        self.register_command(
            "auto-fit-selected",
            self._auto_fit_selected,
            label="Auto-fit selected node",
            icon="fit",
            aliases=("auto fit", "fit node"),
            keywords=("resize", "size"),
            applicable=lambda: self._single_type() in {"text", *MEDIA_NODE_TYPES},
        )
        self.register_command(
            "selected-properties",
            self._show_selected_properties,
            label="Show selected node properties",
            icon="info",
            aliases=("properties", "details"),
            keywords=("metadata", "info"),
            applicable=self._has_single_selection,
        )
        self.register_command(
            "selected-tags",
            self._show_selected_tags,
            label="Edit selected node tags",
            icon="tag",
            aliases=("tags", "tag node"),
            keywords=("labels", "categories"),
            applicable=lambda: self._single_type() not in {None, "frame"},
        )
        self.register_command(
            "export-selected-media",
            self._export_selected_media,
            label="Export selected media to disk",
            icon="export",
            aliases=("export media", "save media"),
            keywords=("file", "disk"),
            applicable=lambda: self._single_type() in MEDIA_NODE_TYPES,
        )
        self.register_command(
            "edit-selected-frame",
            self._open_selected,
            label="Edit selected frame properties",
            icon="edit",
            aliases=("frame properties",),
            keywords=("frame", "color", "opacity"),
            applicable=lambda: self._single_type() == "frame",
        )
        self.register_command(
            "toggle-selected-frame-lock",
            self._toggle_selected_frame_lock,
            label=self._frame_lock_label,
            icon="lock",
            aliases=("lock frame", "unlock frame"),
            keywords=("frame", "move contents"),
            applicable=lambda: self._single_type() == "frame",
        )
        self.register_command(
            "select-frame-contents",
            self._select_frame_contents,
            label="Select frame contents",
            icon="select-all",
            aliases=("select contents",),
            keywords=("frame", "selection", "contained nodes"),
            applicable=lambda: self._single_type() == "frame",
        )

    def _register(self, entry: _CommandEntry):
        if entry.command_id in self._entries:
            raise ValueError(f"Duplicate command id: {entry.command_id}")
        entry.order = self._next_order
        self._next_order += 1
        self._entries[entry.command_id] = entry

    @Slot(str, result=list)
    def query_commands(self, query):
        normalized = str(query or "").strip().casefold()
        restricted = self._surface_restricted()
        ranked = []
        for entry in self._entries.values():
            if restricted and not entry.safe_while_surface_open:
                continue
            if entry.applicable is not None and not entry.applicable():
                continue
            if not normalized:
                if not entry.favorite:
                    continue
                score = 0
            else:
                score = self._match_score(entry, normalized)
                if score is None:
                    continue
            ranked.append((score, entry.order, entry))
        ranked.sort(key=lambda item: (item[0], item[1]))
        return [self._serialize(entry) for _, _, entry in ranked]

    @Slot(str, result=bool)
    def execute_command(self, command_id):
        entry = self._entries.get(str(command_id))
        if entry is None or self._operations.is_busy:
            return False
        if self._surface_restricted() and not entry.safe_while_surface_open:
            return False
        if entry.applicable is not None and not entry.applicable():
            return False
        if entry.action is not None:
            if not entry.action.isEnabled():
                return False
            entry.action.trigger()
            return True
        if entry.callback is None:
            return False
        result = entry.callback()
        return result is not False

    def _serialize(self, entry):
        enabled = True
        reason = ""
        if entry.action is not None and not entry.action.isEnabled():
            enabled = False
            reason = entry.unavailable_reason
        return {
            "id": entry.command_id,
            "label": self._label(entry),
            "shortcut": entry.shortcut,
            "icon": (
                f"../assets/icons/{entry.icon}.svg" if entry.icon else ""
            ),
            "enabled": enabled,
            "reason": reason,
        }

    @staticmethod
    def _label(entry):
        return str(entry.label() if callable(entry.label) else entry.label)

    @classmethod
    def _match_score(cls, entry, query):
        label = cls._label(entry).casefold()
        aliases = tuple(str(value).casefold() for value in entry.aliases)
        candidates = (label, *aliases)
        if query in candidates:
            return 0
        if any(value.startswith(query) for value in candidates):
            return 1
        if any(
            any(word.startswith(query) for word in _WORD_RE.findall(value))
            for value in candidates
        ):
            return 2
        if any(query in value for value in candidates):
            return 3
        if any(query in str(value).casefold() for value in entry.keywords):
            return 4
        return None

    def _surface_restricted(self):
        view = getattr(self._window, "view", None)
        root = view.rootObject() if view is not None else None
        if root is None:
            return False
        return any(
            bool(root.property(name))
            for name in (
                "isTextEditorOpen",
                "isFrameEditorOpen",
                "isNodePropertiesOpen",
                "isMediaViewerOpen",
            )
        )

    def _selected_ids(self):
        return [int(node_id) for node_id in self._node_model.get_selected_ids()]

    def _has_selection(self):
        return bool(self._selected_ids())

    def _has_single_selection(self):
        return len(self._selected_ids()) == 1

    def _selected_node(self):
        selected = self._selected_ids()
        return self._node_model.get_node_data(selected[0]) if len(selected) == 1 else None

    def _single_type(self):
        node = self._selected_node()
        return node.get("type") if node else None

    def _has_system_copy_selection(self):
        selected = self._selected_ids()
        if not selected:
            return False
        return all(
            (self._node_model.get_node_data(node_id) or {}).get("type")
            in {"text", "image"}
            for node_id in selected
        )

    def _selected_id(self):
        selected = self._selected_ids()
        return selected[0] if len(selected) == 1 else 0

    def _open_selected(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.request_open_editor(node_id)

    def _rename_selected(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.rename_node(node_id, "")

    def _auto_fit_selected(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.auto_fit_node(node_id)

    def _show_selected_properties(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.show_node_properties(node_id)

    def _show_selected_tags(self):
        node_id = self._selected_id()
        if node_id:
            self.tagsRequested.emit(node_id)

    def _export_selected_media(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.export_node_to_disk(node_id)

    def _toggle_selected_frame_lock(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.toggle_frame_locked(node_id)

    def _select_frame_contents(self):
        node_id = self._selected_id()
        if node_id:
            self._canvas.select_frame_contents(node_id)

    def _frame_lock_label(self):
        node_id = self._selected_id()
        return (
            "Unlock selected frame"
            if node_id and self._canvas.is_frame_locked(node_id)
            else "Lock selected frame"
        )
