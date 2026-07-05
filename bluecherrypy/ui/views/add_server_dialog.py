from __future__ import annotations
from typing import Optional
from PyQt6.QtWidgets import (
    QDialog, QFormLayout, QLineEdit, QCheckBox, QSpinBox,
    QDialogButtonBox, QVBoxLayout, QLabel, QComboBox
)
from PyQt6.QtCore import Qt
from bluecherrypy.models.server import Server, StreamProtocol


class AddServerDialog(QDialog):
    def __init__(self, parent=None, server: Optional[Server] = None):
        super().__init__(parent)
        self._editing = server
        self.setWindowTitle("Edit Server" if server else "Add Server")
        self.setMinimumWidth(380)
        self._build_ui()
        if server:
            self._populate(server)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._name = QLineEdit()
        self._name.setPlaceholderText("My DVR")
        self._host = QLineEdit()
        self._host.setPlaceholderText("192.168.1.100 or dvr.example.com")
        self._port = QSpinBox()
        self._port.setRange(1, 65535)
        self._port.setValue(7001)
        self._login = QLineEdit()
        self._login.setPlaceholderText("admin")
        self._password = QLineEdit()
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._use_ssl = QCheckBox("Use HTTPS (recommended)")
        self._use_ssl.setChecked(True)
        self._protocol = QComboBox()
        for p in StreamProtocol:
            self._protocol.addItem(p.label, p)

        form.addRow("Name", self._name)
        form.addRow("Host", self._host)
        form.addRow("Port", self._port)
        form.addRow("Username", self._login)
        form.addRow("Password", self._password)
        form.addRow("", self._use_ssl)
        form.addRow("Live Stream", self._protocol)

        self._error_label = QLabel()
        self._error_label.setStyleSheet("color: red;")
        self._error_label.hide()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        layout.addLayout(form)
        layout.addWidget(self._error_label)
        layout.addWidget(buttons)

    def _populate(self, server: Server):
        self._name.setText(server.name)
        self._host.setText(server.host)
        self._port.setValue(server.port)
        self._login.setText(server.login)
        self._password.setText(server.password)
        self._use_ssl.setChecked(server.use_ssl)
        for i in range(self._protocol.count()):
            if self._protocol.itemData(i) == server.stream_protocol:
                self._protocol.setCurrentIndex(i)
                break

    def _on_save(self):
        if not self._name.text().strip():
            self._show_error("Name is required.")
            return
        if not self._host.text().strip():
            self._show_error("Host is required.")
            return
        if not self._login.text().strip():
            self._show_error("Username is required.")
            return
        self.accept()

    def _show_error(self, msg: str):
        self._error_label.setText(msg)
        self._error_label.show()

    def build_server(self) -> Server:
        base = self._editing or Server(name="", host="", login="", password="")
        base.name = self._name.text().strip()
        base.host = self._host.text().strip()
        base.port = self._port.value()
        base.login = self._login.text().strip()
        base.password = self._password.text()
        base.use_ssl = self._use_ssl.isChecked()
        base.stream_protocol = self._protocol.currentData()
        return base
