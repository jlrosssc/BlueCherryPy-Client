from __future__ import annotations
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QPushButton, QLabel,
    QStackedWidget, QScrollArea, QGridLayout,
    QSplitter, QToolBar, QStatusBar, QMessageBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import QAction

from bluecherrypy.storage.server_store import ServerStore
from bluecherrypy.models.server import Server
from bluecherrypy.models.device import Device
from bluecherrypy.networking.client import BluecherryClient
from bluecherrypy.ui.views.add_server_dialog import AddServerDialog
from bluecherrypy.ui.views.camera_tile import CameraTileWidget
from bluecherrypy.ui.views.live_camera_window import LiveCameraWidget
from bluecherrypy.ui.views.recordings_browser import RecordingsBrowserWidget, RecordingsBrowserWindow

_NAV_BTN_STYLE = """
    QPushButton {
        border: 1px solid #555;
        border-radius: 5px;
        padding: 5px 22px;
        background: #3a3a3c;
        color: #aaa;
        font-size: 13px;
        font-weight: 500;
    }
    QPushButton:checked {
        background: #0a84ff;
        color: white;
        border-color: #0a84ff;
    }
    QPushButton:hover:!checked { background: #48484a; }
    QPushButton:disabled { color: #444; border-color: #333; }
"""


class _ConnectThread(QThread):
    finished = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, server: Server):
        super().__init__()
        self._server = server

    def run(self):
        try:
            self.finished.emit(BluecherryClient(self._server).connect())
        except Exception as e:
            self.error.emit(str(e))


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._store = ServerStore()
        self._tiles: list[CameraTileWidget] = []
        self._extra_windows: list[QWidget] = []
        self._connect_thread: _ConnectThread | None = None
        self._current_server: Server | None = None
        self._current_devices: list[Device] = []
        self._recordings_widget: RecordingsBrowserWidget | None = None
        self.setWindowTitle("BluecherryPy")
        self.resize(1200, 760)
        self._build_ui()
        self._refresh_server_list()

    # ── UI construction ───────────────────────────────────────────────────────

    def _build_ui(self):
        # --- Menu bar ---
        mb = self.menuBar()
        server_menu = mb.addMenu("Server")
        add_action = QAction("Add Server…", self)
        add_action.setShortcut("Ctrl+N")
        add_action.triggered.connect(self._on_add_server)
        server_menu.addAction(add_action)

        view_menu = mb.addMenu("View")
        self._live_action = QAction("Live Cameras", self)
        self._live_action.setShortcut("Ctrl+1")
        self._live_action.triggered.connect(lambda: self._switch_page(0))
        view_menu.addAction(self._live_action)
        self._rec_action = QAction("Recordings", self)
        self._rec_action.setShortcut("Ctrl+2")
        self._rec_action.setEnabled(False)
        self._rec_action.triggered.connect(lambda: self._switch_page(1))
        view_menu.addAction(self._rec_action)

        # --- Toolbar ---
        tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(16, 16))
        tb.addAction(add_action)
        self.addToolBar(tb)

        self._status = QStatusBar()
        self.setStatusBar(self._status)

        # --- Central layout: sidebar + content ---
        splitter = QSplitter(Qt.Orientation.Horizontal)

        splitter.addWidget(self._build_sidebar())
        splitter.addWidget(self._build_content_area())
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 1000])
        self.setCentralWidget(splitter)

    def _build_sidebar(self) -> QWidget:
        side = QWidget()
        side.setMinimumWidth(160)
        side.setMaximumWidth(220)
        side.setStyleSheet("background:#1c1c1e;")
        layout = QVBoxLayout(side)
        layout.setContentsMargins(8, 10, 8, 8)
        layout.setSpacing(6)

        title = QLabel("BluecherryPy")
        title.setStyleSheet("color:#fff; font-size:14px; font-weight:bold; padding:4px 2px 10px;")
        layout.addWidget(title)

        servers_lbl = QLabel("SERVERS")
        servers_lbl.setStyleSheet("color:#666; font-size:10px; font-weight:bold; padding:4px 2px 2px;")
        layout.addWidget(servers_lbl)

        self._server_list = QListWidget()
        self._server_list.setStyleSheet(
            "QListWidget{border:none; background:transparent; color:#ddd; font-size:13px;}"
            "QListWidget::item{padding:6px 4px; border-radius:5px;}"
            "QListWidget::item:selected{background:#2c5282; color:#fff;}"
            "QListWidget::item:hover:!selected{background:#2a2a3a;}"
        )
        self._server_list.currentRowChanged.connect(self._on_server_selected)
        layout.addWidget(self._server_list, stretch=1)

        btn_row = QHBoxLayout()
        self._edit_btn = QPushButton("Edit")
        self._edit_btn.setEnabled(False)
        self._edit_btn.setStyleSheet("font-size:11px; padding:3px 8px;")
        self._edit_btn.clicked.connect(self._on_edit_server)
        self._remove_btn = QPushButton("Remove")
        self._remove_btn.setEnabled(False)
        self._remove_btn.setStyleSheet("font-size:11px; padding:3px 8px;")
        self._remove_btn.clicked.connect(self._on_remove_server)
        btn_row.addWidget(self._edit_btn)
        btn_row.addWidget(self._remove_btn)
        layout.addLayout(btn_row)
        return side

    def _build_content_area(self) -> QWidget:
        area = QWidget()
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navigation bar
        nav = QWidget()
        nav.setFixedHeight(44)
        nav.setStyleSheet("background:#2c2c2e; border-bottom:1px solid #444;")
        nav_layout = QHBoxLayout(nav)
        nav_layout.setContentsMargins(14, 6, 14, 6)
        nav_layout.setSpacing(6)

        self._live_btn = QPushButton("Live")
        self._live_btn.setCheckable(True)
        self._live_btn.setChecked(True)
        self._live_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._live_btn.clicked.connect(lambda: self._switch_page(0))

        self._rec_btn = QPushButton("Recordings")
        self._rec_btn.setCheckable(True)
        self._rec_btn.setChecked(False)
        self._rec_btn.setEnabled(False)
        self._rec_btn.setStyleSheet(_NAV_BTN_STYLE)
        self._rec_btn.clicked.connect(lambda: self._switch_page(1))

        self._page_header = QLabel("")
        self._page_header.setStyleSheet("color:#888; font-size:12px; padding-left:12px;")

        nav_layout.addWidget(self._live_btn)
        nav_layout.addWidget(self._rec_btn)
        nav_layout.addWidget(self._page_header)
        nav_layout.addStretch()
        layout.addWidget(nav)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._build_live_page())    # index 0
        self._stack.addWidget(self._build_rec_placeholder())  # index 1 (replaced on connect)
        layout.addWidget(self._stack, stretch=1)
        return area

    def _build_live_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(0)

        self._camera_header = QLabel("Select a server to view cameras")
        self._camera_header.setStyleSheet("font-size:14px; color:#888; padding:8px;")
        layout.addWidget(self._camera_header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea{border:none;}")
        self._grid_container = QWidget()
        self._grid_layout = QGridLayout(self._grid_container)
        self._grid_layout.setSpacing(10)
        self._grid_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        scroll.setWidget(self._grid_container)
        layout.addWidget(scroll, stretch=1)
        return page

    def _build_rec_placeholder(self) -> QWidget:
        page = QWidget()
        page.setStyleSheet("background:#1c1c1e;")
        lbl = QLabel("Connect to a server to browse recordings")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color:#555; font-size:15px;")
        layout = QVBoxLayout(page)
        layout.addWidget(lbl)
        return page

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_page(self, idx: int):
        self._stack.setCurrentIndex(idx)
        self._live_btn.setChecked(idx == 0)
        self._rec_btn.setChecked(idx == 1)

    # ── Server list ───────────────────────────────────────────────────────────

    def _refresh_server_list(self):
        self._server_list.clear()
        for server in self._store.servers:
            label = f"★ {server.name}" if self._store.is_default(server) else server.name
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, server)
            self._server_list.addItem(item)
        if not self._store.servers:
            self._camera_header.setText("Add a server to get started.")

    def _on_server_selected(self, row: int):
        has = row >= 0
        self._edit_btn.setEnabled(has)
        self._remove_btn.setEnabled(has)
        if not has:
            return
        server = self._server_list.item(row).data(Qt.ItemDataRole.UserRole)
        self._load_cameras(server)

    def _load_cameras(self, server: Server):
        self._clear_live_grid(f"Connecting to {server.name}…")
        self._page_header.setText("")
        self._status.showMessage(f"Connecting to {server.name}…")
        self._connect_thread = _ConnectThread(server)
        self._connect_thread.finished.connect(lambda devs: self._on_devices_loaded(server, devs))
        self._connect_thread.error.connect(self._on_connect_error)
        self._connect_thread.start()

    @pyqtSlot(list)
    def _on_devices_loaded(self, server: Server, devices: list[Device]):
        self._current_server = server
        self._current_devices = devices
        self._status.showMessage(f"{len(devices)} camera(s) on {server.name}", 5000)
        self._clear_live_grid()

        if not devices:
            self._camera_header.setText(f"No cameras found on {server.name}")
            return

        self._camera_header.setText(f"{server.name}  —  {len(devices)} camera(s)")
        self._page_header.setText(server.name)
        cols = max(1, min(4, len(devices)))
        for i, device in enumerate(devices):
            tile = CameraTileWidget(server, device)
            tile.clicked.connect(self._open_live_view)
            self._grid_layout.addWidget(tile, i // cols, i % cols)
            tile.start_stream()
            self._tiles.append(tile)

        # Build / replace the recordings page
        self._install_recordings_widget(server, devices)

    @pyqtSlot(str)
    def _on_connect_error(self, msg: str):
        self._status.showMessage(f"Connection failed: {msg}", 8000)
        self._camera_header.setText(f"Connection failed: {msg}")

    def _install_recordings_widget(self, server: Server, devices: list[Device]):
        old = self._stack.widget(1)
        self._recordings_widget = RecordingsBrowserWidget(server, devices, parent=self)
        self._stack.removeWidget(old)
        old.deleteLater()
        self._stack.insertWidget(1, self._recordings_widget)
        self._rec_btn.setEnabled(True)
        self._rec_action.setEnabled(True)

    # ── Live grid ─────────────────────────────────────────────────────────────

    def _clear_live_grid(self, message: str = ""):
        for tile in self._tiles:
            tile.stop_stream()
            tile.setParent(None)
        self._tiles.clear()
        while self._grid_layout.count():
            item = self._grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._camera_header.setText(message)

    # ── Sub-window launchers ──────────────────────────────────────────────────

    def _open_live_view(self, server: Server, device: Device):
        win = LiveCameraWidget(server, device)
        win.recordings_requested.connect(
            lambda s, d: self._open_recordings_window(s, self._current_devices, d)
        )
        win.resize(860, 660)
        win.setWindowTitle(f"{device.name} — {server.name}")
        win.show()
        self._extra_windows.append(win)

    def _open_recordings_window(self, server: Server, devices: list[Device],
                                  initial_device: Device | None = None):
        win = RecordingsBrowserWindow(server, devices, initial_device)
        win.show()
        self._extra_windows.append(win)

    # ── Server CRUD ───────────────────────────────────────────────────────────

    def _on_add_server(self):
        dlg = AddServerDialog(self)
        if dlg.exec():
            self._store.add(dlg.build_server())
            self._refresh_server_list()

    def _on_edit_server(self):
        row = self._server_list.currentRow()
        if row < 0:
            return
        server = self._server_list.item(row).data(Qt.ItemDataRole.UserRole)
        dlg = AddServerDialog(self, server)
        if dlg.exec():
            self._store.update(dlg.build_server())
            self._refresh_server_list()

    def _on_remove_server(self):
        row = self._server_list.currentRow()
        if row < 0:
            return
        server = self._server_list.item(row).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(
            self, "Remove Server", f"Remove '{server.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        ) == QMessageBox.StandardButton.Yes:
            self._store.remove(server)
            self._refresh_server_list()
            self._clear_live_grid("Select a server to view cameras.")

    def closeEvent(self, event):
        self._clear_live_grid()
        for win in self._extra_windows:
            win.close()
        super().closeEvent(event)
