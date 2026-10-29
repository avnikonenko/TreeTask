"""Install TreeTask and its Linux application-menu entry for the current user."""

from pathlib import Path
import shutil
import subprocess
import venv


def install():
    source = Path(__file__).resolve().parents[1]
    home = Path.home()
    destination = home / ".local/share/treetask"
    environment = destination / "venv"
    venv.EnvBuilder(with_pip=True).create(environment)
    python = environment / "bin/python"
    subprocess.run([str(python), "-m", "pip", "install", str(source)], check=True)

    icon = home / ".local/share/icons/hicolor/scalable/apps/treetask.svg"
    icon.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source / "treetask/icon.svg", icon)
    # Keep older launchers/global shortcuts working after the native upgrade.
    (destination / "desktop.py").write_text(
        "import os, sys\n"
        f"python = {str(python)!r}\n"
        "os.execv(python, [python, '-m', 'treetask', *sys.argv[1:]])\n",
        encoding="utf-8",
    )
    applications = home / ".local/share/applications"
    applications.mkdir(parents=True, exist_ok=True)
    # Desktop Exec quoting is distinct from shell quoting.
    executable = str(python).replace("\\", "\\\\").replace('"', '\\"')
    executable = executable.replace("`", "\\`").replace("$", "\\$").replace("%", "%%")
    desktop = applications / "treetask.desktop"
    desktop.write_text(
        "[Desktop Entry]\nType=Application\nName=TreeTask\n"
        "Comment=Manage tasks and grow your plant\n"
        f'Exec="{executable}" -m treetask\n'
        "Icon=treetask\nTerminal=false\nCategories=Office;\n"
        "Keywords=task;todo;plant;productivity;\n",
        encoding="utf-8",
    )
    if shutil.which("update-desktop-database"):
        subprocess.run(["update-desktop-database", str(applications)], check=True)
    else:
        print("update-desktop-database unavailable; desktop cache refresh skipped.")
    print(f"Installed TreeTask: {desktop}")
    print("Open the native TreeTask window from the application menu.")


if __name__ == "__main__":
    install()
