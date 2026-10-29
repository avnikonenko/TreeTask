import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch


from treetask.desktop import InstanceServer, Tray, endpoint
from treetask.repository import Repository
from treetask.ui import MainWindow
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon


class DesktopTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setWindowIcon(QIcon(str(Path(__file__).resolve().parents[1] / "treetask/icon.svg")))

    def test_native_entrypoint_quits_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            code = """import sys
from PySide6.QtCore import QTimer
from treetask import app
OriginalWindow = app.MainWindow
class AutoQuitWindow(OriginalWindow):
    def __init__(self, repo):
        super().__init__(repo)
        QTimer.singleShot(100, self.quit_app)
app.MainWindow = AutoQuitWindow
result = app.main(['--database', sys.argv[1], '--no-tray'])
assert 'streamlit' not in sys.modules
sys.exit(result)
"""
            result = subprocess.run([sys.executable, "-c", code, str(Path(directory) / "tasks.db")],
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_socket_name_is_stable_and_database_specific(self):
        self.assertEqual(endpoint("tasks.db"), endpoint(Path.cwd() / "tasks.db"))
        self.assertNotEqual(endpoint("tasks.db"), endpoint("other.db"))

    def test_second_process_requests_existing_window(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "tasks.db"
            repo = Repository(database)
            window = MainWindow(repo)
            server = InstanceServer(database, window)
            try:
                code = """from PySide6.QtCore import QCoreApplication
from treetask.desktop import request_instance
import sys
app = QCoreApplication([])
sys.exit(0 if request_instance(sys.argv[1]) else 1)
"""
                process = subprocess.Popen([sys.executable, "-c", code, str(database)])
                deadline = time.monotonic() + 8
                while process.poll() is None and time.monotonic() < deadline:
                    self.app.processEvents()
                    time.sleep(0.01)
                if process.poll() is None:
                    process.kill()
                    process.wait()
                    self.fail("Activation request timed out")
                self.app.processEvents()
                self.assertEqual(process.returncode, 0)
                self.assertTrue(window.isVisible())
            finally:
                server.close()
                window.hide()
                window.deleteLater()
                repo.close()

    def test_tray_menu_keeps_shortcuts_and_native_actions(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Repository(Path(directory) / "tasks.db")
            window = MainWindow(repo)
            tray = Tray(window)
            try:
                labels = [action.text() for action in tray.menu.actions()]
                self.assertIn("Open TreeTask", labels)
                self.assertIn("Keyboard shortcuts", labels)
                self.assertIn("Quit TreeTask", labels)
            finally:
                tray.hide()
                window.deleteLater()
                repo.close()

    def test_installer_writes_native_launcher_and_legacy_compatibility_shim(self):
        script = Path(__file__).resolve().parents[1] / "scripts/install-desktop.py"
        spec = importlib.util.spec_from_file_location("installer", script)
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        with tempfile.TemporaryDirectory() as directory:
            home = Path(directory)
            with patch.object(Path, "home", return_value=home), \
                 patch.object(installer.venv.EnvBuilder, "create", side_effect=lambda path: path.mkdir(parents=True)), \
                 patch.object(installer.subprocess, "run"), patch.object(installer.shutil, "which", return_value=None):
                installer.install()
            entry = (home / ".local/share/applications/treetask.desktop").read_text()
            shim = (home / ".local/share/treetask/desktop.py").read_text()
            self.assertIn('" -m treetask', entry)
            self.assertIn("os.execv", shim)
            self.assertNotIn("streamlit", entry + shim)
            self.assertNotIn("gi", shim)


if __name__ == "__main__":
    unittest.main()
