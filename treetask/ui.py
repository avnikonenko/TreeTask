"""Compact Qt task window and task editor."""

import sqlite3
from pathlib import Path

from PySide6.QtCore import QDate, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QKeySequence, QPalette, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFormLayout,
    QHeaderView, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QProgressBar,
    QPushButton, QSplitter, QSystemTrayIcon, QToolButton, QTreeWidget,
    QTreeWidgetItem, QVBoxLayout, QWidget,
)

from .repository import VIEWS


SHORTCUTS = (
    ("Super+Shift+T", "Open TreeTask from any app (after GNOME setup)"),
    ("Ctrl+Alt+Shift+N", "Quick-add a task from any app (after GNOME setup)"),
    ("Ctrl+N / Alt+Shift+N", "New task"),
    ("Ctrl+W", "Close the window; keep running in the panel when available"),
    ("Alt+Shift+D", "Finish selected task or subtask"),
    ("Ctrl+F", "Search tasks"),
    ("Ctrl+Enter", "Save the task dialog"),
    ("Space", "Toggle the selected checkbox"),
)


def apply_theme(app):
    """Use the same restrained dark palette as Idea."""
    colors = {
        QPalette.ColorRole.Window: "#202226", QPalette.ColorRole.WindowText: "#E9EAEE",
        QPalette.ColorRole.Base: "#272A30", QPalette.ColorRole.AlternateBase: "#30343A",
        QPalette.ColorRole.Text: "#E9EAEE", QPalette.ColorRole.Button: "#30343A",
        QPalette.ColorRole.ButtonText: "#E9EAEE", QPalette.ColorRole.Highlight: "#90B7EF",
        QPalette.ColorRole.HighlightedText: "#172337", QPalette.ColorRole.PlaceholderText: "#949BA8",
    }
    palette = QPalette()
    for role, color in colors.items():
        palette.setColor(role, QColor(color))
    app.setPalette(palette)
    app.setStyleSheet("""
        QLineEdit, QPlainTextEdit, QComboBox, QDateEdit {
            padding: 5px; border: 1px solid palette(mid); border-radius: 4px;
        }
        QPushButton { padding: 5px 9px; }
        QToolButton { padding: 4px 8px; }
        QTreeView, QListView { border: 0; }
        QTreeView::item { min-height: 32px; }
        QSplitter::handle { background: palette(mid); width: 1px; }
    """)


class TaskDialog(QDialog):
    def __init__(self, repo, task=None, parent=None):
        super().__init__(parent)
        self.repo = repo
        self.task_id = task["id"] if task is not None else None
        self.saved_id = None
        self.setWindowTitle("Edit task" if task is not None else "New task")
        self.resize(460, 370)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.title = QLineEdit(task["title"] if task is not None else "")
        self.title.setPlaceholderText("What needs doing?")
        self.due = QDateEdit()
        self.due.setCalendarPopup(True)
        self.due.setDisplayFormat("dd MMM yyyy")
        self.due.setDate(QDate.fromString(task["due_date"], "yyyy-MM-dd")
                         if task is not None else QDate.currentDate())
        self.tags = QLineEdit(task["tags"] if task is not None else "")
        self.tags.setPlaceholderText("work, personal")
        form.addRow("Title", self.title)
        form.addRow("Due", self.due)
        form.addRow("Tags", self.tags)
        layout.addLayout(form)
        self.description = QPlainTextEdit(task["description"] if task is not None else "")
        self.description.setPlaceholderText("Description (optional)")
        layout.addWidget(self.description)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save |
                                   QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        close = QShortcut(QKeySequence("Ctrl+W"), self)
        close.activated.connect(self.reject)
        for key in ("Ctrl+Return", "Ctrl+Enter"):
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.activated.connect(self.save)
        self.title.setFocus()

    def save(self):
        try:
            self.saved_id = self.repo.save_task(
                self.title.text(), self.due.date().toPython(), self.description.toPlainText(),
                self.tags.text(), self.task_id,
            )
        except (ValueError, OSError, sqlite3.Error) as exc:
            QMessageBox.warning(self, "Task was not saved", str(exc))
            return
        self.accept()


class MainWindow(QMainWindow):
    def __init__(self, repo):
        super().__init__()
        self.repo = repo
        self.tray = None
        self.quitting = False
        self.task_dialog = None
        self.setWindowTitle("TreeTask")
        self.resize(940, 580)
        self.setMinimumSize(650, 420)
        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)
        top = QHBoxLayout()
        title = QLabel("TreeTask")
        title.setStyleSheet("font-weight: bold; font-size: 18px;")
        top.addWidget(title)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search tasks, descriptions and tags…")
        self.search.setClearButtonEnabled(True)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self.refresh)
        self.search.textChanged.connect(lambda *_: self.search_timer.start())
        top.addWidget(self.search, 1)
        new = QPushButton("+ New task")
        new.clicked.connect(self.new_task)
        top.addWidget(new)
        menu_button = QToolButton()
        menu_button.setText("⋯")
        menu_button.setToolTip("Task actions and keyboard shortcuts")
        menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.actions_menu = QMenu(menu_button)
        self.actions_menu.addAction("Edit selected…", self.edit_selected)
        self.actions_menu.addAction("Add subtask…", self.add_subtask)
        self.actions_menu.addAction("Delete selected…", self.delete_selected)
        self.actions_menu.addSeparator()
        self.actions_menu.addAction("Keyboard shortcuts…", self.show_shortcuts)
        self.actions_menu.addAction("Quit TreeTask", self.quit_app)
        menu_button.setMenu(self.actions_menu)
        top.addWidget(menu_button)
        layout.addLayout(top)
        splitter = QSplitter()
        layout.addWidget(splitter, 1)
        sidebar = QWidget()
        side = QVBoxLayout(sidebar)
        side.setContentsMargins(0, 0, 10, 0)
        self.views = QListWidget()
        for key, label in VIEWS:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.views.addItem(item)
        self.views.setCurrentRow(3)
        self.views.setFixedHeight(175)
        self.views.currentRowChanged.connect(self.refresh)
        side.addWidget(self.views)
        self.tag_label = QLabel("TAGS · match all")
        side.addWidget(self.tag_label)
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(135)
        self.tag_list.itemChanged.connect(lambda *_: self.search_timer.start(0))
        side.addWidget(self.tag_list)
        side.addStretch()
        self.plant = QLabel()
        self.plant.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.plant)
        self.progress = QProgressBar()
        self.progress.setFixedHeight(6)
        self.progress.setTextVisible(False)
        side.addWidget(self.progress)
        self.progress_text = QLabel()
        self.progress_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side.addWidget(self.progress_text)
        sidebar.setMinimumWidth(155)
        sidebar.setMaximumWidth(210)
        splitter.addWidget(sidebar)
        content = QWidget()
        right = QVBoxLayout(content)
        right.setContentsMargins(10, 0, 0, 0)
        heading = QHBoxLayout()
        self.count = QLabel()
        heading.addWidget(self.count, 1)
        self.sort = QComboBox()
        self.sort.addItems(["Due date ↑", "Due date ↓"])
        self.sort.currentIndexChanged.connect(self.refresh)
        heading.addWidget(self.sort)
        right.addLayout(heading)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Task", "Due", "Tags"])
        self.tree.setRootIsDecorated(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.SingleSelection)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        self.tree.setColumnWidth(2, 135)
        self.tree.itemChanged.connect(self.checkbox_changed)
        self.tree.itemDoubleClicked.connect(self.edit_selected)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.context_menu)
        right.addWidget(self.tree)
        self.empty = QLabel("No tasks here. Add a task to get started.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self.empty)
        splitter.addWidget(content)
        splitter.setSizes([175, 740])
        splitter.setStretchFactor(1, 1)
        self.statusBar().showMessage("Double-click to edit · Right-click for task actions")
        for keys, callback in (("Alt+Shift+N", self.new_task), ("Ctrl+N", self.new_task),
                               ("Ctrl+W", self.close),
                               ("Alt+Shift+D", self.finish_selected), ("Ctrl+F", self.search.setFocus)):
            action = QAction(self)
            action.setShortcut(QKeySequence(keys))
            action.triggered.connect(callback)
            self.addAction(action)
        self.refresh()

    def selected_tags(self):
        return [self.tag_list.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.tag_list.count())
                if self.tag_list.item(i).checkState() == Qt.CheckState.Checked]

    def selection(self):
        item = self.tree.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def refresh(self, *_):
        try:
            self._refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Could not load tasks", str(exc))

    def _refresh(self):
        self.search_timer.stop()
        previous = self.selection()
        expanded = {self.tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole)
                    for i in range(self.tree.topLevelItemCount())
                    if self.tree.topLevelItem(i).isExpanded()}
        selected_tags = set(self.selected_tags())
        tag_names = self.repo.tags()
        selected_tags.intersection_update(tag_names)
        with QSignalBlocker(self.tag_list):
            self.tag_list.clear()
            for key, label in tag_names.items():
                item = QListWidgetItem(label)
                item.setData(Qt.ItemDataRole.UserRole, key)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(Qt.CheckState.Checked if key in selected_tags else Qt.CheckState.Unchecked)
                self.tag_list.addItem(item)
        self.tag_list.setVisible(bool(tag_names))
        self.tag_label.setVisible(bool(tag_names))
        view = self.views.currentItem().data(Qt.ItemDataRole.UserRole)
        tasks = self.repo.tasks(view, self.search.text(), selected_tags, bool(self.sort.currentIndex()))
        subtasks = self.repo.subtasks()
        with QSignalBlocker(self.tree):
            self.tree.clear()
            for task in tasks:
                parent = self.add_item(self.tree, task, "task")
                for sub in subtasks.get(task["id"], []):
                    self.add_item(parent, sub, "subtask")
                parent.setExpanded(("task", task["id"], task["id"]) in expanded)
            iterator = self.tree.invisibleRootItem()
            for i in range(iterator.childCount()):
                item = iterator.child(i)
                candidates = [item] + [item.child(j) for j in range(item.childCount())]
                for candidate in candidates:
                    if candidate.data(0, Qt.ItemDataRole.UserRole) == previous:
                        self.tree.setCurrentItem(candidate)
            if self.tree.currentItem() is None and self.tree.topLevelItemCount():
                self.tree.setCurrentItem(self.tree.topLevelItem(0))
        count = len(tasks)
        self.count.setText(f"{count} task{'s' if count != 1 else ''}")
        self.empty.setVisible(not tasks)
        period_tasks = self.repo.tasks(view)
        completed = sum(bool(task["completed"]) for task in period_tasks)
        percent = int(100 * completed / len(period_tasks)) if period_tasks else 0
        pixmap = QPixmap(str(Path(__file__).with_name(f"plant_stage{min(percent // 20, 5)}.png")))
        self.plant.setPixmap(pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio,
                                          Qt.TransformationMode.SmoothTransformation))
        self.progress.setValue(percent)
        self.progress_text.setText(f"{completed} of {len(period_tasks)} complete")

    def add_item(self, parent, record, kind):
        due = QDate.fromString(record["due_date"], "yyyy-MM-dd").toString("dd MMM yyyy") if kind == "task" else ""
        item = QTreeWidgetItem(parent, [record["title"], due, record["tags"] if kind == "task" else ""])
        parent_id = record["id"] if kind == "task" else record["task_id"]
        item.setData(0, Qt.ItemDataRole.UserRole, (kind, record["id"], parent_id))
        item.setCheckState(0, Qt.CheckState.Checked if record["completed"] else Qt.CheckState.Unchecked)
        item.setToolTip(0, record["description"] if kind == "task" else record["title"])
        if record["completed"]:
            font = item.font(0)
            font.setStrikeOut(True)
            item.setFont(0, font)
        return item

    def change(self, operation):
        try:
            operation()
        except Exception as exc:
            QMessageBox.warning(self, "Task change failed", str(exc))
        self.refresh()

    def checkbox_changed(self, item, column):
        if column == 0:
            kind, identity, _ = item.data(0, Qt.ItemDataRole.UserRole)
            checked = item.checkState(0) == Qt.CheckState.Checked
            try:
                self.repo.complete(kind, identity, checked)
            except Exception as exc:
                QMessageBox.warning(self, "Task change failed", str(exc))
            # Do not delete/rebuild tree items inside their itemChanged signal.
            self.search_timer.start(0)

    def finish_selected(self):
        selected = self.selection()
        if selected:
            self.change(lambda: self.repo.complete(selected[0], selected[1], True))

    def new_task(self, *_):
        if self.task_dialog is not None:
            self.task_dialog.showNormal()
            self.task_dialog.raise_()
            self.task_dialog.activateWindow()
            return
        dialog = TaskDialog(self.repo, parent=self)
        self.task_dialog = dialog
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self.refresh()
        finally:
            self.task_dialog = None
            dialog.deleteLater()

    def edit_selected(self, *_):
        selected = self.selection()
        if not selected:
            return
        kind, identity, parent_id = selected
        if kind == "task":
            try:
                task = self.repo.task(identity)
            except Exception as exc:
                QMessageBox.warning(self, "Could not open task", str(exc))
                return
            if TaskDialog(self.repo, task, self).exec() == QDialog.DialogCode.Accepted:
                self.refresh()
        else:
            title, ok = QInputDialog.getText(self, "Edit subtask", "Title", text=self.tree.currentItem().text(0))
            if ok:
                self.change(lambda: self.repo.save_subtask(parent_id, title, identity))

    def add_subtask(self):
        selected = self.selection()
        if selected:
            title, ok = QInputDialog.getText(self, "New subtask", "Title")
            if ok:
                self.change(lambda: self.repo.save_subtask(selected[2], title))

    def delete_selected(self):
        selected = self.selection()
        if not selected:
            return
        answer = QMessageBox.question(self, "Delete task?", "Delete the selected item? Deleting a task also removes its subtasks.",
                                      QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                      QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            self.change(lambda: self.repo.delete(selected[0], selected[1]))

    def context_menu(self, position):
        item = self.tree.itemAt(position)
        if item:
            self.tree.setCurrentItem(item)
            self.actions_menu.exec(self.tree.viewport().mapToGlobal(position))

    def show_shortcuts(self):
        QMessageBox.information(self, "Keyboard shortcuts", "\n\n".join(f"{key} — {label}" for key, label in SHORTCUTS))

    def open_window(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self.refresh()

    def closeEvent(self, event):
        if not self.quitting and self.tray and QSystemTrayIcon.isSystemTrayAvailable():
            self.hide()
            event.ignore()
        else:
            event.accept()

    def quit_app(self):
        self.quitting = True
        QApplication.instance().quit()
