from __future__ import annotations
import os
import shutil
import tempfile
from datetime import datetime
from typing import Optional

import requests
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QLabel, QPushButton,
    QComboBox, QDateEdit, QProgressBar, QSizePolicy, QFrame,
    QFileDialog, QMenu, QAbstractItemView
)
from PyQt6.QtCore import Qt, QThread, QTimer, pyqtSignal, QDate, QSize, QPoint
from PyQt6.QtGui import QPixmap, QImage, QAction

from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device
from bluecherrypy.models.recording import RecordingEvent
from bluecherrypy.networking.client import BluecherryClient
from bluecherrypy.ui.views.video_player import VideoPlayerWidget

_THUMB_W = 176
_THUMB_H = 99
_ITEM_H  = 120


# ── Background workers ────────────────────────────────────────────────────────

class _FetchRecordingsThread(QThread):
    recordings_ready = pyqtSignal(int, list)
    fetch_error      = pyqtSignal(int, str)

    def __init__(self, client: BluecherryClient, device_id: int):
        super().__init__()
        self._client    = client
        self._device_id = device_id

    def run(self):
        try:
            self.recordings_ready.emit(self._device_id,
                                       self._client.fetch_recordings(self._device_id))
        except Exception as e:
            self.fetch_error.emit(self._device_id, str(e))


class _ThumbnailThread(QThread):
    """jobs: list of (media_id, [url, fallback_url, ...])"""
    loaded = pyqtSignal(int, bytes)

    def __init__(self, server: Server, jobs: list[tuple[int, list[str]]]):
        super().__init__()
        self._server   = server
        self._jobs     = jobs
        self._running  = True

    def run(self):
        session = requests.Session()
        session.verify = False
        headers = {"Authorization": self._server.authorization_header}
        for media_id, urls in self._jobs:
            if not self._running:
                break
            for url in urls:
                try:
                    r = session.get(url, headers=headers, timeout=8)
                    if not r.ok or not r.content:
                        continue
                    ct = r.headers.get("Content-Type", "").lower()
                    is_image = (
                        "image" in ct
                        or ct in ("application/octet-stream", "")
                        or r.content[:2] in (b'\xff\xd8', b'\x89P')
                    )
                    if is_image:
                        self.loaded.emit(media_id, r.content)
                        break  # got it, move to next recording
                except Exception:
                    continue
        session.close()

    def stop(self):
        self._running = False


class _DownloadThread(QThread):
    """Download to a temp file for playback."""
    download_ready = pyqtSignal(str)
    dl_error       = pyqtSignal(str)

    def __init__(self, client: BluecherryClient, recording: RecordingEvent):
        super().__init__()
        self._client    = client
        self._recording = recording

    def run(self):
        try:
            self.download_ready.emit(self._client.download_recording(self._recording))
        except Exception as e:
            self.dl_error.emit(str(e))


class _SaveThread(QThread):
    """Download a recording and save directly to a user-chosen path."""
    progress      = pyqtSignal(int)   # bytes written so far
    save_complete = pyqtSignal(str)   # destination path
    save_error    = pyqtSignal(str)

    def __init__(self, client: BluecherryClient, recording: RecordingEvent,
                 destination: str):
        super().__init__()
        self._client      = client
        self._recording   = recording
        self._destination = destination

    def run(self):
        try:
            tmp = self._client.download_recording(self._recording)
            shutil.copy2(tmp, self._destination)
            self.save_complete.emit(self._destination)
        except Exception as e:
            self.save_error.emit(str(e))


# ── Thumbnail list item ───────────────────────────────────────────────────────

class _RecordingItemWidget(QWidget):
    def __init__(self, recording: RecordingEvent, device_name: str):
        super().__init__()
        self.recording = recording
        self._build(device_name)

    def _build(self, device_name: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 6, 10, 6)
        layout.setSpacing(10)

        self._thumb = QLabel()
        self._thumb.setFixedSize(_THUMB_W, _THUMB_H)
        self._thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._thumb.setStyleSheet(
            "background:#222; border-radius:4px; color:#555; font-size:10px;"
        )
        self._thumb.setText("…")

        info = QWidget()
        info_layout = QVBoxLayout(info)
        info_layout.setContentsMargins(0, 4, 0, 4)
        info_layout.setSpacing(3)

        date_lbl = QLabel(
            self.recording.date.strftime("%Y-%m-%d") if self.recording.date else "Unknown"
        )
        date_lbl.setStyleSheet("font-weight:bold; font-size:12px;")

        time_lbl = QLabel(
            self.recording.date.strftime("%H:%M:%S") if self.recording.date else ""
        )
        time_lbl.setStyleSheet("color:#aaa; font-size:11px;")

        cam_lbl  = QLabel(device_name)
        cam_lbl.setStyleSheet("color:#888; font-size:11px;")

        dur_lbl  = QLabel(
            f"Duration: {self.recording.duration_description}"
            if self.recording.duration_description else ""
        )
        dur_lbl.setStyleSheet("color:#5a9; font-size:11px;")

        type_lbl = QLabel(
            self.recording.type_id.capitalize() if self.recording.type_id else ""
        )
        type_lbl.setStyleSheet("color:#a88; font-size:10px;")

        for w in (date_lbl, time_lbl, cam_lbl, dur_lbl, type_lbl):
            info_layout.addWidget(w)
        info_layout.addStretch()

        layout.addWidget(self._thumb)
        layout.addWidget(info, stretch=1)
        self.setFixedHeight(_ITEM_H)

    def set_thumbnail(self, data: bytes):
        img = QImage.fromData(data)
        if img.isNull():
            return
        pix = QPixmap.fromImage(img).scaled(
            _THUMB_W, _THUMB_H,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._thumb.setText("")
        self._thumb.setStyleSheet("background:#000; border-radius:4px;")
        self._thumb.setPixmap(pix)


# ── Embeddable recordings browser widget ─────────────────────────────────────

class RecordingsBrowserWidget(QWidget):
    """Self-contained recordings browser. Can be embedded in any layout."""

    def __init__(self, server: Server, devices: list[Device],
                 initial_device: Optional[Device] = None, parent=None):
        super().__init__(parent)
        self._server   = server
        self._devices  = devices
        self._client   = BluecherryClient(server)
        self._all_recordings: list[RecordingEvent]       = []
        self._device_map: dict[int, str]                 = {d.id: d.name for d in devices}
        self._fetch_thread: Optional[_FetchRecordingsThread] = None
        self._thumb_thread: Optional[_ThumbnailThread]   = None
        self._dl_thread:    Optional[_DownloadThread]    = None
        self._save_thread:  Optional[_SaveThread]        = None
        self._item_widgets: dict[int, _RecordingItemWidget] = {}
        self._pending_device_ids: list[int]              = []
        self._current_recording: Optional[RecordingEvent] = None
        self._cached_paths: dict[int, str]               = {}  # media_id → temp path
        self._batch_queue:  list                         = []
        self._batch_total:  int                          = 0
        self._batch_dir:    str                          = ""

        self._build_ui()

        if initial_device:
            idx = next(
                (i + 1 for i, d in enumerate(devices) if d.id == initial_device.id), 0
            )
            self._camera_combo.setCurrentIndex(idx)
        self._load_recordings()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_filter_bar())

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self._build_list_panel())
        splitter.addWidget(self._build_player_panel())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([360, 740])
        root.addWidget(splitter, stretch=1)

        self._status_lbl = QLabel()
        self._status_lbl.setStyleSheet(
            "background:#1c1c1e; color:#888; font-size:11px; "
            "padding:3px 10px; border-top:1px solid #333;"
        )
        root.addWidget(self._status_lbl)

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet("background:#2c2c2e; border-bottom:1px solid #444;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 7, 12, 7)
        layout.setSpacing(10)

        layout.addWidget(_lbl("Camera:"))
        self._camera_combo = QComboBox()
        self._camera_combo.setMinimumWidth(160)
        self._camera_combo.addItem("All Cameras", None)
        for d in self._devices:
            self._camera_combo.addItem(d.name, d.id)
        self._camera_combo.currentIndexChanged.connect(self._on_camera_changed)
        layout.addWidget(self._camera_combo)

        layout.addWidget(_sep())
        layout.addWidget(_lbl("From:"))
        self._from_date = QDateEdit()
        self._from_date.setCalendarPopup(True)
        self._from_date.setDate(QDate.currentDate().addDays(-30))
        self._from_date.setDisplayFormat("yyyy-MM-dd")
        self._from_date.dateChanged.connect(self._apply_filters)
        layout.addWidget(self._from_date)

        layout.addWidget(_lbl("To:"))
        self._to_date = QDateEdit()
        self._to_date.setCalendarPopup(True)
        self._to_date.setDate(QDate.currentDate())
        self._to_date.setDisplayFormat("yyyy-MM-dd")
        self._to_date.dateChanged.connect(self._apply_filters)
        layout.addWidget(self._to_date)

        layout.addWidget(_sep())
        for label, val in [("1h", -1), ("4h", -4), ("8h", -8),
                           ("Today", 0), ("7 Days", 7), ("30 Days", 30)]:
            btn = QPushButton(label)
            btn.setFlat(True)
            btn.setStyleSheet("color:#4a9eff; font-size:11px; padding:2px 8px;")
            btn.clicked.connect(lambda _, v=val: self._quick_filter(v))
            layout.addWidget(btn)

        layout.addStretch()
        self._refresh_btn = QPushButton("↺  Refresh")
        self._refresh_btn.clicked.connect(self._load_recordings)
        layout.addWidget(self._refresh_btn)
        return bar

    def _build_list_panel(self) -> QWidget:
        panel = QWidget()
        panel.setMinimumWidth(340)
        panel.setMaximumWidth(440)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._count_lbl = QLabel("  Loading…")
        self._count_lbl.setStyleSheet(
            "background:#1c1c1e; color:#888; font-size:11px; padding:5px 10px;"
        )
        layout.addWidget(self._count_lbl)

        self._progress = QProgressBar()
        self._progress.setRange(0, 0)
        self._progress.setMaximumHeight(3)
        self._progress.setTextVisible(False)
        self._progress.hide()
        layout.addWidget(self._progress)

        self._list = QListWidget()
        self._list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._list.setStyleSheet(
            "QListWidget{border:none; background:#1c1c1e; color:#ddd;}"
            "QListWidget::item:selected{background:#2c5282; color:#ffffff;}"
            "QListWidget::item:hover:!selected{background:#2a2a3a; color:#ddd;}"
        )
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.currentItemChanged.connect(self._on_current_item_changed)
        self._list.itemSelectionChanged.connect(self._on_selection_changed)
        self._list.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self._list, stretch=1)
        return panel

    def _build_player_panel(self) -> QWidget:
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Action bar above the player
        action_bar = QWidget()
        action_bar.setStyleSheet(
            "background:#2c2c2e; border-bottom:1px solid #444;"
        )
        ab_layout = QHBoxLayout(action_bar)
        ab_layout.setContentsMargins(10, 6, 10, 6)
        ab_layout.setSpacing(8)

        self._play_sel_btn = QPushButton("▶  Play")
        self._play_sel_btn.setToolTip("Download and play selected recording")
        self._play_sel_btn.setEnabled(False)
        self._play_sel_btn.clicked.connect(self._play_selected)
        ab_layout.addWidget(self._play_sel_btn)

        self._save_sel_btn = QPushButton("💾  Download")
        self._save_sel_btn.setToolTip("Save selected recording to disk")
        self._save_sel_btn.setEnabled(False)
        self._save_sel_btn.clicked.connect(self._save_selected)
        ab_layout.addWidget(self._save_sel_btn)

        self._sel_info_lbl = QLabel("Select a recording")
        self._sel_info_lbl.setStyleSheet("color:#888; font-size:11px;")
        ab_layout.addWidget(self._sel_info_lbl, stretch=1)
        layout.addWidget(action_bar)

        # Video player
        self._player = VideoPlayerWidget()
        self._player.error_occurred.connect(
            lambda msg: self._set_status(
                f"Player error: {msg} — use ⤴ button to open in system player"
            )
        )
        layout.addWidget(self._player, stretch=1)

        # Download progress bar (used by Save)
        self._dl_bar = QWidget()
        self._dl_bar.setStyleSheet("background:#1c1c1e; border-top:1px solid #333;")
        dl_layout = QHBoxLayout(self._dl_bar)
        dl_layout.setContentsMargins(10, 5, 10, 5)
        self._dl_lbl  = QLabel("Working…")
        self._dl_lbl.setStyleSheet("color:#aaa; font-size:11px;")
        self._dl_prog = QProgressBar()
        self._dl_prog.setRange(0, 0)
        self._dl_prog.setMaximumHeight(6)
        self._dl_prog.setTextVisible(False)
        dl_layout.addWidget(self._dl_lbl)
        dl_layout.addWidget(self._dl_prog, stretch=1)
        self._dl_bar.hide()
        layout.addWidget(self._dl_bar)
        return panel

    # ── Data loading ──────────────────────────────────────────────────────────

    def _load_recordings(self):
        self._stop_threads()
        self._all_recordings.clear()
        self._item_widgets.clear()
        self._cached_paths.clear()
        self._list.clear()
        self._progress.show()
        self._count_lbl.setText("  Loading…")
        self._refresh_btn.setEnabled(False)

        device_id = self._camera_combo.currentData()
        if device_id is None:
            self._pending_device_ids = [d.id for d in self._devices]
            self._fetch_next_device()
        else:
            self._pending_device_ids = []
            self._start_fetch(device_id)

    def _fetch_next_device(self):
        if not self._pending_device_ids:
            self._on_all_fetched()
            return
        self._start_fetch(self._pending_device_ids.pop(0))

    def _start_fetch(self, device_id: int):
        self._fetch_thread = _FetchRecordingsThread(self._client, device_id)
        self._fetch_thread.recordings_ready.connect(self._on_fetch_finished)
        self._fetch_thread.fetch_error.connect(self._on_fetch_error)
        self._fetch_thread.start()

    def _on_fetch_finished(self, device_id: int, recordings: list):
        self._all_recordings.extend(recordings)
        # Defer to the next event-loop tick so the just-finished QThread can
        # complete its SIP/GIL cleanup before its Python reference is dropped.
        if self._pending_device_ids:
            QTimer.singleShot(0, self._fetch_next_device)
        else:
            QTimer.singleShot(0, self._on_all_fetched)

    def _on_fetch_error(self, device_id: int, msg: str):
        name = self._device_map.get(device_id, str(device_id))
        self._set_status(f"Error loading {name}: {msg}")
        if self._pending_device_ids:
            QTimer.singleShot(0, self._fetch_next_device)
        else:
            QTimer.singleShot(0, self._on_all_fetched)

    def _on_all_fetched(self):
        self._progress.hide()
        self._refresh_btn.setEnabled(True)
        self._apply_filters()
        self._start_thumbnail_loading()

    # ── Filtering ─────────────────────────────────────────────────────────────

    def _apply_filters(self):
        import time as _time
        now_ts    = _time.time()
        device_id = self._camera_combo.currentData()

        if getattr(self, "_hours_filter", 0) > 0:
            from_ts = now_ts - self._hours_filter * 3600
            to_ts   = now_ts
        else:
            from_d  = self._from_date.date().toPyDate()
            to_d    = self._to_date.date().toPyDate()
            from_ts = datetime(from_d.year, from_d.month, from_d.day).timestamp()
            to_ts   = datetime(to_d.year, to_d.month, to_d.day, 23, 59, 59).timestamp()

        visible = [
            r for r in self._all_recordings
            if (device_id is None or r.device_id == device_id)
            and (r.time is None or from_ts <= r.time <= to_ts)
        ]
        visible.sort(key=lambda r: r.time or 0, reverse=True)
        self._populate_list(visible)

    def _quick_filter(self, val: int):
        if val < 0:
            self._hours_filter = -val
            self._apply_filters()
        else:
            self._hours_filter = 0
            to = QDate.currentDate()
            self._from_date.setDate(to if val == 0 else to.addDays(-val))
            self._to_date.setDate(to)

    def _populate_list(self, recordings: list[RecordingEvent]):
        self._list.clear()
        self._item_widgets.clear()
        for r in recordings:
            name   = self._device_map.get(r.device_id or 0, "Camera")
            widget = _RecordingItemWidget(r, name)
            item   = QListWidgetItem()
            item.setSizeHint(QSize(self._list.width() or 340, _ITEM_H))
            item.setData(Qt.ItemDataRole.UserRole, r)
            self._list.addItem(item)
            self._list.setItemWidget(item, widget)
            if r.media_id is not None:
                self._item_widgets[r.media_id] = widget

        n, total = len(recordings), len(self._all_recordings)
        self._count_lbl.setText(
            f"  {n} recording{'s' if n != 1 else ''}"
            if n == total else f"  {n} of {total} recordings"
        )

    def _on_camera_changed(self, _):
        device_id = self._camera_combo.currentData()
        if device_id is None or any(r.device_id == device_id
                                    for r in self._all_recordings):
            self._apply_filters()
        else:
            self._load_recordings()

    # ── Thumbnails ────────────────────────────────────────────────────────────

    def _start_thumbnail_loading(self):
        if self._thumb_thread and self._thumb_thread.isRunning():
            self._thumb_thread.stop()
            self._thumb_thread.wait(500)
        jobs = []
        for r in self._all_recordings:
            if r.media_id is None:
                continue
            # Try screenshot endpoint first, fall back to live JPEG snapshot
            urls = [
                self._server.media_screenshot_url(r.media_id),
                self._server.jpeg_url(r.device_id) if r.device_id else None,
            ]
            jobs.append((r.media_id, [u for u in urls if u]))
        if not jobs:
            return
        self._thumb_thread = _ThumbnailThread(self._server, jobs)
        self._thumb_thread.loaded.connect(self._on_thumbnail_loaded)
        self._thumb_thread.start()

    def _on_thumbnail_loaded(self, media_id: int, data: bytes):
        w = self._item_widgets.get(media_id)
        if w:
            w.set_thumbnail(data)

    # ── Selection ─────────────────────────────────────────────────────────────

    def _on_current_item_changed(self, current: QListWidgetItem, _):
        """Tracks the focused item and updates the info label."""
        if current is None:
            self._current_recording = None
            self._sel_info_lbl.setText("Select a recording")
            return
        r: RecordingEvent = current.data(Qt.ItemDataRole.UserRole)
        if r is None:
            return
        self._current_recording = r
        cam      = self._device_map.get(r.device_id or 0, "Camera")
        date_str = r.date.strftime("%Y-%m-%d %H:%M") if r.date else ""
        dur_str  = f"  ·  {r.duration_description}" if r.duration_description else ""
        self._sel_info_lbl.setText(f"{cam}  ·  {date_str}{dur_str}")

    def _on_selection_changed(self):
        """Updates buttons and auto-plays when selection changes."""
        selected = self._list.selectedItems()
        n = len(selected)
        downloadable = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected
            if item.data(Qt.ItemDataRole.UserRole) is not None
            and item.data(Qt.ItemDataRole.UserRole).media_id is not None
        ]
        n_dl   = len(downloadable)
        single = (n == 1 and self._current_recording is not None
                  and self._current_recording.media_id is not None)

        self._play_sel_btn.setEnabled(single)
        self._save_sel_btn.setEnabled(n_dl > 0)
        self._save_sel_btn.setText(
            f"💾  Download ({n_dl})" if n_dl > 1 else "💾  Download"
        )
        if n > 1:
            self._sel_info_lbl.setText(f"{n} recordings selected")
        elif n == 0:
            self._sel_info_lbl.setText("Select a recording")

        if n == 1 and self._current_recording is not None:
            if self._current_recording.media_id is None:
                self._player.show_placeholder("No media file for this recording.")
            elif self._player.has_loaded_media:
                # Auto-switch when player already has something loaded
                self._play_recording(self._current_recording)

    # ── Context menu ──────────────────────────────────────────────────────────

    def _on_context_menu(self, pos: QPoint):
        item = self._list.itemAt(pos)
        if item is None:
            return
        r: RecordingEvent = item.data(Qt.ItemDataRole.UserRole)
        if r is None:
            return

        selected = self._list.selectedItems()
        multi    = len(selected) > 1 and item in selected
        dl_targets = [
            i.data(Qt.ItemDataRole.UserRole) for i in (selected if multi else [item])
            if i.data(Qt.ItemDataRole.UserRole) is not None
            and i.data(Qt.ItemDataRole.UserRole).media_id is not None
        ]

        menu = QMenu(self)
        play_act     = menu.addAction("▶  Play")
        dl_label     = (f"💾  Download {len(dl_targets)} recordings…"
                        if multi else "💾  Download to disk…")
        download_act = menu.addAction(dl_label)
        play_act.setEnabled(r.media_id is not None and not multi)
        download_act.setEnabled(len(dl_targets) > 0)

        chosen = menu.exec(self._list.mapToGlobal(pos))
        if chosen == play_act:
            self._play_recording(r)
        elif chosen == download_act:
            if len(dl_targets) > 1:
                self._start_batch_save(dl_targets)
            elif dl_targets:
                self._save_recording(dl_targets[0])

    # ── Playback ──────────────────────────────────────────────────────────────

    def _play_selected(self):
        if self._current_recording:
            self._play_recording(self._current_recording)

    def _play_recording(self, r: RecordingEvent):
        if r.media_id is not None and r.media_id in self._cached_paths:
            path = self._cached_paths[r.media_id]
            if os.path.exists(path):
                self._play_cached(path, r)
                return

        if self._dl_thread and self._dl_thread.isRunning():
            self._dl_thread.terminate()
            self._dl_thread.wait()

        self._player.show_placeholder("Downloading for playback…")
        self._dl_lbl.setText(f"Fetching  {r.title}…")
        self._dl_bar.show()
        self._dl_thread = _DownloadThread(self._client, r)
        self._dl_thread.download_ready.connect(lambda path: self._on_play_download_done(path, r))
        self._dl_thread.dl_error.connect(self._on_download_error)
        self._dl_thread.start()

    def _play_cached(self, path: str, r: RecordingEvent):
        cam      = self._device_map.get(r.device_id or 0, "Camera")
        date_str = r.date.strftime("%Y-%m-%d %H:%M") if r.date else ""
        self._player.play_file(
            path, f"{cam}  ·  {date_str}  ·  {r.duration_description or ''}"
        )

    def _on_play_download_done(self, path: str, r: RecordingEvent):
        self._dl_bar.hide()
        if r.media_id is not None:
            self._cached_paths[r.media_id] = path
        self._play_cached(path, r)

    # ── Save to disk ──────────────────────────────────────────────────────────

    def _save_selected(self):
        selected = self._list.selectedItems()
        recordings = [
            item.data(Qt.ItemDataRole.UserRole) for item in selected
            if item.data(Qt.ItemDataRole.UserRole) is not None
            and item.data(Qt.ItemDataRole.UserRole).media_id is not None
        ]
        if not recordings:
            return
        if len(recordings) == 1:
            self._save_recording(recordings[0])
        else:
            self._start_batch_save(recordings)

    def _save_recording(self, r: RecordingEvent):
        cam      = self._device_map.get(r.device_id or 0, "Camera")
        date_str = r.date.strftime("%Y%m%d_%H%M%S") if r.date else "recording"
        default  = f"{cam}_{date_str}.mp4".replace("/", "-").replace(":", "-")

        dest, _ = QFileDialog.getSaveFileName(
            self, "Save Recording", default,
            "Video Files (*.mp4 *.mkv);;All Files (*)"
        )
        if not dest:
            return

        # If already cached, copy immediately
        if r.media_id is not None and r.media_id in self._cached_paths:
            src = self._cached_paths[r.media_id]
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dest)
                    self._set_status(f"Saved to {dest}")
                except Exception as e:
                    self._set_status(f"Save failed: {e}")
                return

        # Otherwise download directly to destination
        if self._save_thread and self._save_thread.isRunning():
            self._save_thread.terminate()
            self._save_thread.wait()

        self._dl_lbl.setText(f"Saving  {r.title}…")
        self._dl_bar.show()
        self._save_sel_btn.setEnabled(False)

        self._save_thread = _SaveThread(self._client, r, dest)
        self._save_thread.save_complete.connect(self._on_save_done)
        self._save_thread.save_error.connect(self._on_save_error)
        self._save_thread.start()

    def _on_save_done(self, dest: str):
        self._dl_bar.hide()
        if self._current_recording:
            self._save_sel_btn.setEnabled(True)
        self._set_status(f"✓ Saved to {dest}")

    def _on_save_error(self, msg: str):
        self._dl_bar.hide()
        if self._current_recording:
            self._save_sel_btn.setEnabled(True)
        self._set_status(f"⚠ Save failed: {msg}")

    # ── Batch download ────────────────────────────────────────────────────────

    def _start_batch_save(self, recordings: list):
        dest_dir = QFileDialog.getExistingDirectory(
            self, f"Save {len(recordings)} Recordings To Folder",
            os.path.expanduser("~")
        )
        if not dest_dir:
            return
        self._batch_queue = list(recordings)
        self._batch_total = len(recordings)
        self._batch_dir   = dest_dir
        self._process_batch()

    def _process_batch(self):
        if not self._batch_queue:
            self._dl_bar.hide()
            n = self._batch_total
            self._save_sel_btn.setEnabled(True)
            self._set_status(f"✓ Saved {n} recording{'s' if n != 1 else ''}")
            self._batch_total = 0
            return

        r    = self._batch_queue.pop(0)
        done = self._batch_total - len(self._batch_queue)
        cam  = self._device_map.get(r.device_id or 0, "Camera")
        ts   = r.date.strftime("%Y%m%d_%H%M%S") if r.date else "recording"
        dest = os.path.join(
            self._batch_dir,
            f"{cam}_{ts}.mp4".replace("/", "-").replace(":", "-")
        )

        self._dl_lbl.setText(f"Saving {done}/{self._batch_total}…")
        self._dl_bar.show()
        self._save_sel_btn.setEnabled(False)

        if r.media_id is not None and r.media_id in self._cached_paths:
            src = self._cached_paths[r.media_id]
            if os.path.exists(src):
                try:
                    shutil.copy2(src, dest)
                except Exception as e:
                    self._set_status(f"⚠ {e}")
                QTimer.singleShot(0, self._process_batch)
                return

        if self._save_thread and self._save_thread.isRunning():
            self._save_thread.terminate()
            self._save_thread.wait()

        self._save_thread = _SaveThread(self._client, r, dest)
        self._save_thread.save_complete.connect(lambda _: self._process_batch())
        self._save_thread.save_error.connect(self._on_batch_save_error)
        self._save_thread.start()

    def _on_batch_save_error(self, msg: str):
        self._set_status(f"⚠ {msg} (skipping…)")
        QTimer.singleShot(0, self._process_batch)

    def _on_download_error(self, msg: str):
        self._dl_bar.hide()
        self._player.show_placeholder(f"⚠ Download failed:\n{msg}")
        self._set_status(f"Download failed: {msg}")

    def _set_status(self, msg: str):
        self._status_lbl.setText(f"  {msg}")

    # ── Cleanup ───────────────────────────────────────────────────────────────

    def _stop_threads(self):
        for t in (self._fetch_thread, self._thumb_thread,
                  self._dl_thread, self._save_thread):
            if t and t.isRunning():
                t.terminate()
                t.wait(300)

    def closeEvent(self, event):
        self._stop_threads()
        super().closeEvent(event)


# ── Standalone window wrapper ─────────────────────────────────────────────────

class RecordingsBrowserWindow(QMainWindow):
    def __init__(self, server: Server, devices: list[Device],
                 initial_device: Optional[Device] = None):
        super().__init__()
        self.setWindowTitle(f"Recordings — {server.name}")
        self.resize(1100, 700)
        widget = RecordingsBrowserWidget(server, devices, initial_device, self)
        self.setCentralWidget(widget)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _lbl(text: str) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet("color:#aaa; font-size:11px;")
    return l


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.VLine)
    f.setStyleSheet("color:#444;")
    return f
