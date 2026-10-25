"""Linux panel helper, run with the system Python for its GTK bindings."""

import argparse
from contextlib import closing
import fcntl
from pathlib import Path
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen


INSTALL = Path.home() / ".local/share/treetask"
URL = "http://127.0.0.1:8517"


def healthy():
    try:
        with closing(urlopen(URL + "/_stcore/health", timeout=1)) as response:
            return response.status == 200
    except (URLError, TimeoutError):
        return False


def owns_server(pid_file, app):
    try:
        arguments = (Path("/proc") / pid_file.read_text().strip() / "cmdline").read_bytes()
        return str(app).encode() in arguments.split(b"\0")
    except (OSError, ValueError):
        return False


def open_app():
    """Serialize launches and reuse only a server started by this helper."""
    INSTALL.mkdir(parents=True, exist_ok=True)
    with (INSTALL / "launch.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        python = INSTALL / "venv/bin/python"
        # Resolve the installed package without depending on this copied helper.
        app = Path(subprocess.check_output(
            [str(python), "-c", "import treetask; print(treetask.__path__[0])"],
            text=True, cwd=INSTALL,
        ).strip()) / "app.py"
        pid_file = INSTALL / "server.pid"
        process = None
        if not owns_server(pid_file, app):
            if healthy():
                raise RuntimeError("Port 8517 is already in use; refusing to open an unrelated app.")
            with (INSTALL / "server.log").open("a") as log:
                process = subprocess.Popen(
                    [str(python), "-m", "streamlit", "run", str(app),
                     "--server.address=127.0.0.1", "--server.port=8517",
                     "--server.headless=true", "--browser.gatherUsageStats=false"],
                    stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
                )
            pid_file.write_text(str(process.pid), encoding="utf-8")
        deadline = time.monotonic() + 30
        while not healthy():
            if process is not None and process.poll() is not None:
                raise RuntimeError(f"TreeTask failed to start; see {INSTALL / 'server.log'}")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"TreeTask did not become ready; see {INSTALL / 'server.log'}")
            time.sleep(0.2)
        subprocess.run(["xdg-open", URL], check=True)


def run_tray():
    import gi

    gi.require_version("Gtk", "3.0")
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3, Gtk

    INSTALL.mkdir(parents=True, exist_ok=True)
    with (INSTALL / "tray.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        icon = Path.home() / ".local/share/icons/hicolor/scalable/apps/treetask.svg"
        indicator = AyatanaAppIndicator3.Indicator.new(
            "treetask", str(icon), AyatanaAppIndicator3.IndicatorCategory.APPLICATION_STATUS,
        )
        indicator.set_title("TreeTask")
        indicator.set_status(AyatanaAppIndicator3.IndicatorStatus.ACTIVE)
        menu = Gtk.Menu()
        item = Gtk.MenuItem(label="Open TreeTask (Super+Shift+T)")
        # Keep server startup and browser launching out of the GTK event loop.
        item.connect("activate", lambda _: subprocess.Popen(
            ["/usr/bin/python3", str(INSTALL / "desktop.py")],
        ))
        menu.append(item)
        shortcuts_item = Gtk.MenuItem(label="Keyboard shortcuts")
        shortcuts_menu = Gtk.Menu()
        for label in (
            "Anywhere: Super+Shift+T — Open TreeTask",
            "In TreeTask: Alt+Shift+N — New task",
            "In TreeTask: Alt+Shift+D — Finish selected task",
            "In new-task form: Ctrl+Enter — Add task",
        ):
            shortcut = Gtk.MenuItem(label=label)
            shortcut.set_sensitive(False)
            shortcuts_menu.append(shortcut)
        shortcuts_item.set_submenu(shortcuts_menu)
        menu.append(shortcuts_item)
        quit_item = Gtk.MenuItem(label="Hide icon")
        quit_item.connect("activate", lambda _: Gtk.main_quit())
        menu.append(quit_item)
        menu.show_all()
        indicator.set_menu(menu)
        Gtk.main()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tray", action="store_true")
    args = parser.parse_args()
    if args.tray:
        run_tray()
    else:
        open_app()


if __name__ == "__main__":
    main()
