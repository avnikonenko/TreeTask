import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path

from treetask.repository import Repository, normalize_tags


class RepositoryTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / "tasks.db"
        self.repo = Repository(self.path)
        self.addCleanup(self.repo.close)

    def test_create_edit_and_clear_metadata(self):
        identity = self.repo.save_task("  Trip  ", date(2026, 10, 29), "  Cabin\nMaps  ",
                                       " Travel, Weekend, TRAVEL, , weekend ")
        task = self.repo.task(identity)
        self.assertEqual((task["title"], task["description"], task["tags"]),
                         ("Trip", "Cabin\nMaps", "Travel, Weekend"))
        self.repo.save_task("Edited", "2026-11-01", task_id=identity)
        task = self.repo.task(identity)
        self.assertEqual((task["title"], task["due_date"], task["description"], task["tags"]),
                         ("Edited", "2026-11-01", "", ""))
        self.assertEqual(normalize_tags("Straße, STRASSE"), "Straße")

    def test_rejects_empty_title_and_invalid_date_without_writing(self):
        for title, due in ((" ", "2026-10-29"), ("Task", "not-a-date")):
            with self.assertRaises(ValueError):
                self.repo.save_task(title, due)
        self.assertEqual(self.repo.tasks("all"), [])
        with self.assertRaises(ValueError):
            self.repo.save_subtask(1, " ")

    def test_date_sort_is_stable_in_both_directions(self):
        for title, due in (("Later", "2026-11-01"), ("Earlier", "2026-10-01"),
                           ("Same date", "2026-10-01")):
            self.repo.save_task(title, due)
        self.assertEqual([row["title"] for row in self.repo.tasks()],
                         ["Earlier", "Same date", "Later"])
        self.assertEqual([row["title"] for row in self.repo.tasks(descending=True)],
                         ["Later", "Earlier", "Same date"])

    def test_views_use_calendar_week_including_year_boundary(self):
        for day in ("2025-12-28", "2025-12-29", "2025-12-31", "2026-01-04", "2026-01-05"):
            self.repo.save_task(day, day)
        today = date(2025, 12, 31)
        self.assertEqual([row["title"] for row in self.repo.tasks("today", today=today)], ["2025-12-31"])
        self.assertEqual([row["title"] for row in self.repo.tasks("week", today=today)],
                         ["2025-12-29", "2025-12-31", "2026-01-04"])
        self.repo.complete("task", 3, True)
        self.assertEqual(len(self.repo.tasks("ongoing")), 4)
        self.assertEqual(len(self.repo.tasks("completed")), 1)
        self.assertEqual(len(self.repo.tasks("all")), 5)
        with self.assertRaises(ValueError):
            self.repo.tasks("invalid")

    def test_search_and_all_tag_matching_are_case_insensitive(self):
        self.repo.save_task("Report", "2026-10-29", "Quarterly numbers", "Work, urgent")
        self.repo.save_task("Desk", "2026-10-29", tags="work")
        self.repo.save_task("Bench", "2026-10-29", tags="woodwork, urgent")
        self.assertEqual([row["title"] for row in self.repo.tasks(tags=["WORK"])], ["Report", "Desk"])
        self.assertEqual([row["title"] for row in self.repo.tasks(tags=["work", "urgent"])], ["Report"])
        self.assertEqual([row["title"] for row in self.repo.tasks(query="NUMBERS", tags=["work"])], ["Report"])
        self.assertEqual([row["title"] for row in self.repo.tasks(query="urgent")], ["Report", "Bench"])
        self.assertEqual(self.repo.tasks(query="missing", tags=["work"]), [])
        self.assertEqual(self.repo.tags(), {"urgent": "urgent", "woodwork": "woodwork", "work": "Work"})

    def test_subtask_completion_is_independent_and_delete_cascades(self):
        parent = self.repo.save_task("Parent", "2026-10-29")
        child = self.repo.save_subtask(parent, "Child")
        self.repo.complete("subtask", child, True)
        self.assertEqual(self.repo.task(parent)["completed"], 0)
        self.repo.save_subtask(parent, "Changed", child)
        self.assertEqual(self.repo.subtasks()[parent][0]["title"], "Changed")
        self.repo.complete("task", parent, True)
        self.repo.complete("task", parent, False)
        self.assertEqual(self.repo.subtasks()[parent][0]["completed"], 1)
        self.repo.delete("task", parent)
        self.assertEqual(self.repo.subtasks(), {})
        with self.assertRaises(sqlite3.IntegrityError):
            self.repo.save_subtask(parent, "Orphan")

    def test_migrates_legacy_database_without_losing_records(self):
        legacy = self.path.with_name("legacy.db")
        connection = sqlite3.connect(legacy)
        try:
            connection.executescript("""
                CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL,
                    due_date TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE subtasks (id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL,
                    title TEXT NOT NULL, completed INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE);
                INSERT INTO tasks VALUES (42, 'Existing', '2026-01-01', 0);
                INSERT INTO subtasks VALUES (7, 42, 'Child', 1);
            """)
        finally:
            connection.close()
        for _ in range(2):
            migrated = Repository(legacy)
            try:
                self.assertEqual(tuple(migrated.task(42)), (42, "Existing", "2026-01-01", 0, "", ""))
                self.assertEqual(migrated.subtasks()[42][0]["completed"], 1)
            finally:
                migrated.close()


if __name__ == "__main__":
    unittest.main()
