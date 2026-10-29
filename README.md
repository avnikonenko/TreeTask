# TreeTask

A minimal native desktop task manager, using the same Qt toolkit and compact
layout as Idea. Check off tasks, sort by due date, and watch a small plant grow.
Your descriptions, tags, and subtasks stay in SQLite on your computer.

![Native TreeTask with fictional example tasks](docs/images/main-window.png)

Native window with example tasks, date sorting, tags, and expandable subtasks.

## Quick start

Requires Python 3.10+ and a desktop with Qt support. PySide6 is installed automatically.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/treetask
```

Choose **Today**, **This week**, **Completed**, **Ongoing**, or **All tasks**.
**Ongoing** is the default. Tasks sort by due date; use the date dropdown to reverse
that order. Double-click a task to edit it, or right-click for subtasks and actions.

## Handy shortcuts

| Shortcut | Action |
| --- | --- |
| Ctrl+Alt+Shift+N | Quick-add from any app after [GNOME setup](docs/user-guide.md#panel-icon-and-global-shortcut). |
| Super+Shift+T | Open TreeTask after GNOME setup. |
| Ctrl+N | New task inside TreeTask. |
| Ctrl+Enter | Save the task dialog. |
| Ctrl+W | Close the window to the panel, or cancel a task dialog. |
| Space | Toggle the selected task's checkbox. |

For example: press **Ctrl+Alt+Shift+N**, type a task, then **Ctrl+Enter** to save.

See the [user guide](docs/user-guide.md) for desktop installation, shortcuts,
search, tags, existing-data compatibility, and development checks.

[MIT license](LICENSE).
