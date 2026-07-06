from __future__ import annotations
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QToolBar,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread, QRectF
from PyQt6.QtGui import QPixmap, QImage, QAction

from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device


# ── Stream thread ─────────────────────────────────────────────────────────────

class _StreamThread(QThread):
    frame_ready = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)

    def __init__(self, server: Server, device_id: int):
        super().__init__()
        self._server = server
        self._device_id = device_id
        self._stream = None

    def run(self):
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


# ── Zoomable frame view ───────────────────────────────────────────────────────

class _FrameView(QGraphicsView):
    """QGraphicsView that zooms on scroll wheel and pans when dragged."""

    _MIN_ZOOM = 0.5
    _MAX_ZOOM = 8.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self._item = QGraphicsPixmapItem()
        self._scene.addItem(self._item)
        self.setScene(self._scene)

        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background:#000; border:none;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._zoom_level = 1.0
        self._has_frame = False

    def set_pixmap(self, pix: QPixmap):
        self._item.setPixmap(pix)
        if not self._has_frame:
            self._has_frame = True
            self._fit()

    def show_message(self, text: str):
        self._item.setPixmap(QPixmap())
        self._scene.setSceneRect(QRectF(0, 0, self.width(), self.height()))
        self._has_frame = False

    def reset_zoom(self):
        self._zoom_level = 1.0
        self.resetTransform()
        self._fit()

    def _fit(self):
        r = self._item.boundingRect()
        if r.isEmpty():
            return
        self.fitInView(r, Qt.AspectRatioMode.KeepAspectRatio)
        t = self.transform()
        self._zoom_level = t.m11()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        new_zoom = self._zoom_level * factor
        new_zoom = max(self._MIN_ZOOM, min(self._MAX_ZOOM, new_zoom))
        factor = new_zoom / self._zoom_level
        self._zoom_level = new_zoom
        self.scale(factor, factor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if not self._has_frame and self._item.pixmap().isNull():
            return
        # Re-fit only when at default zoom so resizing the window feels natural
        if abs(self._zoom_level - self.transform().m11()) < 0.05:
            self._fit()


# ── Main live camera widget ───────────────────────────────────────────────────

class LiveCameraWidget(QWidget):
    recordings_requested = pyqtSignal(object, object)  # server, device

    def __init__(self, server: Server, device: Device, parent=None):
        super().__init__(parent)
        self.server = server
        self.device = device
        self._thread: _StreamThread | None = None
        self.setWindowTitle(device.name)
        self._build_ui()
        self.start_stream()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QToolBar()
        toolbar.setMovable(False)
        recordings_action = QAction("Recordings", self)
        recordings_action.triggered.connect(
            lambda: self.recordings_requested.emit(self.server, self.device)
        )
        toolbar.addAction(recordings_action)

        reset_action = QAction("Reset Zoom", self)
        reset_action.triggered.connect(lambda: self._view.reset_zoom())
        toolbar.addAction(reset_action)

        if self.device.has_ptz:
            self._add_ptz_controls(toolbar)

        # Zoomable frame view
        self._view = _FrameView()

        # Status bar
        self._status_label = QLabel("Connecting…")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setStyleSheet(
            "background:#111; color:#aaa; padding:4px; font-size:11px;"
        )

        layout.addWidget(toolbar)
        layout.addWidget(self._view, stretch=1)
        layout.addWidget(self._status_label)

    def _add_ptz_controls(self, toolbar: QToolBar):
        toolbar.addSeparator()
        from bluecherrypy.networking.client import BluecherryClient
        client = BluecherryClient(self.server)

        def ptz(pan=None, tilt=None, zoom=None):
            import threading
            threading.Thread(
                target=client.send_ptz,
                kwargs={"device_id": self.device.id, "pan": pan, "tilt": tilt, "zoom": zoom},
                daemon=True,
            ).start()

        for label, kwargs in [
            ("◀", {"pan": "l"}), ("▶", {"pan": "r"}),
            ("▲", {"tilt": "u"}), ("▼", {"tilt": "d"}),
            ("⊕", {"zoom": "t"}), ("⊖", {"zoom": "w"}),
        ]:
            btn = QPushButton(label)
            btn.setFixedWidth(32)
            btn.clicked.connect(lambda _, kw=kwargs: ptz(**kw))
            toolbar.addWidget(btn)

    def start_stream(self):
        self._thread = _StreamThread(self.server, self.device.id)
        self._thread.frame_ready.connect(self._on_frame)
        self._thread.error_occurred.connect(self._on_error)
        self._thread.start()

    def stop_stream(self):
        if self._thread:
            self._thread.stop_stream()
            self._thread = None

    def _on_frame(self, data: bytes):
        img = QImage.fromData(data)
        if img.isNull():
            return
        self._view.set_pixmap(QPixmap.fromImage(img))
        self._status_label.setText("Live  ·  scroll to zoom  ·  drag to pan")
        self._status_label.setStyleSheet(
            "background:#111; color:#4caf50; padding:4px; font-size:11px;"
        )

    def _on_error(self, msg: str):
        self._view.show_message(msg)
        self._status_label.setText(f"⚠ {msg}")
        self._status_label.setStyleSheet(
            "background:#111; color:#f44; padding:4px; font-size:11px;"
        )

    def closeEvent(self, event):
        self.stop_stream()
        super().closeEvent(event)
