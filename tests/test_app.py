import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from streamlit.testing.v1 import AppTest


APP = Path(__file__).resolve().parents[1] / "treetask/app.py"


class TaskActionsTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        home_patch = patch.object(Path, "home", return_value=self.home)
        home_patch.start()
        self.addCleanup(home_patch.stop)
        self.app = AppTest.from_file(str(APP)).run()
        self.assertFalse(self.app.exception)

    def rows(self):
        with closing(sqlite3.connect(self.home / ".treetask/tasks.db")) as conn:
            return conn.execute("SELECT title, completed FROM tasks ORDER BY id").fetchall()

    def add_task(self, title):
        self.app.button(key="new_task_dialog_btn").click().run()
        next(widget for widget in self.app.text_input if widget.label == "Task title").set_value(title)
        self.app.button(key="new_task_dialog_btn").click()
        self.app.button(key="dialog_add_task_btn").click().run()
        self.assertFalse(self.app.exception)

    def test_add_and_finish_only_selected_task(self):
        for title in ("First", "Second"):
            self.add_task(title)
        self.app.selectbox(key="task_to_finish").select(2).run()
        finish = next(button for button in self.app.button if button.label == "Finish selected task")
        finish.click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.rows(), [("First", 0), ("Second", 1)])
        self.assertEqual(self.app.selectbox(key="task_to_finish").options, ["First (#1)"])

    def test_dialog_add_and_empty_title(self):
        self.app.button(key="new_task_dialog_btn").click().run()
        title = next(widget for widget in self.app.text_input if widget.label == "Task title")
        title.set_value("   ")
        submit = next(button for button in self.app.button if button.label == "Add task")
        # AppTest reruns the full script rather than just the dialog fragment.
        self.app.button(key="new_task_dialog_btn").click()
        submit.click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.rows(), [])
        self.assertTrue(self.app.error)
        title = next(widget for widget in self.app.text_input if widget.label == "Task title")
        title.set_value("  Dialog task  ")
        submit = next(button for button in self.app.button if button.label == "Add task")
        self.app.button(key="new_task_dialog_btn").click()
        submit.click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.rows(), [("Dialog task", 0)])

    def test_no_finish_action_when_no_unfinished_tasks(self):
        self.assertFalse(any(button.label == "Finish selected task" for button in self.app.button))
        self.assertFalse(any(expander.label == "Keyboard actions" for expander in self.app.expander))

    def test_finish_controls_disappear_after_last_task_completed(self):
        self.add_task("Only task")
        self.assertTrue(any(expander.label == "Keyboard actions" for expander in self.app.expander))
        self.app.button(key="finish_task_btn").click().run()
        self.assertFalse(self.app.exception)
        self.assertFalse(any(expander.label == "Keyboard actions" for expander in self.app.expander))

    def test_search_and_view_filters(self):
        self.add_task("First task")
        self.add_task("Second task")
        self.app.text_input(key="task_search").set_value("SECOND").run()
        self.assertFalse(self.app.exception)
        self.assertEqual([widget.label for widget in self.app.checkbox], ["Second task"])
        self.app.radio(key="period_select").set_value("completed").run()
        self.assertFalse(self.app.exception)
        self.assertFalse(self.app.checkbox)
        self.assertEqual(self.rows(), [("First task", 0), ("Second task", 0)])

    def test_edit_subtask_and_delete_remain_available(self):
        self.add_task("Parent")
        self.app.button(key="edit_task_btn_1").click().run()
        self.app.text_input(key="new_task_title_1").set_value("Edited")
        self.app.button(key="save_task_btn_1").click().run()
        self.assertEqual(self.rows(), [("Edited", 0)])
        self.app.text_input(key="new_sub_1").set_value("Child")
        self.app.button(key="FormSubmitter:add_sub_form_1-Add Subtask").click().run()
        self.assertFalse(self.app.exception)
        self.app.checkbox(key="sub_cb_1_1").check().run()
        self.app.button(key="edit_sub_btn_1_1").click().run()
        self.app.text_input(key="new_subtitle_1_1").set_value("Edited child")
        self.app.button(key="save_sub_btn_1_1").click().run()
        self.assertFalse(self.app.exception)
        with closing(sqlite3.connect(self.home / ".treetask/tasks.db")) as conn:
            self.assertEqual(conn.execute("SELECT title, completed FROM subtasks").fetchall(),
                             [("Edited child", 1)])
        self.app.button(key="del_task_btn_1").click().run()
        self.assertFalse(self.app.exception)
        self.assertEqual(self.rows(), [])


if __name__ == "__main__":
    unittest.main()
