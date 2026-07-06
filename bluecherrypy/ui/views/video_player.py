from __future__ import annotations
import os
import subprocess
import sys
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QSlider, QLabel, QSizePolicy, QStackedWidget
)
from PyQt6.QtCore import Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap, QImage
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
from PyQt6.QtMultimediaWidgets import QVideoWidget


def _fmt_ms(ms: int) -> str:
    s = ms // 1000
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


class VideoPlayerWidget(QWidget):
    """Embedded video player. Call play_file(path) to load a local media file."""

    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._setup_player()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Video area: stack so we can show placeholder over the video widget
        self._stack = QStackedWidget()

        self._placeholder = QLabel("Select a recording to play")
        self._placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._placeholder.setStyleSheet("background:#111; color:#555; font-size:14px;")
        self._placeholder.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._video_widget = QVideoWidget()
        self._video_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._video_widget.setStyleSheet("background:#000;")
        # macOS: must have a non-zero minimum size or the compositor ignores the surface
        self._video_widget.setMinimumSize(320, 180)

        self._stack.addWidget(self._placeholder)   # index 0
        self._stack.addWidget(self._video_widget)  # index 1
        self._stack.setCurrentIndex(0)
        root.addWidget(self._stack, stretch=1)

        # Controls bar
        bar = QWidget()
        bar.setStyleSheet("background:#1c1c1e;")
        bar_layout = QVBoxLayout(bar)
        bar_layout.setContentsMargins(10, 6, 10, 8)
        bar_layout.setSpacing(5)

        self._seek = QSlider(Qt.Orientation.Horizontal)
        self._seek.setRange(0, 0)
        self._seek.sliderMoved.connect(self._on_seek_moved)
        self._seek.sliderReleased.connect(self._on_seek_released)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._play_btn = QPushButton("▶")
        self._play_btn.setFixedWidth(38)
        self._play_btn.setToolTip("Play / Pause")
        self._play_btn.clicked.connect(self._toggle_play)
        self._play_btn.setEnabled(False)

        self._stop_btn = QPushButton("⏹")
        self._stop_btn.setFixedWidth(38)
        self._stop_btn.setToolTip("Stop")
        self._stop_btn.clicked.connect(self._stop)
        self._stop_btn.setEnabled(False)

        self._ext_btn = QPushButton("⤴")
        self._ext_btn.setFixedWidth(38)
        self._ext_btn.setToolTip("Open in system player")
        self._ext_btn.clicked.connect(self._open_external)
        self._ext_btn.setEnabled(False)

        self._time_lbl = QLabel("0:00 / 0:00")
        self._time_lbl.setStyleSheet("color:#aaa; font-size:11px; min-width:100px;")

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")

        vol_lbl = QLabel("🔊")
        vol_lbl.setStyleSheet("color:#aaa; font-size:12px;")
        self._vol = QSlider(Qt.Orientation.Horizontal)
        self._vol.setRange(0, 100)
        self._vol.setValue(80)
        self._vol.setMaximumWidth(80)
        self._vol.setToolTip("Volume")
        self._vol.valueChanged.connect(lambda v: self._audio.setVolume(v / 100.0))

        btn_row.addWidget(self._play_btn)
        btn_row.addWidget(self._stop_btn)
        btn_row.addWidget(self._ext_btn)
        btn_row.addWidget(self._time_lbl)
        btn_row.addWidget(self._status_lbl)
        btn_row.addStretch()
        btn_row.addWidget(vol_lbl)
        btn_row.addWidget(self._vol)

        bar_layout.addWidget(self._seek)
        bar_layout.addLayout(btn_row)
        root.addWidget(bar)

        self._current_path: str | None = None

    def _setup_player(self):
        self._player = QMediaPlayer(self)
        self._audio = QAudioOutput(self)
        self._audio.setVolume(0.8)
        self._player.setVideoOutput(self._video_widget)
        self._player.setAudioOutput(self._audio)
        self._player.playbackStateChanged.connect(self._on_state_changed)
        self._player.positionChanged.connect(self._on_position_changed)
        self._player.durationChanged.connect(self._on_duration_changed)
        self._player.mediaStatusChanged.connect(self._on_media_status)
        self._player.errorOccurred.connect(self._on_error)

    @property
    def has_loaded_media(self) -> bool:
        return self._current_path is not None

    def play_file(self, path: str, label: str = ""):
        self._current_path = path
        self._status_lbl.setText(label)
        self._status_lbl.setStyleSheet("color:#888; font-size:11px;")
        self._player.stop()
        # Switch to video surface before setting source so macOS AVFoundation
        # can attach to the live widget rather than a hidden one
        self._stack.setCurrentIndex(1)
        self._video_widget.show()
        self._player.setSource(QUrl.fromLocalFile(os.path.abspath(path)))
        self._player.play()
        self._play_btn.setEnabled(True)
        self._stop_btn.setEnabled(True)
        self._ext_btn.setEnabled(True)

    def show_placeholder(self, text: str = "Select a recording to play"):
        self._player.stop()
        self._player.setSource(QUrl())
        self._stack.setCurrentIndex(0)
        self._placeholder.setText(text)
        self._seek.setValue(0)
        self._time_lbl.setText("0:00 / 0:00")
        self._play_btn.setEnabled(False)
        self._stop_btn.setEnabled(False)
        self._ext_btn.setEnabled(False)
        self._current_path = None

    def _toggle_play(self):
        state = self._player.playbackState()
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self._player.pause()
        else:
            self._player.play()

    def _stop(self):
        self._player.stop()

    def _open_external(self):
        if not self._current_path:
            return
        if sys.platform == "darwin":
            subprocess.Popen(["open", self._current_path])
        elif sys.platform == "win32":
            os.startfile(self._current_path)
        else:
            subprocess.Popen(["xdg-open", self._current_path])

    def _on_seek_moved(self, pos: int):
        self._player.setPosition(pos)

    def _on_seek_released(self):
        self._player.setPosition(self._seek.value())

    def _on_state_changed(self, state):
        self._play_btn.setText(
            "⏸" if state == QMediaPlayer.PlaybackState.PlayingState else "▶"
        )

    def _on_position_changed(self, pos):
        if not self._seek.isSliderDown():
            self._seek.setValue(int(pos))
        self._update_time_label()

    def _on_duration_changed(self, dur):
        self._seek.setRange(0, max(int(dur), 0))
        self._update_time_label()

    def _on_media_status(self, status):
        if status == QMediaPlayer.MediaStatus.LoadingMedia:
            self._status_lbl.setText("Loading…")
            self._status_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        elif status == QMediaPlayer.MediaStatus.BufferedMedia:
            self._status_lbl.setStyleSheet("color:#888; font-size:11px;")

    def _on_error(self, error, msg: str):
        if error == QMediaPlayer.Error.NoError:
            return
        self._status_lbl.setText(f"⚠ {msg}")
        self._status_lbl.setStyleSheet("color:#f88; font-size:11px;")
        self.error_occurred.emit(msg)

    def _update_time_label(self):
        pos = self._player.position()
        dur = self._player.duration()
        self._time_lbl.setText(f"{_fmt_ms(pos)} / {_fmt_ms(dur)}")
