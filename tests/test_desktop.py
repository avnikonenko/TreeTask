import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from treetask import desktop


class DesktopLaunchTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.install = Path(temporary.name)
        for name, value in (
            ("INSTALL", self.install),
            ("owns_server", None),
            ("healthy", None),
            ("subprocess.check_output", None),
            ("subprocess.Popen", None),
            ("subprocess.run", None),
            ("time.sleep", None),
        ):
            kwargs = {"new": value} if value is not None else {}
            mock = patch.object(desktop, name, **kwargs) if "." not in name else patch(
                "treetask.desktop." + name, **kwargs,
            )
            result = mock.start()
            self.addCleanup(mock.stop)
            if name != "INSTALL":
                setattr(self, name.replace(".", "_"), result)
        self.subprocess_check_output.return_value = "/installed/treetask\n"

    def test_reuses_running_server(self):
        self.owns_server.return_value = True
        self.healthy.return_value = True
        desktop.open_app()
        self.subprocess_Popen.assert_not_called()
        self.subprocess_run.assert_called_once_with(["xdg-open", desktop.URL], check=True)

    def test_starts_server_and_waits_before_opening(self):
        self.owns_server.return_value = False
        self.healthy.side_effect = [False, False, True]
        process = self.subprocess_Popen.return_value
        process.pid = 123
        process.poll.return_value = None
        desktop.open_app()
        command = self.subprocess_Popen.call_args.args[0]
        self.assertIn("--server.address=127.0.0.1", command)
        self.assertIn("--server.port=8517", command)
        self.assertEqual((self.install / "server.pid").read_text(), "123")
        self.time_sleep.assert_called_once()
        self.subprocess_run.assert_called_once_with(["xdg-open", desktop.URL], check=True)

    def test_refuses_unrelated_server(self):
        self.owns_server.return_value = False
        self.healthy.return_value = True
        with self.assertRaisesRegex(RuntimeError, "already in use"):
            desktop.open_app()
        self.subprocess_Popen.assert_not_called()
        self.subprocess_run.assert_not_called()

    def test_reports_failed_start_without_opening_browser(self):
        self.owns_server.return_value = False
        self.healthy.return_value = False
        self.subprocess_Popen.return_value.pid = 123
        self.subprocess_Popen.return_value.poll.return_value = 1
        with self.assertRaisesRegex(RuntimeError, "failed to start"):
            desktop.open_app()
        self.subprocess_run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
