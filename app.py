import sys
import streamlit as st
import sqlite3
from datetime import date, timedelta
from pathlib import Path
import atexit
from contextlib import closing
import threading
import streamlit.components.v1 as components

# Page config for wide layout
st.set_page_config(page_title="TaskPlantApp", layout="wide")

# Database path and lock for thread-safety
DB_PATH = Path(__file__).with_name('tasks.db')
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
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            due_date TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0
        )''')
    cur.execute(
        '''CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY,
            task_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
        )''')
close_connection(conn)

# Sidebar: Exit and Add Task
def exit_app():
    # Close tab
    components.html("<script>window.close();</script>", height=0)
    st.stop()

with st.sidebar:
    if st.button("Exit", key="exit_btn", on_click=exit_app):
        pass
    st.title("Task Period")
    period = st.selectbox("Select period", ("today", "week", "completed", "ongoing", "all"), key="period_select")
    st.title("Add Task")
    new_title = st.text_input("Task Title", key="new_task_title")
    new_date = st.date_input("Task Date", date.today(), key="new_task_date")
    if st.button("Add Task", key="add_task_btn"):
        if new_title.strip():
            conn = get_connection()
            with DB_LOCK, closing(conn.cursor()) as cur:
                cur.execute(
                    "INSERT INTO tasks (title, due_date) VALUES (?, ?)",
                    (new_title.strip(), new_date.isoformat())
                )
                conn.commit()
            close_connection(conn)
            st.rerun()
        else:
            st.error("Enter task title")

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
    
    cur.execute(f"SELECT id, title, due_date, completed FROM tasks {condition}")
    tasks = cur.fetchall()
    
close_connection(conn)

# Display header
st.header(f"Tasks for the {period}")

# Iterate through tasks
for task_id, title, due_str, completed in tasks:
    cols = st.columns([1, 5, 1, 1])
    # Completion toggle
    checked = cols[0].checkbox(
        "Done", value=bool(completed), key=f"task_cb_{task_id}", label_visibility="hidden"
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
    cols[1].markdown(f"**{title}** (created {due_str})", unsafe_allow_html=True)

    # Buttons and state keys
    state_key = f"edit_mode_task_{task_id}"
    btn_key = f"edit_task_btn_{task_id}"
    del_key = f"del_task_btn_{task_id}"

    # Edit button
    if cols[2].button("Edit", key=btn_key):
        st.session_state[state_key] = True
        st.rerun()
    # Delete button
    if cols[3].button("Delete", key=del_key):
        conn = get_connection()
        with DB_LOCK, closing(conn.cursor()) as cur:
            cur.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
            conn.commit()
        close_connection(conn)
        st.rerun()

    # Edit form
    if st.session_state.get(state_key, False):
        new_t = cols[1].text_input("New title", value=title, key=f"new_task_title_{task_id}")
        new_d = cols[1].date_input("New date", value=date.fromisoformat(due_str), key=f"new_task_date_{task_id}")
        save_key = f"save_task_btn_{task_id}"
        cancel_key = f"cancel_task_btn_{task_id}"
        if cols[2].button("Save", key=save_key):
            conn = get_connection()
            with DB_LOCK, closing(conn.cursor()) as cur:
                cur.execute(
                    "UPDATE tasks SET title = ?, due_date = ? WHERE id = ?",
                    (new_t.strip(), new_d.isoformat(), task_id)
                )
                conn.commit()
            close_connection(conn)
            del st.session_state[state_key]
            st.rerun()
        if cols[3].button("Cancel", key=cancel_key):
            del st.session_state[state_key]
            st.rerun()

    # Subtasks header
    cols[1].markdown(
        f"<div style='margin-left:6rem; color: blue;'><u>Subtasks:</u></div>",
        unsafe_allow_html=True
    )

    # Fetch subtasks
    conn = get_connection()
    with DB_LOCK, closing(conn.cursor()) as cur:
        cur.execute(
            "SELECT id, title, completed FROM subtasks WHERE task_id = ?",
            (task_id,)
        )
        subtasks = cur.fetchall()
    close_connection(conn)

    # Display each subtask
    for sub_id, sub_title, sub_completed in subtasks:
        sub_cols = st.columns([1.5, 4, 1, 1])
        sc_key = f"sub_cb_{task_id}_{sub_id}"
        sc = sub_cols[0].checkbox(
            "Done", value=bool(sub_completed), key=sc_key, label_visibility="hidden"
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

        sub_cols[1].markdown(
            f"<div style='text-align:left; color:darkblue; padding-left:10px;'>&bull; {sub_title}</div>",
            unsafe_allow_html=True
        )
        # Subtask edit
        sub_state = f"edit_mode_sub_{task_id}_{sub_id}"
        sub_btn = f"edit_sub_btn_{task_id}_{sub_id}"
        del_sub_btn = f"del_sub_btn_{task_id}_{sub_id}"
        if sub_cols[2].button("Edit", key=sub_btn):
            st.session_state[sub_state] = True
            st.rerun()
        if st.session_state.get(sub_state, False):
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
    with st.expander("Add Subtask", expanded=False):
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
st.write(f"**Task Progress:** {progress_pct}% ({completed_tasks}/{total_tasks})")

# SVG plant based on progress

# SVG stages
stage = min(progress_pct // 20, 5)
img_path = Path(__file__).parent / f"plant_stage{stage}.png"

# display the PNG
st.image(
    str(img_path),
    use_container_width=True,
    #use_column_width=True,  # auto‐scale to container width
    caption=f"Plant at {progress_pct}%"
)
#svg_path = Path(__file__).parent / f"plant_stage{stage}.png"
#svg_content = svg_path.read_text()
#svg_html = f"""
#<div style="text-align: center; margin-top: 2rem; max-width: 600px; margin-left: auto; margin-right: auto; overflow: auto;">
#  {svg_content}
#</div>
#"""
#st.markdown(svg_html, unsafe_allow_html=True)

