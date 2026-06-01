"""
Pi5 Provisioning Tab -- BLE QR code provisioning, software deployment, and device management.

Provides SSH-based management of the Pi5 edge unit:
- Generate and display QR codes for phone pairing
- Show current QR for connected Pi5 device
- Install/update Pi5 software files and systemd service
- Security management (reset keys, clear whitelist, clear sessions)
- Device status monitoring (CPU temp, RAM, BLE service, etc.)
"""

import logging
import os
from io import BytesIO
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QGroupBox, QFormLayout, QMessageBox, QScrollArea,
    QFrame, QFileDialog, QProgressBar, QTextEdit,
)
from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QPixmap, QFont, QPainter

from predict.desktop.pi5_ssh import Pi5SSH

logger = logging.getLogger(__name__)

# Try importing QR / image / print libraries (optional deps)
try:
    import qrcode
    _has_qrcode = True
except ImportError:
    _has_qrcode = False

try:
    from PySide6.QtPrintSupport import QPrintDialog, QPrinter
    _has_print = True
except ImportError:
    _has_print = False


# ===================================================================
# Styles (dark theme, consistent with other tabs)
# ===================================================================

_BTN_PRIMARY = (
    "QPushButton { background-color: #C40000; color: white; "
    "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background-color: #e04040; }"
    "QPushButton:disabled { background-color: #555; color: #999; }"
)

_BTN_SECONDARY = (
    "QPushButton { background-color: #21262D; color: #C9D1D9; "
    "padding: 6px 14px; border: 1px solid #30363D; border-radius: 4px; }"
    "QPushButton:hover { background-color: #30363D; }"
    "QPushButton:disabled { background-color: #161B22; color: #555; }"
)

_BTN_DANGER = (
    "QPushButton { background-color: #f85149; color: white; "
    "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background-color: #ff6e6e; }"
    "QPushButton:disabled { background-color: #555; color: #999; }"
)

_BTN_SUCCESS = (
    "QPushButton { background-color: #2ea043; color: white; "
    "padding: 8px 16px; border-radius: 4px; font-weight: bold; }"
    "QPushButton:hover { background-color: #3fb950; }"
    "QPushButton:disabled { background-color: #555; color: #999; }"
)

_GROUP_STYLE = (
    "QGroupBox { border: 1px solid #30363D; border-radius: 6px; "
    "margin-top: 12px; padding-top: 16px; color: #C9D1D9; font-weight: bold; }"
    "QGroupBox::title { subcontrol-origin: margin; left: 12px; padding: 0 6px; }"
)

_INPUT_STYLE = (
    "QLineEdit { background-color: #0D1117; color: #C9D1D9; "
    "border: 1px solid #30363D; border-radius: 4px; padding: 6px 10px; }"
    "QLineEdit:focus { border-color: #C40000; }"
)

_LOG_STYLE = (
    "QTextEdit { background-color: #0D1117; color: #C9D1D9; "
    "border: 1px solid #30363D; border-radius: 4px; padding: 6px; "
    "font-family: 'Consolas', 'Courier New', monospace; font-size: 11px; }"
)

_PROGRESS_STYLE = (
    "QProgressBar { border: 1px solid #30363D; border-radius: 4px; "
    "background-color: #0D1117; text-align: center; color: #C9D1D9; }"
    "QProgressBar::chunk { background-color: #2ea043; border-radius: 3px; }"
)

_LABEL_DIM = "color: #8B949E; font-size: 12px;"
_LABEL_VALUE = "color: #C9D1D9; font-size: 13px; font-weight: bold;"
_LABEL_OK = "color: #3fb950; font-weight: bold;"
_LABEL_ERR = "color: #f85149; font-weight: bold;"

# Default Pi5 software directory (local files to deploy)
_DEFAULT_PI5_SRC = r"c:\tmp\pi5-deploy"


# ===================================================================
# Worker Threads
# ===================================================================

class SSHWorker(QThread):
    """Run a Pi5SSH method in a background thread."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ssh: Pi5SSH, operation: str, **kwargs):
        super().__init__()
        self._ssh = ssh
        self._op = operation
        self._kwargs = kwargs

    def run(self):
        try:
            if not self._ssh.connect():
                self.error.emit("Cannot connect to Pi5 at %s" % self._ssh._host)
                return
            method = getattr(self._ssh, self._op)
            result = method(**self._kwargs)
            self.finished.emit({"result": result})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._ssh.disconnect()


class _QRGenerateWorker(QThread):
    """Read BLE MAC and generate a new secret key on the Pi5."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ssh: Pi5SSH):
        super().__init__()
        self._ssh = ssh

    def run(self):
        try:
            if not self._ssh.connect():
                self.error.emit("Cannot connect to Pi5 at %s" % self._ssh._host)
                return
            mac = self._ssh.read_ble_mac()
            if not mac:
                self.error.emit("Could not read BLE MAC address. Is Bluetooth enabled on the Pi5?")
                return
            key = self._ssh.generate_and_write_key()
            self.finished.emit({"result": {"mac": mac, "key": key}})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._ssh.disconnect()


class _QRReadWorker(QThread):
    """Read current BLE MAC and existing secret key from Pi5 (no new key generation)."""
    finished = Signal(dict)
    error = Signal(str)

    def __init__(self, ssh: Pi5SSH):
        super().__init__()
        self._ssh = ssh

    def run(self):
        try:
            if not self._ssh.connect():
                self.error.emit("Cannot connect to Pi5 at %s" % self._ssh._host)
                return
            mac = self._ssh.read_ble_mac()
            if not mac:
                self.error.emit("Could not read BLE MAC address.")
                return
            # Read existing key (don't generate new one)
            try:
                key = self._ssh._exec(
                    f"cat {Pi5SSH.SECRET_KEY_FILE} 2>/dev/null || echo ''"
                ).strip()
            except Exception:
                key = ""
            self.finished.emit({"result": {"mac": mac, "key": key}})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._ssh.disconnect()


class _InstallWorker(QThread):
    """Install Pi5 software files via SSH."""
    finished = Signal(dict)
    error = Signal(str)
    progress = Signal(str, int, int)  # filename, current, total

    def __init__(self, ssh: Pi5SSH, local_dir: str, install_service: bool = True):
        super().__init__()
        self._ssh = ssh
        self._local_dir = local_dir
        self._install_service = install_service

    def run(self):
        try:
            if not self._ssh.connect():
                self.error.emit("Cannot connect to Pi5 at %s" % self._ssh._host)
                return
            result = self._ssh.install_software(
                self._local_dir,
                progress_cb=lambda f, c, t: self.progress.emit(f, c, t),
            )
            if self._install_service:
                svc_status = self._ssh.install_service()
                result["service_status"] = svc_status
            self.finished.emit({"result": result})
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self._ssh.disconnect()


# ===================================================================
# Pi5 Provisioning Tab
# ===================================================================

class Pi5ProvisioningTab(QWidget):
    """Tab for Pi5 BLE provisioning, software deployment, and device management."""

    def __init__(self, api_client, parent=None):
        super().__init__(parent)
        self._api_client = api_client
        self._current_qr_pixmap: Optional[QPixmap] = None
        self._current_deep_link: str = ""
        self._workers: list = []
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI Setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(scroll)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setSpacing(14)
        layout.setContentsMargins(16, 16, 16, 16)
        scroll.setWidget(container)

        # 1. Pi5 Connection
        layout.addWidget(self._build_connection_section())

        # 2. Current QR Code (read from connected device)
        layout.addWidget(self._build_current_qr_section())

        # 3. Generate New QR Code
        layout.addWidget(self._build_qr_section())

        # 4. Export / Print
        layout.addWidget(self._build_export_section())

        # 5. Software Installation
        layout.addWidget(self._build_install_section())

        # 6. Security Management
        layout.addWidget(self._build_security_section())

        # 7. Device Status
        layout.addWidget(self._build_status_section())

        layout.addStretch()

    # ------ Section 1: Connection ------

    def _build_connection_section(self) -> QGroupBox:
        group = QGroupBox("Pi5 Connection")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        form = QFormLayout()
        form.setSpacing(8)

        self._host_input = QLineEdit("192.168.5.1")
        self._host_input.setStyleSheet(_INPUT_STYLE)
        self._host_input.setPlaceholderText("Pi5 IP address")
        form.addRow("Host:", self._host_input)

        self._user_input = QLineEdit("predict")
        self._user_input.setStyleSheet(_INPUT_STYLE)
        form.addRow("Username:", self._user_input)

        self._pass_input = QLineEdit("12345678")
        self._pass_input.setStyleSheet(_INPUT_STYLE)
        self._pass_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._pass_input)

        layout.addLayout(form)

        btn_row = QHBoxLayout()
        self._test_btn = QPushButton("Test Connection")
        self._test_btn.setStyleSheet(_BTN_PRIMARY)
        self._test_btn.clicked.connect(self._on_test_connection)
        btn_row.addWidget(self._test_btn)
        btn_row.addStretch()

        self._conn_status = QLabel("Not connected")
        self._conn_status.setStyleSheet(_LABEL_DIM)
        btn_row.addWidget(self._conn_status)
        layout.addLayout(btn_row)

        return group

    # ------ Section 2: Current QR Code (from connected device) ------

    def _build_current_qr_section(self) -> QGroupBox:
        group = QGroupBox("Current Device QR Code")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        desc = QLabel(
            "Show the QR code for the currently connected Pi5 device using its existing secret key. "
            "Use this to print or share the QR without generating a new key."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(_LABEL_DIM)
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self._show_current_qr_btn = QPushButton("Show Current QR")
        self._show_current_qr_btn.setStyleSheet(_BTN_SECONDARY)
        self._show_current_qr_btn.clicked.connect(self._on_show_current_qr)
        btn_row.addWidget(self._show_current_qr_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # QR display
        qr_frame = QFrame()
        qr_frame.setStyleSheet(
            "QFrame { background-color: #0D1117; border: 1px solid #30363D; border-radius: 6px; }"
        )
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._current_device_qr = QLabel("Connect to a Pi5 and click 'Show Current QR'")
        self._current_device_qr.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_device_qr.setStyleSheet(_LABEL_DIM)
        self._current_device_qr.setMinimumSize(300, 300)
        qr_layout.addWidget(self._current_device_qr)

        self._current_device_link = QLabel("")
        self._current_device_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._current_device_link.setStyleSheet("color: #58a6ff; font-size: 11px;")
        self._current_device_link.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._current_device_link.setWordWrap(True)
        qr_layout.addWidget(self._current_device_link)

        layout.addWidget(qr_frame)

        return group

    # ------ Section 3: Generate New QR Code ------

    def _build_qr_section(self) -> QGroupBox:
        group = QGroupBox("Generate New QR Code")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        desc = QLabel(
            "Generate a NEW secret key and QR code. This replaces the existing key on the Pi5. "
            "Phones paired with the old key will need to re-scan the new QR."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #d29922; font-size: 12px;")
        layout.addWidget(desc)

        btn_row = QHBoxLayout()
        self._generate_qr_btn = QPushButton("Generate New Key + QR")
        self._generate_qr_btn.setStyleSheet(_BTN_SUCCESS)
        self._generate_qr_btn.clicked.connect(self._on_generate_qr)
        btn_row.addWidget(self._generate_qr_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # QR display area
        qr_frame = QFrame()
        qr_frame.setStyleSheet(
            "QFrame { background-color: #0D1117; border: 1px solid #30363D; border-radius: 6px; }"
        )
        qr_layout = QVBoxLayout(qr_frame)
        qr_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._qr_label = QLabel("No new QR code generated yet")
        self._qr_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._qr_label.setStyleSheet(_LABEL_DIM)
        self._qr_label.setMinimumSize(300, 300)
        qr_layout.addWidget(self._qr_label)

        self._deep_link_label = QLabel("")
        self._deep_link_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._deep_link_label.setStyleSheet("color: #58a6ff; font-size: 11px;")
        self._deep_link_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._deep_link_label.setWordWrap(True)
        qr_layout.addWidget(self._deep_link_label)

        layout.addWidget(qr_frame)

        return group

    # ------ Section 4: Export / Print ------

    def _build_export_section(self) -> QGroupBox:
        group = QGroupBox("Export / Print")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QHBoxLayout(group)

        self._save_png_btn = QPushButton("Save PNG")
        self._save_png_btn.setStyleSheet(_BTN_SECONDARY)
        self._save_png_btn.setEnabled(False)
        self._save_png_btn.clicked.connect(self._on_save_png)
        layout.addWidget(self._save_png_btn)

        self._print_btn = QPushButton("Print")
        self._print_btn.setStyleSheet(_BTN_SECONDARY)
        self._print_btn.setEnabled(False)
        self._print_btn.clicked.connect(self._on_print)
        layout.addWidget(self._print_btn)

        self._copy_link_btn = QPushButton("Copy Link")
        self._copy_link_btn.setStyleSheet(_BTN_SECONDARY)
        self._copy_link_btn.setEnabled(False)
        self._copy_link_btn.clicked.connect(self._on_copy_link)
        layout.addWidget(self._copy_link_btn)

        layout.addStretch()

        return group

    # ------ Section 5: Software Installation ------

    def _build_install_section(self) -> QGroupBox:
        group = QGroupBox("Software Installation")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        desc = QLabel(
            "Deploy PREDICT software to the Pi5. This uploads all Python files, "
            "installs the systemd service, and restarts the predict service."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(_LABEL_DIM)
        layout.addWidget(desc)

        # Source directory
        dir_row = QHBoxLayout()
        dir_label = QLabel("Source:")
        dir_label.setStyleSheet(_LABEL_DIM)
        dir_row.addWidget(dir_label)

        self._install_dir_input = QLineEdit(_DEFAULT_PI5_SRC)
        self._install_dir_input.setStyleSheet(_INPUT_STYLE)
        self._install_dir_input.setPlaceholderText("Local directory with Pi5 .py files")
        dir_row.addWidget(self._install_dir_input)

        browse_btn = QPushButton("Browse")
        browse_btn.setStyleSheet(_BTN_SECONDARY)
        browse_btn.clicked.connect(self._on_browse_install_dir)
        dir_row.addWidget(browse_btn)
        layout.addLayout(dir_row)

        # Action buttons
        btn_row = QHBoxLayout()

        self._install_btn = QPushButton("Install / Update Software")
        self._install_btn.setStyleSheet(_BTN_SUCCESS)
        self._install_btn.clicked.connect(self._on_install_software)
        btn_row.addWidget(self._install_btn)

        self._install_service_btn = QPushButton("Install Service Only")
        self._install_service_btn.setStyleSheet(_BTN_SECONDARY)
        self._install_service_btn.clicked.connect(self._on_install_service_only)
        btn_row.addWidget(self._install_service_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Progress bar
        self._install_progress = QProgressBar()
        self._install_progress.setStyleSheet(_PROGRESS_STYLE)
        self._install_progress.setVisible(False)
        layout.addWidget(self._install_progress)

        # Install log
        self._install_log = QTextEdit()
        self._install_log.setStyleSheet(_LOG_STYLE)
        self._install_log.setReadOnly(True)
        self._install_log.setMaximumHeight(150)
        self._install_log.setVisible(False)
        layout.addWidget(self._install_log)

        return group

    # ------ Section 6: Security Management ------

    def _build_security_section(self) -> QGroupBox:
        group = QGroupBox("Security Management")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        warn = QLabel(
            "These actions affect the Pi5 unit directly. "
            "Resetting security will invalidate all existing phone pairings."
        )
        warn.setWordWrap(True)
        warn.setStyleSheet("color: #d29922; font-size: 12px;")
        layout.addWidget(warn)

        btn_row = QHBoxLayout()

        self._reset_security_btn = QPushButton("Reset Security")
        self._reset_security_btn.setStyleSheet(_BTN_DANGER)
        self._reset_security_btn.setToolTip("Generate new key, clear whitelist, clear sessions, restart BLE")
        self._reset_security_btn.clicked.connect(self._on_reset_security)
        btn_row.addWidget(self._reset_security_btn)

        self._view_whitelist_btn = QPushButton("View Whitelist")
        self._view_whitelist_btn.setStyleSheet(_BTN_SECONDARY)
        self._view_whitelist_btn.clicked.connect(self._on_view_whitelist)
        btn_row.addWidget(self._view_whitelist_btn)

        self._clear_whitelist_btn = QPushButton("Clear Whitelist")
        self._clear_whitelist_btn.setStyleSheet(_BTN_DANGER)
        self._clear_whitelist_btn.clicked.connect(self._on_clear_whitelist)
        btn_row.addWidget(self._clear_whitelist_btn)

        self._restart_ble_btn = QPushButton("Restart Service")
        self._restart_ble_btn.setStyleSheet(_BTN_SECONDARY)
        self._restart_ble_btn.clicked.connect(self._on_restart_ble)
        btn_row.addWidget(self._restart_ble_btn)

        btn_row.addStretch()
        layout.addLayout(btn_row)

        self._security_status = QLabel("")
        self._security_status.setStyleSheet(_LABEL_DIM)
        self._security_status.setWordWrap(True)
        layout.addWidget(self._security_status)

        return group

    # ------ Section 7: Device Status ------

    def _build_status_section(self) -> QGroupBox:
        group = QGroupBox("Device Status")
        group.setStyleSheet(_GROUP_STYLE)
        layout = QVBoxLayout(group)

        btn_row = QHBoxLayout()
        self._refresh_status_btn = QPushButton("Refresh Status")
        self._refresh_status_btn.setStyleSheet(_BTN_SECONDARY)
        self._refresh_status_btn.clicked.connect(self._on_refresh_status)
        btn_row.addWidget(self._refresh_status_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Status grid
        grid = QFormLayout()
        grid.setSpacing(6)

        self._stat_cpu_temp = QLabel("--")
        self._stat_cpu_temp.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("CPU Temperature:"), self._stat_cpu_temp)

        self._stat_ram = QLabel("--")
        self._stat_ram.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("RAM Usage:"), self._stat_ram)

        self._stat_disk = QLabel("--")
        self._stat_disk.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("SD Card:"), self._stat_disk)

        self._stat_uptime = QLabel("--")
        self._stat_uptime.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("Uptime:"), self._stat_uptime)

        self._stat_ble = QLabel("--")
        self._stat_ble.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("Predict Service:"), self._stat_ble)

        self._stat_sessions = QLabel("--")
        self._stat_sessions.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("Active Sessions:"), self._stat_sessions)

        self._stat_whitelist = QLabel("--")
        self._stat_whitelist.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("Whitelisted Phones:"), self._stat_whitelist)

        self._stat_files = QLabel("--")
        self._stat_files.setStyleSheet(_LABEL_VALUE)
        grid.addRow(self._dim_label("Installed Files:"), self._stat_files)

        layout.addLayout(grid)

        return group

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _dim_label(text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setStyleSheet(_LABEL_DIM)
        return lbl

    def _get_ssh(self) -> Pi5SSH:
        """Create a Pi5SSH instance from current field values."""
        return Pi5SSH(
            host=self._host_input.text().strip() or "192.168.5.1",
            username=self._user_input.text().strip() or "predict",
            password=self._pass_input.text().strip() or "12345678",
        )

    def _run_ssh(self, operation: str, on_done, on_error=None, **kwargs):
        """Run an SSH operation in a background thread."""
        ssh = self._get_ssh()
        worker = SSHWorker(ssh, operation, **kwargs)
        worker.finished.connect(on_done)
        worker.error.connect(on_error or self._default_error)
        self._workers = [w for w in self._workers if not w.isFinished()]
        self._workers.append(worker)
        worker.start()

    def _default_error(self, msg: str):
        QMessageBox.critical(self, "SSH Error", msg)

    def _set_export_buttons(self, enabled: bool):
        self._save_png_btn.setEnabled(enabled)
        self._print_btn.setEnabled(enabled)
        self._copy_link_btn.setEnabled(enabled)

    def _render_qr(self, deep_link: str) -> Optional[QPixmap]:
        """Generate QR pixmap from a deep link string."""
        if not _has_qrcode:
            return None
        qr = qrcode.make(deep_link)
        buf = BytesIO()
        qr.save(buf, format="PNG")
        buf.seek(0)
        pixmap = QPixmap()
        pixmap.loadFromData(buf.read())
        return pixmap.scaled(
            300, 300,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # ------------------------------------------------------------------
    # Event Handlers
    # ------------------------------------------------------------------

    def _on_test_connection(self):
        self._conn_status.setText("Connecting...")
        self._conn_status.setStyleSheet("color: #d29922;")
        self._test_btn.setEnabled(False)

        def on_done(data):
            self._test_btn.setEnabled(True)
            info = data.get("result", {})
            if info.get("connected"):
                ble_text = "active" if info.get("ble_active") else "inactive"
                fw = info.get("firmware", "?")
                self._conn_status.setText(
                    f"Connected -- {info.get('hostname', '?')} | "
                    f"{info.get('uptime', '?')} | Service: {ble_text} | FW: {fw}"
                )
                self._conn_status.setStyleSheet(_LABEL_OK)
            else:
                self._conn_status.setText(f"Failed: {info.get('error', 'unknown')}")
                self._conn_status.setStyleSheet(_LABEL_ERR)

        def on_err(msg):
            self._test_btn.setEnabled(True)
            self._conn_status.setText(f"Error: {msg}")
            self._conn_status.setStyleSheet(_LABEL_ERR)

        self._run_ssh("test_connection", on_done, on_err)

    # --- Show Current QR ---

    def _on_show_current_qr(self):
        if not _has_qrcode:
            QMessageBox.warning(self, "Missing Dependency",
                                "qrcode library not installed.\nRun: pip install qrcode Pillow")
            return

        self._show_current_qr_btn.setEnabled(False)
        self._current_device_qr.setText("Reading from Pi5...")
        self._current_device_qr.setPixmap(QPixmap())
        self._current_device_link.setText("")

        def on_done(data):
            self._show_current_qr_btn.setEnabled(True)
            result = data.get("result", {})
            mac = result.get("mac")
            key = result.get("key")

            if not mac:
                self._current_device_qr.setText("Could not read BLE MAC from Pi5")
                self._current_device_qr.setStyleSheet(_LABEL_ERR)
                return

            if not key:
                self._current_device_qr.setText(
                    "No secret key found on Pi5. Generate a new QR code first."
                )
                self._current_device_qr.setStyleSheet("color: #d29922;")
                return

            deep_link = f"predict://pi5?mac={mac}&key={key}"
            try:
                pixmap = self._render_qr(deep_link)
                if pixmap:
                    self._current_device_qr.setPixmap(pixmap)
                    self._current_device_qr.setStyleSheet("")
                    self._current_device_link.setText(deep_link)
                    # Also make this the "active" QR for export
                    self._current_qr_pixmap = pixmap
                    self._current_deep_link = deep_link
                    self._set_export_buttons(True)
            except Exception as e:
                self._current_device_qr.setText(f"QR render failed: {e}")
                self._current_device_qr.setStyleSheet(_LABEL_ERR)

        def on_err(msg):
            self._show_current_qr_btn.setEnabled(True)
            self._current_device_qr.setText(f"Error: {msg}")
            self._current_device_qr.setStyleSheet(_LABEL_ERR)

        ssh = self._get_ssh()
        worker = _QRReadWorker(ssh)
        worker.finished.connect(on_done)
        worker.error.connect(on_err)
        self._workers = [w for w in self._workers if not w.isFinished()]
        self._workers.append(worker)
        worker.start()

    # --- Generate New QR ---

    def _on_generate_qr(self):
        if not _has_qrcode:
            QMessageBox.warning(self, "Missing Dependency",
                                "qrcode library is not installed.\nRun: pip install qrcode Pillow")
            return

        reply = QMessageBox.question(
            self, "Generate New Key",
            "This will replace the current secret key on the Pi5.\n"
            "Phones paired with the old key will need to re-scan.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._generate_qr_btn.setEnabled(False)
        self._qr_label.setText("Connecting to Pi5...")
        self._qr_label.setPixmap(QPixmap())
        self._deep_link_label.setText("")

        def on_done(data):
            self._generate_qr_btn.setEnabled(True)
            result = data.get("result", {})
            mac = result.get("mac")
            key = result.get("key")

            if not mac:
                self._qr_label.setText("Could not read BLE MAC address from Pi5")
                self._qr_label.setStyleSheet(_LABEL_ERR)
                return

            deep_link = f"predict://pi5?mac={mac}&key={key}"
            self._current_deep_link = deep_link

            try:
                pixmap = self._render_qr(deep_link)
                if pixmap:
                    self._current_qr_pixmap = pixmap
                    self._qr_label.setPixmap(pixmap)
                    self._qr_label.setStyleSheet("")
                    self._deep_link_label.setText(deep_link)
                    self._set_export_buttons(True)
            except Exception as e:
                self._qr_label.setText(f"QR generation failed: {e}")
                self._qr_label.setStyleSheet(_LABEL_ERR)

        def on_err(msg):
            self._generate_qr_btn.setEnabled(True)
            self._qr_label.setText(f"Error: {msg}")
            self._qr_label.setStyleSheet(_LABEL_ERR)

        ssh = self._get_ssh()
        worker = _QRGenerateWorker(ssh)
        worker.finished.connect(on_done)
        worker.error.connect(on_err)
        self._workers = [w for w in self._workers if not w.isFinished()]
        self._workers.append(worker)
        worker.start()

    # --- Export / Print ---

    def _on_save_png(self):
        if not self._current_qr_pixmap:
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Save QR Code", "predict_pi5_qr.png", "PNG Images (*.png)"
        )
        if path:
            self._current_qr_pixmap.save(path, "PNG")
            QMessageBox.information(self, "Saved", f"QR code saved to:\n{path}")

    def _on_print(self):
        if not _has_print:
            QMessageBox.warning(self, "Print Unavailable", "Print support not available.")
            return
        if not self._current_qr_pixmap:
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        dialog = QPrintDialog(printer, self)
        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            painter = QPainter(printer)
            try:
                rect = painter.viewport()
                size = self._current_qr_pixmap.size()
                size.scale(rect.size() * 0.6, Qt.AspectRatioMode.KeepAspectRatio)
                x = (rect.width() - size.width()) // 2
                y = rect.height() // 6

                title_font = QFont()
                title_font.setPointSize(18)
                title_font.setBold(True)
                painter.setFont(title_font)
                painter.drawText(rect.x(), rect.y() + 40, rect.width(), 60,
                                 Qt.AlignmentFlag.AlignHCenter, "PREDICT Pi5 Pairing QR Code")

                from PySide6.QtCore import QRect
                target = QRect(x, y + 80, size.width(), size.height())
                painter.drawPixmap(target, self._current_qr_pixmap)

                link_font = QFont()
                link_font.setPointSize(8)
                painter.setFont(link_font)
                painter.drawText(rect.x(), y + size.height() + 100, rect.width(), 40,
                                 Qt.AlignmentFlag.AlignHCenter, self._current_deep_link)
            finally:
                painter.end()

    def _on_copy_link(self):
        if self._current_deep_link:
            from PySide6.QtWidgets import QApplication
            clipboard = QApplication.clipboard()
            clipboard.setText(self._current_deep_link)
            QMessageBox.information(self, "Copied", "Deep link copied to clipboard.")

    # --- Software Installation ---

    def _on_browse_install_dir(self):
        path = QFileDialog.getExistingDirectory(
            self, "Select Pi5 Software Directory", self._install_dir_input.text()
        )
        if path:
            self._install_dir_input.setText(path)

    def _on_install_software(self):
        local_dir = self._install_dir_input.text().strip()
        if not local_dir or not os.path.isdir(local_dir):
            QMessageBox.warning(self, "Invalid Directory",
                                f"Directory not found: {local_dir}")
            return

        py_files = [f for f in os.listdir(local_dir) if f.endswith(".py")]
        if not py_files:
            QMessageBox.warning(self, "No Files", "No .py files found in the selected directory.")
            return

        reply = QMessageBox.question(
            self, "Install Software",
            f"This will upload {len(py_files)} Python files to the Pi5,\n"
            f"install the systemd service, and restart.\n\n"
            f"Files: {', '.join(py_files[:8])}{'...' if len(py_files) > 8 else ''}\n\n"
            f"The Pi5 service will restart after installation.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._install_btn.setEnabled(False)
        self._install_service_btn.setEnabled(False)
        self._install_progress.setVisible(True)
        self._install_progress.setValue(0)
        self._install_progress.setMaximum(len(py_files))
        self._install_log.setVisible(True)
        self._install_log.clear()
        self._install_log.append(f"Starting installation from {local_dir}...")

        ssh = self._get_ssh()
        worker = _InstallWorker(ssh, local_dir, install_service=True)

        def on_progress(fname, current, total):
            self._install_progress.setValue(current)
            self._install_log.append(f"  [{current}/{total}] Uploading {fname}")

        def on_done(data):
            self._install_btn.setEnabled(True)
            self._install_service_btn.setEnabled(True)
            result = data.get("result", {})
            installed = result.get("installed", [])
            errors = result.get("errors", [])
            skipped = result.get("skipped", [])
            svc = result.get("service_status", "unknown")

            self._install_progress.setValue(self._install_progress.maximum())
            self._install_log.append(f"\nInstalled: {len(installed)} files")
            if skipped:
                self._install_log.append(f"Skipped (not found locally): {', '.join(skipped)}")
            if errors:
                self._install_log.append(f"Errors: {len(errors)}")
                for e in errors:
                    self._install_log.append(f"  - {e}")
            self._install_log.append(f"Service status: {svc}")

            if not errors:
                self._install_log.append("\nInstallation complete!")
            else:
                self._install_log.append("\nInstallation completed with errors.")

        def on_err(msg):
            self._install_btn.setEnabled(True)
            self._install_service_btn.setEnabled(True)
            self._install_log.append(f"\nERROR: {msg}")

        worker.progress.connect(on_progress)
        worker.finished.connect(on_done)
        worker.error.connect(on_err)
        self._workers = [w for w in self._workers if not w.isFinished()]
        self._workers.append(worker)
        worker.start()

    def _on_install_service_only(self):
        reply = QMessageBox.question(
            self, "Install Service",
            "This will install/update the systemd service unit and restart.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._install_service_btn.setEnabled(False)
        self._install_log.setVisible(True)
        self._install_log.append("Installing systemd service...")

        def on_done(data):
            self._install_service_btn.setEnabled(True)
            status = data.get("result", "unknown")
            self._install_log.append(f"Service installed. Status: {status}")

        def on_err(msg):
            self._install_service_btn.setEnabled(True)
            self._install_log.append(f"ERROR: {msg}")

        self._run_ssh("install_service", on_done, on_err)

    # --- Security Management ---

    def _on_reset_security(self):
        reply = QMessageBox.warning(
            self, "Reset Security",
            "This will:\n"
            "  - Generate a new BLE secret key\n"
            "  - Clear all whitelisted phones\n"
            "  - Delete all active sessions\n"
            "  - Restart the service\n\n"
            "All existing phone pairings will stop working.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._reset_security_btn.setEnabled(False)
        self._security_status.setText("Resetting security...")
        self._security_status.setStyleSheet("color: #d29922;")

        def on_done(data):
            self._reset_security_btn.setEnabled(True)
            new_key = data.get("result", "")
            self._security_status.setText(
                f"Security reset complete. New key: {new_key[:8]}... "
                f"Generate a new QR code to pair phones."
            )
            self._security_status.setStyleSheet(_LABEL_OK)
            # Invalidate existing QR
            self._current_qr_pixmap = None
            self._current_deep_link = ""
            self._qr_label.setPixmap(QPixmap())
            self._qr_label.setText("QR invalidated -- generate a new one")
            self._qr_label.setStyleSheet("color: #d29922;")
            self._deep_link_label.setText("")
            self._current_device_qr.setPixmap(QPixmap())
            self._current_device_qr.setText("Key changed -- click 'Show Current QR' to refresh")
            self._current_device_qr.setStyleSheet("color: #d29922;")
            self._current_device_link.setText("")
            self._set_export_buttons(False)

        def on_err(msg):
            self._reset_security_btn.setEnabled(True)
            self._security_status.setText(f"Reset failed: {msg}")
            self._security_status.setStyleSheet(_LABEL_ERR)

        self._run_ssh("reset_security", on_done, on_err)

    def _on_view_whitelist(self):
        self._view_whitelist_btn.setEnabled(False)

        def on_done(data):
            self._view_whitelist_btn.setEnabled(True)
            macs = data.get("result", [])
            if not macs:
                QMessageBox.information(self, "Whitelist", "No phones are currently whitelisted.")
            else:
                text = "\n".join(f"  {i+1}. {m}" for i, m in enumerate(macs))
                QMessageBox.information(
                    self, "Whitelist", f"Whitelisted phones ({len(macs)}):\n\n{text}"
                )

        def on_err(msg):
            self._view_whitelist_btn.setEnabled(True)
            QMessageBox.critical(self, "Error", f"Could not read whitelist:\n{msg}")

        self._run_ssh("read_whitelist", on_done, on_err)

    def _on_clear_whitelist(self):
        reply = QMessageBox.warning(
            self, "Clear Whitelist",
            "This will remove all whitelisted phones.\n"
            "Paired phones will need to re-pair using a QR code.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._clear_whitelist_btn.setEnabled(False)
        self._security_status.setText("Clearing whitelist...")
        self._security_status.setStyleSheet("color: #d29922;")

        def on_done(_data):
            self._clear_whitelist_btn.setEnabled(True)
            self._security_status.setText("Whitelist cleared successfully.")
            self._security_status.setStyleSheet(_LABEL_OK)

        def on_err(msg):
            self._clear_whitelist_btn.setEnabled(True)
            self._security_status.setText(f"Clear failed: {msg}")
            self._security_status.setStyleSheet(_LABEL_ERR)

        self._run_ssh("clear_whitelist", on_done, on_err)

    def _on_restart_ble(self):
        self._restart_ble_btn.setEnabled(False)
        self._security_status.setText("Restarting service...")
        self._security_status.setStyleSheet("color: #d29922;")

        def on_done(_data):
            self._restart_ble_btn.setEnabled(True)
            self._security_status.setText("Service restarted.")
            self._security_status.setStyleSheet(_LABEL_OK)

        def on_err(msg):
            self._restart_ble_btn.setEnabled(True)
            self._security_status.setText(f"Restart failed: {msg}")
            self._security_status.setStyleSheet(_LABEL_ERR)

        self._run_ssh("restart_ble_service", on_done, on_err)

    # --- Device Status ---

    def _on_refresh_status(self):
        self._refresh_status_btn.setEnabled(False)

        def on_done(data):
            self._refresh_status_btn.setEnabled(True)
            status = data.get("result", {})

            if "error" in status:
                self._stat_cpu_temp.setText(f"Error: {status['error']}")
                self._stat_cpu_temp.setStyleSheet(_LABEL_ERR)
                return

            # CPU temp
            cpu_temp = status.get("cpu_temp", 0)
            temp_color = "#3fb950" if cpu_temp < 60 else ("#d29922" if cpu_temp < 75 else "#f85149")
            self._stat_cpu_temp.setText(f"{cpu_temp:.1f} C")
            self._stat_cpu_temp.setStyleSheet(f"color: {temp_color}; font-weight: bold;")

            # RAM
            ram_total = status.get("ram_total_mb", 0)
            ram_used = status.get("ram_used_mb", 0)
            ram_pct = (ram_used / ram_total * 100) if ram_total > 0 else 0
            ram_color = "#3fb950" if ram_pct < 70 else ("#d29922" if ram_pct < 90 else "#f85149")
            self._stat_ram.setText(f"{ram_used} / {ram_total} MB ({ram_pct:.0f}%)")
            self._stat_ram.setStyleSheet(f"color: {ram_color}; font-weight: bold;")

            # Disk
            sd_total = status.get("sd_total_gb", "?")
            sd_free = status.get("sd_free_gb", "?")
            self._stat_disk.setText(f"{sd_free} GB free / {sd_total} GB total")
            self._stat_disk.setStyleSheet(_LABEL_VALUE)

            # Uptime
            self._stat_uptime.setText(status.get("uptime", "--"))
            self._stat_uptime.setStyleSheet(_LABEL_VALUE)

            # Service
            ble = status.get("ble_service", "unknown")
            ble_color = "#3fb950" if ble == "active" else "#f85149"
            self._stat_ble.setText(ble)
            self._stat_ble.setStyleSheet(f"color: {ble_color}; font-weight: bold;")

            # Sessions
            self._stat_sessions.setText(str(status.get("session_count", 0)))
            self._stat_sessions.setStyleSheet(_LABEL_VALUE)

            # Whitelist
            wl_count = status.get("whitelist_count", 0)
            wl_macs = status.get("whitelist", [])
            wl_text = str(wl_count)
            if wl_macs:
                wl_text += " (" + ", ".join(wl_macs[:3])
                if len(wl_macs) > 3:
                    wl_text += f", +{len(wl_macs) - 3} more"
                wl_text += ")"
            self._stat_whitelist.setText(wl_text)
            self._stat_whitelist.setStyleSheet(_LABEL_VALUE)

            # Installed files
            self._stat_files.setText(str(status.get("installed_files", 0)) + " .py files")
            self._stat_files.setStyleSheet(_LABEL_VALUE)

        def on_err(msg):
            self._refresh_status_btn.setEnabled(True)
            self._stat_cpu_temp.setText(f"Error: {msg}")
            self._stat_cpu_temp.setStyleSheet(_LABEL_ERR)

        self._run_ssh("get_device_status", on_done, on_err)

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup(self):
        """Stop any running workers."""
        for w in self._workers:
            if w.isRunning():
                w.quit()
                w.wait(2000)
        self._workers.clear()
