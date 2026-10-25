# TreeTask
TreeTask is a Streamlit-based task manager that grows a plant as you complete your tasks. Each completed task brings the plant closer to full bloom, giving a visual sense of accomplishment. Users can create tasks and nested subtasks, filter them by period (today, this week, completed, ongoing, or all), and track completion using a progress percentage. Data persistence is handled by a lightweight SQLite database stored in the user’s home directory, and a command-line entry point (treetask) launches the Streamlit interface.

## Installation

Requires Python 3.10 or newer and Streamlit 1.52 or newer (for native keyboard
shortcuts).

From a local clone of the repository:

```bash
pip install .
```

## Usage

After installation you can launch the application with:

```bash
treetask
```

Alternatively use the module or Streamlit directly:

```bash
python -m treetask
streamlit run treetask/app.py
```

## Keyboard shortcuts

These shortcuts work while the TreeTask browser page has focus:

| Shortcut | Action |
| --- | --- |
| Alt+Shift+N | Open the new-task dialog. |
| Ctrl+Enter | Submit the new-task dialog while editing its form. |
| Alt+Shift+D | Mark the task chosen in **Task to finish** as completed. |

The completion selector under **Keyboard actions** lists unfinished tasks in the
current view and search. The section appears only when there are unfinished tasks.
Completing
a parent task does not automatically complete its subtasks; their existing Done
checkboxes remain independent.

## Compact interface

Use **+ New task** in the top toolbar to add a task. Search filters task titles
within the selected sidebar view. Each row has a completion checkbox, a due date,
and edit/delete icons; expand **Subtasks** to add or manage its subtasks.

The sidebar holds a small 140-pixel plant and progress for the entire selected
period, independent of the search text. The layout follows Idea's compact toolbar
and navigation style while remaining a browser-based Streamlit app.

## Requirements

The application depends on [Streamlit](https://streamlit.io/). When installing
via `pip`, the dependency is installed automatically.

## Validation

With the package dependencies installed, run `python -m unittest discover -s tests -v`.
The tests use a temporary database and leave your tasks untouched.

## License

Distributed under the terms of the MIT license. See the `LICENSE` file for full
text.
