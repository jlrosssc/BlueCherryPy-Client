from __future__ import annotations
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, pyqtSignal, QThread, pyqtSlot
from PyQt6.QtGui import QPixmap, QImage
from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device
class _StreamThread(QThread):
    frame_ready = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, server: Server, device_id: int):
        super().__init__()
        self._server = server
        self._device_id = device_id
        self._stream = None

    def run(self):
        # Probe local network and pick protocol — runs off the UI thread
        from bluecherrypy.networking.mjpeg_stream import create_stream
        self._stream = create_stream(self._server, self._device_id,
                                     self.frame_ready.emit, self.error_occurred.emit)
        self._stream.start()
        self.exec()

    def stop_stream(self):
        if self._stream:
            self._stream.stop()
        self.quit()
        self.wait(2000)


class CameraTileWidget(QWidget):
    clicked = pyqtSignal(object, object)  # server, device

    def __init__(self, server: Server, device: Device, parent=None):
        super().__init__(parent)
        self.server = server
        self.device = device
        self._thread: _StreamThread | None = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setMinimumSize(240, 180)
        self._image_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._image_label.setStyleSheet("background: #111; border-radius: 6px;")

        self._name_label = QLabel(self.device.name)
        self._name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._name_label.setStyleSheet("font-weight: bold; font-size: 12px;")

        self._status_label = QLabel("Connecting…")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet("color: #888; font-size: 10px;")

        layout.addWidget(self._image_label)
        layout.addWidget(self._name_label)
        layout.addWidget(self._status_label)
        self.setStyleSheet("CameraTileWidget { border: 1px solid #333; border-radius: 8px; }")

    def start_stream(self):
        self._thread = _StreamThread(self.server, self.device.id)
        self._thread.frame_ready.connect(self._on_frame)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.start()

    def stop_stream(self):
        if self._thread:
            self._thread.stop_stream()
            self._thread = None

    @pyqtSlot(bytes)
    def _on_frame(self, data: bytes):
        img = QImage.fromData(data)
        if img.isNull():
            return
        pix = QPixmap.fromImage(img).scaled(
            self._image_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._image_label.setPixmap(pix)
        self._status_label.setText("Live")
        self._status_label.setStyleSheet("color: #4caf50; font-size: 10px;")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._image_label.setText(f"⚠ {msg}")
        self._image_label.setStyleSheet("background: #200; color: #f88; border-radius: 6px; padding: 8px;")
        self._status_label.setText("Offline")
        self._status_label.setStyleSheet("color: #f44; font-size: 10px;")

    def mousePressEvent(self, event):
        self.clicked.emit(self.server, self.device)
        super().mousePressEvent(event)
