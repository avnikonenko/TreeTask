# TreeTask
TreeTask is a Streamlit-based task manager that grows a plant as you complete your tasks. Each completed task brings the plant closer to full bloom, giving a visual sense of accomplishment. Users can create tasks and nested subtasks, filter them by period (today, this week, completed, ongoing, or all), and track completion using a progress percentage. Data persistence is handled by a lightweight SQLite database stored in the user’s home directory, and a command-line entry point (treetask) launches the Streamlit interface.

## Installation

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

## Requirements

The application depends on [Streamlit](https://streamlit.io/). When installing
via `pip`, the dependency is installed automatically.

## License

Distributed under the terms of the MIT license. See the `LICENSE` file for full
text.
