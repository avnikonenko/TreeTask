"""Native tray menu and same-user, single-instance desktop activation."""

import hashlib
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from .ui import SHORTCUTS


def endpoint(database):
    digest = hashlib.sha256(str(Path(database).resolve()).encode()).hexdigest()[:24]
    return "treetask-" + digest


def request_instance(database, command="open"):
    socket = QLocalSocket()
    socket.connectToServer(endpoint(database))
    if not socket.waitForConnected(1500):
        return False
    socket.write(command.encode() + b"\n")
    if socket.bytesToWrite() and not socket.waitForBytesWritten(1500):
        socket.abort()
        return False
    if not socket.bytesAvailable() and not socket.waitForReadyRead(1500):
        socket.abort()
        return False
    accepted = bytes(socket.readAll()).strip() == b"ok"
    socket.disconnectFromServer()
    return accepted


class InstanceServer(QLocalServer):
    """Created only after obtaining the database lock; stale sockets are safe to remove."""
    def __init__(self, database, window):
        super().__init__(window)
        self.window = window
        self.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        name = endpoint(database)
        QLocalServer.removeServer(name)
        if not self.listen(name):
            raise RuntimeError(self.errorString())
        self.newConnection.connect(self.accept_connections)

    def accept_connections(self):
        while self.hasPendingConnections():
            socket = self.nextPendingConnection()
            socket.setReadBufferSize(128)
            socket.readyRead.connect(lambda socket=socket: self.receive(socket))
            socket.disconnected.connect(socket.deleteLater)
            self.receive(socket)

    def receive(self, socket):
        if not socket.canReadLine():
            return
        command = bytes(socket.readLine()).strip()
        if command not in (b"open", b"capture", b"tray"):
            socket.disconnectFromServer()
            return
        socket.write(b"ok\n")
        socket.disconnectFromServer()
        if command == b"open":
            QTimer.singleShot(0, self.window.open_window)
        elif command == b"capture":
            QTimer.singleShot(0, self.window.new_task)


class Tray(QSystemTrayIcon):
    def __init__(self, window):
        super().__init__(QApplication.windowIcon(), window)
        self.setToolTip("TreeTask")
        menu = QMenu(window)
        menu.addAction("Open TreeTask", window.open_window)
        menu.addAction("+ New task", window.new_task)
        shortcuts = menu.addMenu("Keyboard shortcuts")
        for key, label in SHORTCUTS:
            action = shortcuts.addAction(f"{key} — {label}")
            action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("Quit TreeTask", window.quit_app)
        self.menu = menu
        self.setContextMenu(menu)
        self.activated.connect(lambda reason: window.open_window()
                               if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
        self.show()
