"""Enable the TreeTask panel icon and global shortcut on GNOME."""

from pathlib import Path
import shlex
import shutil
import subprocess


def setup():
    home = Path.home()
    install = home / ".local/share/treetask"
    python = install / "venv/bin/python"
    if not python.is_file():
        raise RuntimeError("Run scripts/install-desktop.py first.")
    keybindings = shutil.which("desktop-keybindings")
    if keybindings is None:
        raise RuntimeError("desktop-keybindings is required to register the global shortcut.")
    subprocess.run(
        [keybindings, "--backend", "gnome", "add", "--name", "Open TreeTask",
         "--command", shlex.join([str(python), "-m", "treetask"]),
         "--binding", "<Super><Shift>t"],
        check=True,
    )
    autostart = home / ".config/autostart/treetask.desktop"
    autostart.parent.mkdir(parents=True, exist_ok=True)
    entry = (home / ".local/share/applications/treetask.desktop").read_text(encoding="utf-8")
    # Reuse the launcher's desktop-file escaping, adding only the tray flag.
    entry = "\n".join(line + " --tray" if line.startswith("Exec=") else line
                      for line in entry.splitlines()) + "\n"
    autostart.write_text(entry, encoding="utf-8")
    with (install / "tray.log").open("a") as log:
        subprocess.Popen(
            [str(python), "-m", "treetask", "--tray"],
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True,
        )
    print("TreeTask panel icon enabled now and at login. Global shortcut: Super+Shift+T")


if __name__ == "__main__":
    setup()
