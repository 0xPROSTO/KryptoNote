from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog

from KryptoNote.gui.widgets.dialogs.canvas_navigation_dialog import (
    GoToDialog,
    ZoomToDialog,
)


def _show(dialog, application):
    dialog.show()
    application.processEvents()
    application.processEvents()


def _has_field_focus(field):
    return field.hasFocus() or field.lineEdit().hasFocus()


def test_zoom_to_focuses_selected_value_and_applies_with_enter(qt_application):
    dialog = ZoomToDialog(5, 500)
    _show(dialog, qt_application)

    assert dialog.zoom_input.minimum() == 5
    assert dialog.zoom_input.maximum() == 500
    assert _has_field_focus(dialog.zoom_input)
    assert "100" in dialog.zoom_input.lineEdit().selectedText()

    QTest.keyClicks(dialog.zoom_input, "999")
    assert "999" in dialog.zoom_input.text()
    dialog.zoom_input.interpretText()
    assert dialog.zoom_percent == 500

    dialog.zoom_input.selectAll()
    QTest.keyClicks(dialog.zoom_input, "-20")
    assert "-20" in dialog.zoom_input.text()
    dialog.zoom_input.interpretText()
    assert dialog.zoom_percent == 5

    dialog.zoom_input.setValue(100)
    QTest.keyClick(dialog.zoom_input, Qt.Key.Key_Up)
    assert dialog.zoom_percent == 101
    QTest.keyClick(dialog.zoom_input, Qt.Key.Key_Return)
    qt_application.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.zoom_percent == 101


def test_go_to_enter_and_arrow_navigation_follow_the_field_contract(qt_application):
    dialog = GoToDialog(12.6, -8.6)
    _show(dialog, qt_application)

    assert dialog.coordinates == (13, -9)
    assert _has_field_focus(dialog.x_input)
    assert dialog.x_input.lineEdit().selectedText() == "13"

    QTest.keyClick(dialog.x_input, Qt.Key.Key_Right)
    assert _has_field_focus(dialog.y_input)
    assert dialog.y_input.lineEdit().hasSelectedText()

    QTest.keyClick(dialog.y_input, Qt.Key.Key_Left)
    assert _has_field_focus(dialog.x_input)
    assert dialog.x_input.lineEdit().hasSelectedText()

    dialog.x_input.setValue(-42)
    QTest.keyClick(dialog.x_input, Qt.Key.Key_Return)
    assert _has_field_focus(dialog.y_input)
    assert dialog.y_input.lineEdit().hasSelectedText()

    dialog.y_input.setValue(88)
    QTest.keyClick(dialog.y_input, Qt.Key.Key_Return)
    qt_application.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.coordinates == (-42, 88)


def test_go_to_button_applies_both_values_from_the_first_field(qt_application):
    dialog = GoToDialog(0, 0)
    _show(dialog, qt_application)
    dialog.x_input.setValue(-101)
    dialog.y_input.setValue(202)
    dialog.x_input.setFocus()

    dialog.action_button.click()
    qt_application.processEvents()

    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.coordinates == (-101, 202)
