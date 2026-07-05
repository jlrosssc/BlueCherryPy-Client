from __future__ import annotations
import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QProgressBar, QMessageBox, QSplitter
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device
from bluecherrypy.networking.client import BluecherryClient, BluecherryError


class _FetchThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, client: BluecherryClient, device_id: int):
        super().__init__()
        self._client = client
        self._device_id = device_id

    def run(self):
        try:
            self.finished.emit(self._client.fetch_recordings(self._device_id))
        except Exception as e:
            self.error.emit(str(e))


class _DownloadThread(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, client: BluecherryClient, recording):
        super().__init__()
        self._client = client
        self._recording = recording

    def run(self):
        try:
            self.finished.emit(self._client.download_recording(self._recording))
        except Exception as e:
            self.error.emit(str(e))


class RecordingsWidget(QWidget):
    def __init__(self, server: Server, device: Device, parent=None):
        super().__init__(parent)
        self.server = server
        self.device = device
        self._client = BluecherryClient(server)
        self._recordings = []
        self.setWindowTitle(f"Recordings — {device.name}")
        self.resize(600, 500)
        self._build_ui()
        self._load_recordings()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(f"Recordings for {self.device.name}")
        header.setStyleSheet("font-size: 15px; font-weight: bold; padding: 8px 0;")
        layout.addWidget(header)

        self._list = QListWidget()
        self._list.currentRowChanged.connect(self._on_selection_changed)
        layout.addWidget(self._list, stretch=1)

        self._detail_label = QLabel()
        self._detail_label.setStyleSheet("color: #888; font-size: 11px; padding: 4px 0;")
        layout.addWidget(self._detail_label)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.hide()
        layout.addWidget(self._progress)

        btn_row = QHBoxLayout()
        self._play_btn = QPushButton("Play Recording")
        self._play_btn.setEnabled(False)
        self._play_btn.clicked.connect(self._on_play)
        self._download_btn = QPushButton("Download")
        self._download_btn.setEnabled(False)
        self._download_btn.clicked.connect(self._on_download)
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_recordings)
        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._download_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._refresh_btn)
        layout.addLayout(btn_row)

    def _load_recordings(self):
        self._list.clear()
        self._recordings = []
        self._detail_label.setText("Loading…")
        self._progress.show()
        self._thread = _FetchThread(self._client, self.device.id)
        self._thread.finished.connect(self._on_loaded)
        self._thread.error.connect(self._on_error)
        self._thread.start()

    @pyqtSlot(list)
    def _on_loaded(self, recordings):
        self._progress.hide()
        self._recordings = recordings
        if not recordings:
            self._detail_label.setText("No recordings found.")
            return
        for r in recordings:
            date_str = r.date.strftime("%Y-%m-%d %H:%M:%S") if r.date else "Unknown date"
            dur = f"  ({r.duration_description})" if r.duration_description else ""
            item = QListWidgetItem(f"{date_str}{dur}  —  {r.title}")
            self._list.addItem(item)
        self._detail_label.setText(f"{len(recordings)} recording(s) found.")

    @pyqtSlot(str)
    def _on_error(self, msg: str):
        self._progress.hide()
        self._detail_label.setText(f"Error: {msg}")

    def _on_selection_changed(self, row: int):
        has = 0 <= row < len(self._recordings)
        self._play_btn.setEnabled(has)
        self._download_btn.setEnabled(has and self._recordings[row].media_id is not None)

    def _on_play(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._download_and_open(self._recordings[row], play=True)

    def _on_download(self):
        row = self._list.currentRow()
        if row < 0:
            return
        self._download_and_open(self._recordings[row], play=False)

    def _download_and_open(self, recording, play: bool):
        self._progress.show()
        self._play_btn.setEnabled(False)
        self._download_btn.setEnabled(False)
        self._thread = _DownloadThread(self._client, recording)
        self._thread.finished.connect(lambda path: self._on_downloaded(path, play))
        self._thread.error.connect(self._on_download_error)
        self._thread.start()

    def _on_downloaded(self, path: str, play: bool):
        self._progress.hide()
        self._on_selection_changed(self._list.currentRow())
        if play:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif sys.platform == "win32":
                os.startfile(path)
            else:
                subprocess.Popen(["xdg-open", path])
        else:
            QMessageBox.information(self, "Downloaded", f"Saved to:\n{path}")

    def _on_download_error(self, msg: str):
        self._progress.hide()
        self._on_selection_changed(self._list.currentRow())
        QMessageBox.warning(self, "Download Failed", msg)
