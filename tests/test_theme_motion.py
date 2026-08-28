from PySide6.QtCore import QAbstractAnimation, QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QWidget

import KryptoNote.gui.widgets.dialog_motion as dialog_motion
import KryptoNote.gui.widgets.overlays.dim_overlay as dim_overlay
from KryptoNote.gui.theme.theme_bridge import ThemeBridge
from KryptoNote.gui.theme.theme_manager import ThemeManager
from KryptoNote.gui.widgets.dialogs.confirmation_dialog import ConfirmationDialog


def test_motion_mode_persists_and_updates_theme_bridge(tmp_path):
    settings_path = tmp_path / "motion.ini"
    manager = ThemeManager(
        store=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    manager.load()
    bridge = ThemeBridge(manager=manager)
    changes = []
    bridge.motionChanged.connect(lambda: changes.append(bridge.motionMode))

    manager.preview_motion_mode("reduced")

    assert changes == ["reduced"]
    assert bridge.motionMode == "reduced"
    assert bridge.effectiveMotionMode == "reduced"
    assert bridge.motionEnabled is False
    assert bridge.colorMotionEnabled is True
    assert bridge.durationPress == 60
    assert bridge.durationState == 80
    assert bridge.durationPanel == 100
    assert bridge.durationExit == 60

    manager.commit_motion_mode()
    reloaded = ThemeManager(
        store=QSettings(str(settings_path), QSettings.Format.IniFormat)
    )
    reloaded.load()
    reloaded_bridge = ThemeBridge(manager=reloaded)

    assert reloaded.motion_mode == "reduced"
    assert reloaded_bridge.effectiveMotionMode == "reduced"

    reloaded.preview_motion_mode("off")
    assert reloaded_bridge.colorMotionEnabled is False
    assert reloaded_bridge.durationPress == 0
    assert reloaded_bridge.durationState == 0
    assert reloaded_bridge.durationPanel == 0
    assert reloaded_bridge.durationExit == 0


def test_dialog_and_dim_share_enter_exit_lifecycle(qt_application, monkeypatch):
    def duration(_widget, kind):
        return 48 if kind in {"panel", "dialog_enter"} else 28

    monkeypatch.setattr(dialog_motion, "widget_motion_duration", duration)
    monkeypatch.setattr(dim_overlay, "widget_motion_duration", duration)

    host = QWidget()
    host.resize(720, 480)
    host.show()
    manager = dim_overlay.WindowOverlayManager(host)
    dialog = ConfirmationDialog(
        "Delete selected item?",
        "This action cannot be undone.",
        confirm_text="Delete",
        destructive=True,
        icon_name="delete",
        parent=host,
    )
    dialog._dialog_motion_allowed = lambda: True
    dialog._dialog_motion_spatial_allowed = lambda: True
    real_children = dialog.findChildren(
        QWidget,
        options=Qt.FindChildOption.FindDirectChildrenOnly,
    )
    finished_state = {}

    def capture_finished_state(_result):
        surface = dialog.windowHandle()
        proxy = dialog._dialog_motion_proxy
        finished_state.update(
            dialog_visible=dialog.isVisible(),
            surface_opacity=(
                float(surface.opacity()) if surface is not None else 1.0
            ),
            proxy_opacity=(
                float(proxy.surfaceOpacity) if proxy is not None else 1.0
            ),
            real_children_hidden=all(
                child.isHidden() for child in real_children
            ),
        )

    dialog.finished.connect(capture_finished_state)
    manager.prepare("delete-confirmation")
    dialog.set_dialog_motion_present_callback(
        lambda: manager.present(
            "delete-confirmation",
            duration_kind="dialog_enter",
        )
    )
    dialog.set_dialog_motion_dismiss_callback(
        lambda: manager.begin_dismiss("delete-confirmation")
    )

    try:
        dialog.show()
        qt_application.processEvents()

        assert dialog._dialog_motion_phase == "enter"
        surface = dialog.windowHandle()
        assert surface is dialog._dialog_motion_window
        assert surface is not None
        initial_geometry = surface.geometry()
        proxy = dialog._dialog_motion_proxy
        assert proxy is not None
        assert proxy.isWindow()
        assert proxy.isVisible()
        assert float(surface.opacity()) == 0.0
        assert dialog.focusWidget() not in (
            dialog.cancel_button,
            dialog.confirm_button,
        )
        assert not any(child.isHidden() for child in real_children)
        assert (
            dialog._dialog_motion_group.state()
            == QAbstractAnimation.State.Running
        )
        assert (
            manager.overlay.anim.state()
            == QAbstractAnimation.State.Running
        )
        dialog_opacity = float(proxy.surfaceOpacity)
        dim_opacity = manager.overlay.opacity_effect.opacity()
        assert 0.0 <= dialog_opacity < 1.0
        assert 0.0 <= dim_opacity < 1.0
        dialog_progress = (
            dialog_opacity - dialog_motion.ENTER_OPACITY
        ) / (1.0 - dialog_motion.ENTER_OPACITY)
        assert abs(dialog_progress - dim_opacity) < 0.05
        assert dialog_motion.ENTER_SCALE <= float(proxy.scale) < 1.0
        assert surface.geometry() == initial_geometry
        assert proxy.geometry() == dialog.frameGeometry()

        QTest.qWait(80)
        qt_application.processEvents()
        assert dialog._dialog_motion_phase == "idle"
        assert dialog._dialog_motion_proxy is None
        assert float(surface.opacity()) == 1.0
        assert surface.geometry() == initial_geometry
        assert not any(child.isHidden() for child in real_children)
        assert manager.overlay.opacity_effect.opacity() == 1.0
        assert dialog.focusWidget() not in (
            dialog.cancel_button,
            dialog.confirm_button,
        )
        QTest.keyClick(dialog, Qt.Key.Key_Tab)
        assert dialog.cancel_button.hasFocus()
        dialog._focus_dialog_surface()

        dialog.reject()
        assert dialog._dialog_motion_phase == "exit_wait"
        assert float(surface.opacity()) == 1.0
        waiting_proxy = dialog._dialog_motion_proxy
        assert waiting_proxy is not None
        assert waiting_proxy.isVisible()
        QTest.qWait(5)
        qt_application.processEvents()
        assert dialog._dialog_motion_phase == "exit"
        exit_proxy = dialog._dialog_motion_proxy
        assert exit_proxy is not None
        assert exit_proxy.isVisible()
        assert float(surface.opacity()) == 0.0
        assert not any(child.isHidden() for child in real_children)
        assert (
            dialog._dialog_motion_group.state()
            == QAbstractAnimation.State.Running
        )
        assert (
            manager.overlay.anim.state()
            == QAbstractAnimation.State.Running
        )
        assert surface.geometry() == initial_geometry

        QTest.qWait(60)
        qt_application.processEvents()
        assert finished_state["dialog_visible"] is False
        assert finished_state["surface_opacity"] <= 0.001
        assert finished_state["proxy_opacity"] <= 0.001
        assert finished_state["real_children_hidden"] is False
        assert dialog._dialog_motion_proxy is None
        assert float(surface.opacity()) == 1.0
        assert not any(child.isHidden() for child in real_children)
        assert manager.overlay.opacity_effect.opacity() == 0.0
    finally:
        manager.release("delete-confirmation")
        if dialog.isVisible():
            dialog._dialog_motion_bypass = True
            dialog.close()
            dialog._dialog_motion_bypass = False
        host.close()


def test_dialog_exit_falls_back_if_proxy_never_presents(
    qt_application,
    monkeypatch,
):
    def duration(_widget, kind):
        return 24 if kind == "dialog_exit" else 8

    monkeypatch.setattr(dialog_motion, "widget_motion_duration", duration)
    monkeypatch.setattr(dialog_motion, "SURFACE_READY_TIMEOUT_MS", 4)
    monkeypatch.setattr(
        dialog_motion._DialogMotionSurface,
        "_confirm_presentation_ready",
        lambda self: None,
    )

    host = QWidget()
    host.resize(640, 420)
    host.show()
    dialog = ConfirmationDialog(
        "Close this dialog?",
        "The fallback must keep a continuous visible surface.",
        parent=host,
    )
    dialog._dialog_motion_allowed = lambda: True
    dialog._dialog_motion_spatial_allowed = lambda: True
    finished = []
    dialog.finished.connect(finished.append)

    try:
        dialog.show()
        QTest.qWait(20)
        qt_application.processEvents()
        surface = dialog.windowHandle()
        assert surface is not None
        assert float(surface.opacity()) == 1.0

        dialog.reject()
        assert dialog._dialog_motion_phase == "exit_wait"
        assert float(surface.opacity()) == 1.0

        QTest.qWait(10)
        qt_application.processEvents()
        assert dialog._dialog_motion_phase == "exit"
        assert dialog._dialog_motion_proxy is None
        fallback_group = dialog._dialog_motion_group
        assert fallback_group is not None
        assert (
            fallback_group.state()
            == QAbstractAnimation.State.Running
        )
        opacity_animation = fallback_group.animationAt(0)
        assert opacity_animation.targetObject() is surface
        assert bytes(opacity_animation.propertyName()) == b"opacity"
        assert float(opacity_animation.endValue()) == 0.0

        QTest.qWait(40)
        qt_application.processEvents()
        assert finished == [int(QDialog.DialogCode.Rejected)]
        assert not dialog.isVisible()
        assert float(surface.opacity()) == 1.0
    finally:
        if dialog.isVisible():
            dialog._dialog_motion_bypass = True
            dialog.close()
            dialog._dialog_motion_bypass = False
        host.close()
