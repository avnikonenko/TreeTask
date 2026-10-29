"""SQLite storage shared with earlier TreeTask versions."""

from datetime import date, timedelta
from pathlib import Path
import sqlite3


VIEWS = (("today", "Today"), ("week", "This week"), ("completed", "Completed"),
         ("ongoing", "Ongoing"), ("all", "All tasks"))


def split_tags(value):
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def normalize_tags(value):
    unique = {}
    for tag in split_tags(value):
        unique.setdefault(tag.casefold(), tag)
    return ", ".join(unique.values())


class Repository:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        try:
            with self.conn:
                self.conn.execute("BEGIN IMMEDIATE")
                self.conn.execute("""CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY, title TEXT NOT NULL, due_date TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    description TEXT NOT NULL DEFAULT '', tags TEXT NOT NULL DEFAULT '')""")
                self.conn.execute("""CREATE TABLE IF NOT EXISTS subtasks (
                    id INTEGER PRIMARY KEY, task_id INTEGER NOT NULL, title TEXT NOT NULL,
                    completed INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE)""")
                columns = {row[1] for row in self.conn.execute("PRAGMA table_info(tasks)")}
                for column in ("description", "tags"):
                    if column not in columns:
                        self.conn.execute(f"ALTER TABLE tasks ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
        except Exception:
            self.conn.close()
            raise

    def close(self):
        self.conn.close()

    def tasks(self, view="ongoing", query="", tags=(), descending=False, today=None):
        today = today or date.today()
        condition, parameters = "", []
        if view == "today":
            condition, parameters = "WHERE due_date = ?", [today.isoformat()]
        elif view == "week":
            monday = today - timedelta(days=today.weekday())
            condition = "WHERE due_date BETWEEN ? AND ?"
            parameters = [monday.isoformat(), (monday + timedelta(days=6)).isoformat()]
        elif view in ("completed", "ongoing"):
            condition, parameters = "WHERE completed = ?", [int(view == "completed")]
        elif view != "all":
            raise ValueError(f"Unknown view: {view}")
        direction = "DESC" if descending else "ASC"
        rows = self.conn.execute(
            f"SELECT * FROM tasks {condition} ORDER BY due_date {direction}, id ASC", parameters,
        ).fetchall()
        search = query.strip().casefold()
        required = {tag.casefold() for tag in tags}
        return [row for row in rows
                if (not search or any(search in row[field].casefold()
                                      for field in ("title", "description", "tags")))
                and required.issubset({tag.casefold() for tag in split_tags(row["tags"])})]

    def tags(self):
        labels = {}
        for row in self.conn.execute("SELECT tags FROM tasks ORDER BY id"):
            for tag in split_tags(row[0]):
                labels.setdefault(tag.casefold(), tag)
        return {tag: labels[tag] for tag in sorted(labels)}

    def subtasks(self):
        children = {}
        for row in self.conn.execute("SELECT * FROM subtasks ORDER BY task_id, id"):
            children.setdefault(row["task_id"], []).append(row)
        return children

    def task(self, task_id):
        row = self.conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        if row is None:
            raise ValueError("This task no longer exists. Refresh the list.")
        return row

    def save_task(self, title, due_date, description="", tags="", task_id=None):
        title = title.strip()
        if not title:
            raise ValueError("Enter a task title.")
        values = (title, date.fromisoformat(str(due_date)).isoformat(),
                  description.strip(), normalize_tags(tags))
        with self.conn:
            if task_id is None:
                return self.conn.execute(
                    "INSERT INTO tasks(title, due_date, description, tags) VALUES (?, ?, ?, ?)",
                    values,
                ).lastrowid
            self.task(task_id)
            self.conn.execute("UPDATE tasks SET title=?, due_date=?, description=?, tags=? WHERE id=?",
                              values + (task_id,))
        return task_id

    def save_subtask(self, task_id, title, subtask_id=None):
        title = title.strip()
        if not title:
            raise ValueError("Enter a subtask title.")
        with self.conn:
            if subtask_id is None:
                return self.conn.execute("INSERT INTO subtasks(task_id, title) VALUES (?, ?)",
                                         (task_id, title)).lastrowid
            self.conn.execute("UPDATE subtasks SET title=? WHERE id=? AND task_id=?",
                              (title, subtask_id, task_id))
        return subtask_id

    @staticmethod
    def table(kind):
        if kind not in ("task", "subtask"):
            raise ValueError("Unknown task type")
        return "tasks" if kind == "task" else "subtasks"

    def complete(self, kind, identity, completed):
        with self.conn:
            self.conn.execute(f"UPDATE {self.table(kind)} SET completed=? WHERE id=?",
                              (int(completed), identity))

    def delete(self, kind, identity):
        with self.conn:
            self.conn.execute(f"DELETE FROM {self.table(kind)} WHERE id=?", (identity,))
