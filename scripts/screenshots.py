"""Render the native UI with fictional data; never reads the user's database.

Run with QT_QPA_PLATFORM=offscreen .venv/bin/python scripts/screenshots.py.
"""

from datetime import date
from pathlib import Path
import tempfile

from PySide6.QtCore import QCoreApplication, QEvent, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from treetask.repository import Repository
from treetask.ui import MainWindow, TaskDialog, apply_theme


def main():
    root = Path(__file__).resolve().parents[1]
    app = QApplication([])
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(str(root / "treetask/icon.svg")))
    apply_theme(app)
    with tempfile.TemporaryDirectory() as directory:
        repo = Repository(Path(directory) / "example.db")
        try:
            first = repo.save_task("Plan a quiet weekend", date(2026, 10, 31),
                                   "Pick a walking route and leave an afternoon free for reading.",
                                   "personal, weekend")
            repo.save_subtask(first, "Choose a walking route")
            child = repo.save_subtask(first, "Pack a book")
            repo.complete("subtask", child, True)
            repo.save_task("Finish the reading notes", date(2026, 11, 1),
                           "Summarize the last chapter and keep three useful ideas.", "learning")
            repo.save_task("Prepare Monday's priorities", date(2026, 11, 2),
                           "Choose three tasks to focus on next week.", "work, planning")
            done = repo.save_task("Water the balcony plants", date(2026, 10, 29), tags="home")
            repo.complete("task", done, True)
            done = repo.save_task("Clear the inbox", date(2026, 10, 30), tags="work")
            repo.complete("task", done, True)
            window = MainWindow(repo)
            window.views.setCurrentRow(4)
            window.resize(1000, 620)
            for i in range(window.tree.topLevelItemCount()):
                item = window.tree.topLevelItem(i)
                if item.data(0, Qt.ItemDataRole.UserRole)[1] == first:
                    item.setExpanded(True)
                    window.tree.setCurrentItem(item)
            window.show()
            app.processEvents()
            destination = root / "docs/images"
            destination.mkdir(parents=True, exist_ok=True)
            if not window.grab().save(str(destination / "main-window.png")):
                raise RuntimeError("Could not save main window screenshot")
            dialog = TaskDialog(repo, repo.task(first), window)
            dialog.show()
            app.processEvents()
            if not dialog.grab().save(str(destination / "task-dialog.png")):
                raise RuntimeError("Could not save task editor screenshot")
            dialog.close()
            dialog.deleteLater()
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            print("Rendered fictional examples in docs/images/")
        finally:
            repo.close()


if __name__ == "__main__":
    main()
