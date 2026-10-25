"""Streamlit interface for the TreeTask productivity app.

The application lets users track tasks and subtasks and visualises their
completion progress as a growing plant.
"""

import streamlit as st
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from contextlib import closing
import threading

# Page config for wide layout
st.set_page_config(
    page_title="TreeTask", page_icon=str(Path(__file__).with_name("icon.svg")),
    layout="wide",
)

st.markdown("""
<style>
    .stMainBlockContainer { max-width: 1100px; padding-top: 4rem; padding-bottom: 2rem; }
    [data-testid="stSidebar"] { min-width: 240px; max-width: 240px; }
    [data-testid="stVerticalBlock"] { gap: 0.6rem; }
    [data-testid="stSidebar"] [data-testid="stImage"] { margin: 0 auto; }
    [data-testid="stCaptionContainer"] p { font-size: 0.8rem; }
    .st-key-finish_task_btn [aria-label^="Shortcut "] { display: none; }
</style>
""", unsafe_allow_html=True)

# Database path and lock for thread-safety
# Store the database in the user's configuration directory instead of the
# package directory so installed packages remain read‑only.
DB_PATH = Path.home() / ".treetask" / "tasks.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
DB_LOCK = threading.Lock()

# Database helper class
def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def close_connection(conn):
    conn.commit()
    conn.close()

# Initialize DB schema
conn = get_connection()
#           created_date TEXT NOT NULL,

with DB_LOCK, closing(conn.cursor()) as cur:
    # Serialize schema checks and migrations across browser sessions/processes.
    cur.execute("BEGIN IMMEDIATE")
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            description TEXT NOT NULL DEFAULT '',
            tags TEXT NOT NULL DEFAULT ''
        )''')
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )''')
    columns = {row[1] for row in cur.execute("PRAGMA table_info(tasks)")}
    for column in ("description", "tags"):
        if column not in columns:
            cur.execute(f"ALTER TABLE tasks ADD COLUMN {column} TEXT NOT NULL DEFAULT ''")
close_connection(conn)

def normalize_tags(value):
    tags = []
    seen = set()
    for tag in value.split(","):
        tag = tag.strip()
        if tag and tag.casefold() not in seen:
            tags.append(tag)
            seen.add(tag.casefold())
    return ", ".join(tags)


def add_task(title, due_date, description="", tags=""):
    conn = get_connection()
    with DB_LOCK, closing(conn.cursor()) as cur:
        cur.execute(
            "INSERT INTO tasks (title, due_date, description, tags) VALUES (?, ?, ?, ?)",
            (title.strip(), due_date.isoformat(), description.strip(), normalize_tags(tags)),
        )
    close_connection(conn)


@st.dialog("New task")
def new_task_dialog():
    with st.form("new_task_dialog", clear_on_submit=True):
        title = st.text_input("Task title")
        due_date = st.date_input("Task date", date.today())
        description = st.text_area("Description", key="new_task_description")
        tags = st.text_input("Tags", placeholder="work, personal", key="new_task_tags",
                             help="Separate tags with commas.")
        submitted = st.form_submit_button("Add task", key="dialog_add_task_btn")
    if submitted:
        if title.strip():
            add_task(title, due_date, description, tags)
            st.rerun()
        else:
            st.error("Enter task title")


# Compact toolbar and view navigation.
with st.container(horizontal=True, vertical_alignment="center"):
    st.markdown("**TreeTask**", width="content")
    query = st.text_input(
        "Search tasks", placeholder="Search tasks…", label_visibility="collapsed",
        key="task_search",
    )
    if st.button("+ New task", key="new_task_dialog_btn", shortcut="Alt+Shift+N"):
        new_task_dialog()

with st.sidebar:
    period = st.radio(
        "View", ("today", "week", "completed", "ongoing", "all"),
        index=3,
        format_func=lambda value: {"today": "Today", "week": "This week",
                                  "completed": "Completed", "ongoing": "Ongoing",
                                  "all": "All tasks"}[value],
        key="period_select", label_visibility="collapsed",
    )
    plant = st.container()

# Fetch tasks for period
today = date.today()

conn = get_connection()
with DB_LOCK, closing(conn.cursor()) as cur:
    condition = ""
    if period in ["week", "today"]:
        cutoff_lower = today - timedelta(days=7) if period == "week" else today
        cutof_upper = today + timedelta(days=7) if period == "week" else today
        condition = (f"WHERE due_date >= '{cutoff_lower.isoformat()}' "
                   f"AND due_date <= '{cutof_upper.isoformat()}'")

    if period == "completed":
        condition = 'WHERE completed = 1'
    
    if period == "ongoing":
        condition = 'WHERE completed = 0'

    if period == "all":
        condition = ""
    
    cur.execute(f"SELECT id, title, due_date, completed, description, tags FROM tasks {condition}")
    tasks = cur.fetchall()
    
close_connection(conn)

# Search within the selected view, leaving its progress calculation unchanged.
if query.strip():
    search = query.strip().casefold()
    tasks = [task for task in tasks
             if any(search in field.casefold() for field in (task[1], task[4], task[5]))]
st.caption(f"{len(tasks)} task{'s' if len(tasks) != 1 else ''}")
if not tasks:
    st.caption("No matching tasks." if query.strip() else "No tasks here. Add a task to get started.")

unfinished = {task[0]: task[1] for task in tasks if not task[3]}
if unfinished:
    keyboard_actions = st.sidebar.expander("Keyboard actions")
    selected_task = keyboard_actions.selectbox(
        "Task to finish", list(unfinished),
        format_func=lambda task_id: f"{unfinished[task_id]} (#{task_id})",
        key="task_to_finish",
    )
    if keyboard_actions.button(
        "Finish selected task", key="finish_task_btn", shortcut="Alt+Shift+D",
        width="stretch", help="Finish selected task (Alt+Shift+D)",
    ):
        conn = get_connection()
        with DB_LOCK, closing(conn.cursor()) as cur:
            cur.execute("UPDATE tasks SET completed = 1 WHERE id = ?", (selected_task,))
        close_connection(conn)
        # Keep the existing checkbox from restoring its stale unchecked value.
        st.session_state.pop(f"task_cb_{selected_task}", None)
        st.rerun()

# Iterate through tasks
for task_id, title, due_str, completed, description, tags in tasks:
    cols = st.columns([6, 2, 0.65, 0.65], vertical_alignment="center")
    # Completion toggle
    checked = cols[0].checkbox(
        title, value=bool(completed), key=f"task_cb_{task_id}"
    )
    if checked != bool(completed):
        conn = get_connection()
        with DB_LOCK, closing(conn.cursor()) as cur:
            cur.execute(
                "UPDATE tasks SET completed = ? WHERE id = ?",
                (1 if checked else 0, task_id)
            )
            conn.commit()
        close_connection(conn)
        st.rerun()

    # Title display
    cols[1].caption(date.fromisoformat(due_str).strftime("%d %b %Y"))
    if tags:
        cols[0].caption(tags)

    # Buttons and state keys
    state_key = f"edit_mode_task_{task_id}"
    btn_key = f"edit_task_btn_{task_id}"
    del_key = f"del_task_btn_{task_id}"

    # Edit button
    if cols[2].button("", icon=":material/edit:", help="Edit task", key=btn_key):
        st.session_state[state_key] = True
        st.rerun()
    # Delete button
    if cols[3].button("", icon=":material/delete:", help="Delete task", key=del_key):
        conn = get_connection()
        with DB_LOCK, closing(conn.cursor()) as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        close_connection(conn)
        st.rerun()

    # Edit form
    if st.session_state.get(state_key, False):
        cols = st.columns([4, 4, 1, 1])
        new_t = cols[0].text_input("New title", value=title, key=f"new_task_title_{task_id}")
        new_d = cols[1].date_input("New date", value=date.fromisoformat(due_str), key=f"new_task_date_{task_id}")
        new_description = st.text_area("Description", value=description,
                                       key=f"task_description_{task_id}")
        new_tags = st.text_input("Tags", value=tags, key=f"task_tags_{task_id}",
                                 help="Separate tags with commas.")
        save_key = f"save_task_btn_{task_id}"
        cancel_key = f"cancel_task_btn_{task_id}"
        if cols[2].button("Save", key=save_key):
            conn = get_connection()
            with DB_LOCK, closing(conn.cursor()) as cur:
                cur.execute(
                    "UPDATE tasks SET title = ?, due_date = ?, description = ?, tags = ? WHERE id = ?",
                    (new_t.strip(), new_d.isoformat(), new_description.strip(),
                     normalize_tags(new_tags), task_id)
                )
                conn.commit()
            close_connection(conn)
            del st.session_state[state_key]
            st.rerun()
        if cols[3].button("Cancel", key=cancel_key):
            del st.session_state[state_key]
            st.rerun()

    # Fetch subtasks
    conn = get_connection()
    with DB_LOCK, closing(conn.cursor()) as cur:
        cur.execute(
            "SELECT id, title, completed FROM subtasks WHERE task_id = ?",
            (task_id,)
        )
        subtasks = cur.fetchall()
    close_connection(conn)

    details_label = f"Details · {len(subtasks)} subtasks" if description else f"Subtasks · {len(subtasks)}"
    with st.expander(details_label, expanded=False):
        if description:
            st.text(description)
        # Display each subtask
        for sub_id, sub_title, sub_completed in subtasks:
            sub_cols = st.columns([6, 2, 1, 1], vertical_alignment="center")
            sc_key = f"sub_cb_{task_id}_{sub_id}"
            sc = sub_cols[0].checkbox(
                sub_title, value=bool(sub_completed), key=sc_key
            )
            if sc != bool(sub_completed):
                conn = get_connection()
                with DB_LOCK, closing(conn.cursor()) as cur:
                    cur.execute(
                        "UPDATE subtasks SET completed = ? WHERE id = ?",
                        (1 if sc else 0, sub_id)
                    )
                    conn.commit()
                close_connection(conn)
                st.rerun()

            # Subtask edit
            sub_state = f"edit_mode_sub_{task_id}_{sub_id}"
            sub_btn = f"edit_sub_btn_{task_id}_{sub_id}"
            del_sub_btn = f"del_sub_btn_{task_id}_{sub_id}"
            if sub_cols[2].button("Edit", key=sub_btn):
                st.session_state[sub_state] = True
                st.rerun()
            if st.session_state.get(sub_state, False):
                sub_cols = st.columns([1, 6, 1, 1])
                new_st = sub_cols[1].text_input(
                    "New subtask title", value=sub_title, key=f"new_subtitle_{task_id}_{sub_id}"
                )
                save_sub = f"save_sub_btn_{task_id}_{sub_id}"
                cancel_sub = f"cancel_sub_btn_{task_id}_{sub_id}"
                if sub_cols[2].button("Save", key=save_sub):
                    conn = get_connection()
                    with DB_LOCK, closing(conn.cursor()) as cur:
                        cur.execute(
                            "UPDATE subtasks SET title = ? WHERE id = ?",
                            (new_st.strip(), sub_id)
                        )
                        conn.commit()
                    close_connection(conn)
                    del st.session_state[sub_state]
                    st.rerun()
                if sub_cols[3].button("Cancel", key=cancel_sub):
                    del st.session_state[sub_state]
                    st.rerun()
            else:
                if sub_cols[3].button("Delete", key=del_sub_btn):
                    conn = get_connection()
                    with DB_LOCK, closing(conn.cursor()) as cur:
                        cur.execute("DELETE FROM subtasks WHERE id = ?", (sub_id,))
                        conn.commit()
                    close_connection(conn)
                    st.rerun()

        # Add Subtask Form
        form = st.form(key=f"add_sub_form_{task_id}")
        new_sub = form.text_input("Subtask Title", key=f"new_sub_{task_id}")
        if form.form_submit_button("Add Subtask"):
            if new_sub.strip():
                conn = get_connection()
                with DB_LOCK, closing(conn.cursor()) as cur:
                    cur.execute(
                        "INSERT INTO subtasks (task_id, title) VALUES (?, ?)",
                        (task_id, new_sub.strip())
                    )
                    conn.commit()
                close_connection(conn)
                st.rerun()
            else:
                st.error("Enter subtask title")

# Progress calculation using DB
conn = get_connection()
with DB_LOCK, closing(conn.cursor()) as cur:
    
    cur.execute(f"SELECT COUNT(*) FROM tasks {condition}")
    total_tasks = cur.fetchone()[0]
    
    if period == 'all':   
        cur.execute("SELECT COUNT(*) FROM tasks WHERE completed = 1")
    else:
        cur.execute(f"SELECT COUNT(*) FROM tasks {condition} AND completed = 1")
    completed_tasks = cur.fetchone()[0]
    
close_connection(conn)

progress_pct = int((completed_tasks / (total_tasks or 1)) * 100)
stage = min(progress_pct // 20, 5)
img_path = Path(__file__).parent / f"plant_stage{stage}.png"
with plant:
    st.image(str(img_path), width=140)
    st.progress(progress_pct / 100)
    st.caption(f"{completed_tasks} of {total_tasks} complete · {progress_pct}%")
