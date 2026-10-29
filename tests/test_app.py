import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox

from treetask.repository import Repository
from treetask.ui import MainWindow, TaskDialog, VIEWS, apply_theme


class NativeWindowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        apply_theme(cls.app)

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Repository(Path(directory.name) / "tasks.db")
        self.addCleanup(self.repo.close)
        self.window = MainWindow(self.repo)
        self.addCleanup(self.window.deleteLater)
        self.warning_patch = patch.object(QMessageBox, "warning")
        self.warning = self.warning_patch.start()
        self.addCleanup(self.warning_patch.stop)

    def tearDown(self):
        self.warning.assert_not_called()
        self.app.processEvents()

    def titles(self):
        return [self.window.tree.topLevelItem(i).text(0)
                for i in range(self.window.tree.topLevelItemCount())]

    def test_default_views_and_empty_state(self):
        self.assertEqual([self.window.views.item(i).text() for i in range(5)],
                         [label for _, label in VIEWS])
        self.assertEqual(self.window.views.currentRow(), 3)
        self.assertFalse(self.window.empty.isHidden())
        self.assertTrue(self.window.tag_list.isHidden())

    def test_create_edit_and_clear_metadata_in_dialog(self):
        dialog = TaskDialog(self.repo, parent=self.window)
        dialog.title.setText("Task")
        dialog.description.setPlainText("Details")
        dialog.tags.setText("work, WORK, urgent")
        dialog.save()
        self.assertEqual(dialog.result(), QDialog.DialogCode.Accepted)
        task = self.repo.task(dialog.saved_id)
        self.assertEqual((task["description"], task["tags"]), ("Details", "work, urgent"))
        edit = TaskDialog(self.repo, task, self.window)
        self.assertEqual(edit.description.toPlainText(), "Details")
        edit.description.clear()
        edit.tags.clear()
        edit.save()
        self.assertEqual(self.repo.task(task["id"])["description"], "")
        self.window.refresh()
        self.assertEqual(self.titles(), ["Task"])

    def test_checkbox_removes_completed_task_from_ongoing(self):
        identity = self.repo.save_task("Task", "2026-10-29")
        self.window.refresh()
        self.window.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Checked)
        self.app.processEvents()
        self.assertEqual(self.titles(), [])
        self.assertEqual(self.repo.task(identity)["completed"], 1)
        self.window.views.setCurrentRow(2)
        self.assertEqual(self.titles(), ["Task"])
        self.window.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)
        self.app.processEvents()
        self.assertEqual(self.titles(), [])

    def test_sort_tags_and_search_keep_working_together(self):
        self.repo.save_task("Later", "2026-11-01", tags="Work")
        self.repo.save_task("Earlier", "2026-10-01", "Cabin", "work, urgent")
        self.repo.save_task("Other", "2026-10-02", tags="home")
        self.window.refresh()
        self.assertEqual(self.titles(), ["Earlier", "Other", "Later"])
        self.window.sort.setCurrentIndex(1)
        self.assertEqual(self.titles(), ["Later", "Other", "Earlier"])
        work = next(self.window.tag_list.item(i) for i in range(self.window.tag_list.count())
                    if self.window.tag_list.item(i).text() == "Work")
        work.setCheckState(Qt.CheckState.Checked)
        self.app.processEvents()
        self.assertEqual(self.titles(), ["Later", "Earlier"])
        self.window.search.setText("CABIN")
        self.window.refresh()
        self.assertEqual(self.titles(), ["Earlier"])
        self.window.views.setCurrentRow(4)
        self.assertEqual(self.window.selected_tags(), ["work"])

    def test_subtask_checkbox_does_not_complete_parent(self):
        parent = self.repo.save_task("Parent", "2026-10-29")
        child = self.repo.save_subtask(parent, "Child")
        self.window.refresh()
        item = self.window.tree.topLevelItem(0).child(0)
        self.window.tree.setCurrentItem(item)
        self.window.finish_selected()
        self.assertEqual(self.repo.task(parent)["completed"], 0)
        self.assertEqual(self.repo.subtasks()[parent][0]["completed"], 1)
        self.assertEqual(self.window.selection(), ("subtask", child, parent))

    def test_space_toggles_selected_checkbox(self):
        identity = self.repo.save_task("Task", "2026-10-29")
        self.window.views.setCurrentRow(4)
        self.window.refresh()
        self.window.show()
        self.window.tree.setFocus()
        QTest.keyClick(self.window.tree, Qt.Key.Key_Space)
        self.app.processEvents()
        self.assertEqual(self.repo.task(identity)["completed"], 1)
        self.window.hide()

    def test_delete_confirmation_can_cancel_and_cascade(self):
        identity = self.repo.save_task("Parent", "2026-10-29")
        self.repo.save_subtask(identity, "Child")
        self.window.refresh()
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.No):
            self.window.delete_selected()
        self.assertEqual(self.titles(), ["Parent"])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window.delete_selected()
        self.assertEqual(self.titles(), [])
        self.assertEqual(self.repo.subtasks(), {})


if __name__ == "__main__":
    unittest.main()
