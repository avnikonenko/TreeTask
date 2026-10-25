# TreeTask

A small, local task manager with descriptions, tags, and subtasks. Complete tasks
and watch your plant grow. Tasks stay in SQLite on your computer.

![TreeTask in dark mode with fictional example tasks](docs/images/main-window.png)

## Quick start

Requires Python 3.10+. Streamlit is installed automatically.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install .
.venv/bin/treetask
```

For a Linux application-menu launcher, run `python3 scripts/install-desktop.py`.
Optional GNOME panel and global-shortcut setup is covered in the guide.

Start in **Ongoing**, add tasks with **Alt+Shift+N**, and search titles,
descriptions, or tags. Expand **Details** for descriptions and subtasks.

See the [user guide](docs/user-guide.md) for desktop setup, all shortcuts,
updates, data locations, and development checks. The screenshot uses sample data.

[MIT license](LICENSE).
