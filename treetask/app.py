"""Native TreeTask application entry point."""

import argparse
from pathlib import Path
import sys

from PySide6.QtCore import QCoreApplication, QEvent, QLockFile, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox, QSystemTrayIcon

from .desktop import InstanceServer, Tray, request_instance
from .repository import Repository
from .ui import MainWindow, apply_theme


def main(argv=None):
    parser = argparse.ArgumentParser(description="TreeTask — local desktop tasks")
    parser.add_argument("--database", type=Path, help="Use a separate SQLite database")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--tray", action="store_true", help="Start in the top bar")
    modes.add_argument("--no-tray", action="store_true", help="Exit when the window closes")
    modes.add_argument("--capture", action="store_true", help="Open the new-task dialog")
    args = parser.parse_args(argv)
    app = QApplication(sys.argv[:1])
    app.setApplicationName("TreeTask")
    app.setOrganizationName("TreeTask")
    app.setDesktopFileName("treetask")
    app.setWindowIcon(QIcon(str(Path(__file__).with_name("icon.svg"))))
    app.setStyle("Fusion")
    apply_theme(app)
    database = (args.database or Path.home() / ".treetask/tasks.db").resolve()
    lock = None
    repo = None
    server = None
    window = None
    try:
        database.parent.mkdir(parents=True, exist_ok=True)
        lock = QLockFile(str(database) + ".lock")
        lock.setStaleLockTime(0)
        if not lock.tryLock(0):
            command = "capture" if args.capture else "tray" if args.tray else "open"
            if request_instance(database, command):
                return 0
            raise RuntimeError("TreeTask is already running but could not receive the request. "
                               "Quit it from the panel menu and reopen it.")
        repo = Repository(database)
        window = MainWindow(repo)
        server = InstanceServer(database, window)
        if not args.no_tray:
            window.tray = Tray(window)
        tray_available = window.tray is not None and QSystemTrayIcon.isSystemTrayAvailable()
        app.setQuitOnLastWindowClosed(not tray_available)
        if not args.tray or not tray_available:
            window.show()
        if args.tray and not tray_available:
            window.statusBar().showMessage("Panel unavailable — TreeTask is open in this window.")
        if args.capture:
            QTimer.singleShot(0, window.new_task)
        try:
            return app.exec()
        finally:
            if window.tray:
                window.tray.hide()
    except Exception as exc:
        QMessageBox.critical(None, "TreeTask could not start", str(exc))
        return 1
    finally:
        if server is not None:
            server.close()
        if window is not None:
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        if repo is not None:
            repo.close()
        if lock is not None and lock.isLocked():
            lock.unlock()


if __name__ == "__main__":
    sys.exit(main())
