"""
PID Atlas Browser Tab — Browse community-discovered manufacturer PIDs.

Left panel: list of vehicles (make/model) with PID counts.
Right panel: full PID table for selected vehicle (shown on double-click).
"""

import json
import logging
import time
from datetime import datetime
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QLabel, QPushButton, QHeaderView, QSplitter, QFrame,
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont

from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)


SEMANTIC_COLORS = {
    "temperature": QColor("#FF6B35"),
    "pressure": QColor("#4ECDC4"),
    "voltage": QColor("#FFE66D"),
    "speed": QColor("#95E1D3"),
    "counter": QColor("#A8D8EA"),
    "boolean": QColor("#AA96DA"),
    "sensor": QColor("#6BCB77"),
    "config": QColor("#8B949E"),
    "unknown": QColor("#6E7681"),
}


def _format_timestamp(ts: Optional[float]) -> str:
    if not ts:
        return "—"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OSError, ValueError):
        return "—"


class PIDAtlasTab(QWidget):
    """Tab for browsing the community PID atlas."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._worker: Optional[APIWorker] = None
        self._vehicles = []
        self._selected_make = ""
        self._selected_model = ""

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header bar
        header = QFrame()
        header.setFixedHeight(50)
        header.setStyleSheet(
            "QFrame { background-color: #0D1117; border-bottom: 1px solid #30363D; }"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 0, 16, 0)

        title = QLabel("🔧  PID Atlas Browser")
        title.setFont(QFont("Segoe UI", 14, QFont.Bold))
        title.setStyleSheet("color: #F0F6FC;")
        header_layout.addWidget(title)

        header_layout.addStretch()

        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #8B949E; font-size: 12px;")
        header_layout.addWidget(self._status_label)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setStyleSheet(
            "QPushButton { background-color: #21262D; color: #C9D1D9; "
            "padding: 6px 14px; border: 1px solid #30363D; border-radius: 4px; }"
            "QPushButton:hover { background-color: #30363D; }"
        )
        self._refresh_btn.clicked.connect(self._load_vehicles)
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header)

        # Splitter: vehicle list | PID detail
        self._splitter = QSplitter(Qt.Horizontal)
        self._splitter.setStyleSheet(
            "QSplitter { background: #0D1117; }"
            "QSplitter::handle { background: #30363D; width: 1px; }"
        )

        # Left: Vehicle list
        left = QFrame()
        left.setStyleSheet("QFrame { background: #0D1117; }")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 4, 8)

        left_header = QLabel("Vehicles with Discovered PIDs")
        left_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        left_header.setStyleSheet("color: #C9D1D9; padding: 4px;")
        left_layout.addWidget(left_header)

        self._vehicle_table = QTableWidget()
        self._vehicle_table.setColumnCount(5)
        self._vehicle_table.setHorizontalHeaderLabels([
            "Make", "Model", "Year Range", "PIDs", "Named"
        ])
        self._vehicle_table.verticalHeader().setVisible(False)
        self._vehicle_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._vehicle_table.setSelectionMode(QTableWidget.SingleSelection)
        self._vehicle_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._vehicle_table.doubleClicked.connect(self._on_vehicle_double_click)
        self._apply_table_style(self._vehicle_table)

        h = self._vehicle_table.horizontalHeader()
        h.setSectionResizeMode(0, QHeaderView.Stretch)
        h.setSectionResizeMode(1, QHeaderView.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        h.setSectionResizeMode(4, QHeaderView.ResizeToContents)

        left_layout.addWidget(self._vehicle_table)
        self._splitter.addWidget(left)

        # Right: PID detail table
        right = QFrame()
        right.setStyleSheet("QFrame { background: #0D1117; }")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 8, 8, 8)

        self._detail_header = QLabel("Double-click a vehicle to view PIDs")
        self._detail_header.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self._detail_header.setStyleSheet("color: #8B949E; padding: 4px;")
        right_layout.addWidget(self._detail_header)

        # Summary stats row
        self._stats_frame = QFrame()
        self._stats_frame.setVisible(False)
        stats_layout = QHBoxLayout(self._stats_frame)
        stats_layout.setContentsMargins(4, 0, 4, 4)
        stats_layout.setSpacing(16)
        self._stat_labels = {}
        for key in ("Total", "Dynamic", "Static", "Named", "Verified"):
            lbl = QLabel(f"{key}: —")
            lbl.setStyleSheet("color: #8B949E; font-size: 12px;")
            stats_layout.addWidget(lbl)
            self._stat_labels[key] = lbl
        stats_layout.addStretch()
        right_layout.addWidget(self._stats_frame)

        self._pid_table = QTableWidget()
        self._pid_table.setColumnCount(9)
        self._pid_table.setHorizontalHeaderLabels([
            "Service", "PID", "ECU", "Name", "Type", "Unit",
            "Dynamic", "Verified", "Discoveries"
        ])
        self._pid_table.verticalHeader().setVisible(False)
        self._pid_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._pid_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._pid_table.setSortingEnabled(True)
        self._apply_table_style(self._pid_table)

        ph = self._pid_table.horizontalHeader()
        ph.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(3, QHeaderView.Stretch)
        ph.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(6, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(7, QHeaderView.ResizeToContents)
        ph.setSectionResizeMode(8, QHeaderView.ResizeToContents)

        right_layout.addWidget(self._pid_table)
        self._splitter.addWidget(right)

        self._splitter.setSizes([350, 650])
        layout.addWidget(self._splitter)

    def _apply_table_style(self, table: QTableWidget):
        table.setStyleSheet("""
            QTableWidget {
                background-color: #0D1117;
                color: #C9D1D9;
                border: 1px solid #30363D;
                gridline-color: #21262D;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 8px;
            }
            QTableWidget::item:selected {
                background-color: #1F2937;
            }
            QHeaderView::section {
                background-color: #161B22;
                color: #8B949E;
                border: none;
                border-bottom: 1px solid #30363D;
                padding: 6px 8px;
                font-weight: bold;
                font-size: 11px;
            }
        """)

    # ===== Data loading =====

    def _load_vehicles(self):
        self._status_label.setText("Loading...")
        self._refresh_btn.setEnabled(False)

        def fetch():
            return self._api._request("GET", "/pids/atlas/vehicles")

        self._worker = APIWorker(fetch)
        self._worker.finished.connect(self._on_vehicles_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_vehicles_loaded(self, data):
        self._refresh_btn.setEnabled(True)
        vehicles = data.get("vehicles", [])
        self._vehicles = vehicles

        self._vehicle_table.setRowCount(len(vehicles))
        for i, v in enumerate(vehicles):
            make_item = QTableWidgetItem(v["make"])
            make_item.setForeground(QColor("#F0F6FC"))
            make_item.setFont(QFont("Segoe UI", 11, QFont.Bold))

            model_item = QTableWidgetItem(v["model"])
            model_item.setForeground(QColor("#C9D1D9"))

            year_range = f"{v.get('year_min', '?')} – {v.get('year_max', '?')}"
            year_item = QTableWidgetItem(year_range)
            year_item.setTextAlignment(Qt.AlignCenter)
            year_item.setForeground(QColor("#8B949E"))

            pid_item = QTableWidgetItem(str(v.get("pid_count", 0)))
            pid_item.setTextAlignment(Qt.AlignCenter)
            pid_item.setForeground(QColor("#58A6FF"))
            pid_item.setFont(QFont("Segoe UI", 11, QFont.Bold))

            named = v.get("named_count", 0)
            total = v.get("pid_count", 0)
            named_text = f"{named}/{total}"
            named_item = QTableWidgetItem(named_text)
            named_item.setTextAlignment(Qt.AlignCenter)
            color = QColor("#2EA043") if named > 0 else QColor("#6E7681")
            named_item.setForeground(color)

            self._vehicle_table.setItem(i, 0, make_item)
            self._vehicle_table.setItem(i, 1, model_item)
            self._vehicle_table.setItem(i, 2, year_item)
            self._vehicle_table.setItem(i, 3, pid_item)
            self._vehicle_table.setItem(i, 4, named_item)

        total_pids = sum(v.get("pid_count", 0) for v in vehicles)
        self._status_label.setText(
            f"{len(vehicles)} vehicle{'s' if len(vehicles) != 1 else ''} · "
            f"{total_pids} total PIDs"
        )

    def _on_load_error(self, error_msg):
        self._refresh_btn.setEnabled(True)
        self._status_label.setText(f"Error: {error_msg}")
        logger.error(f"PID Atlas load error: {error_msg}")

    # ===== Vehicle double-click → load PIDs =====

    def _on_vehicle_double_click(self, index):
        row = index.row()
        if row < 0 or row >= len(self._vehicles):
            return
        v = self._vehicles[row]
        make = v["make"]
        model = v["model"]
        self._selected_make = make
        self._selected_model = model

        self._detail_header.setText(f"{make} {model} — Loading PIDs...")
        self._detail_header.setStyleSheet("color: #58A6FF; padding: 4px;")

        def fetch():
            return self._api._request(
                "GET", "/pids/atlas/detail",
                params={"make": make, "model": model},
            )

        self._worker = APIWorker(fetch)
        self._worker.finished.connect(self._on_pids_loaded)
        self._worker.error.connect(self._on_pid_load_error)
        self._worker.start()

    def _on_pids_loaded(self, data):
        pids = data.get("pids", [])
        make = data.get("make", self._selected_make)
        model = data.get("model", self._selected_model)

        self._detail_header.setText(f"{make} {model} — {len(pids)} PIDs")
        self._detail_header.setStyleSheet(
            "color: #F0F6FC; padding: 4px; font-size: 13px;"
        )

        # Update stats
        dynamic = sum(1 for p in pids if p.get("is_dynamic"))
        static = len(pids) - dynamic
        named = sum(1 for p in pids if p.get("name"))
        verified = sum(1 for p in pids if p.get("is_verified"))

        self._stat_labels["Total"].setText(f"Total: {len(pids)}")
        self._stat_labels["Dynamic"].setText(f"Dynamic: {dynamic}")
        self._stat_labels["Static"].setText(f"Static: {static}")
        self._stat_labels["Named"].setText(f"Named: {named}")
        self._stat_labels["Verified"].setText(f"Verified: {verified}")
        self._stats_frame.setVisible(True)

        # Populate PID table
        self._pid_table.setSortingEnabled(False)
        self._pid_table.setRowCount(len(pids))

        for i, p in enumerate(pids):
            svc = p.get("service", 0)
            svc_text = f"0x{svc:02X}" if svc else "—"
            svc_item = QTableWidgetItem(svc_text)
            svc_item.setTextAlignment(Qt.AlignCenter)
            svc_item.setForeground(QColor("#79C0FF"))

            pid_hex = p.get("pid_hex", "")
            pid_item = QTableWidgetItem(pid_hex)
            pid_item.setTextAlignment(Qt.AlignCenter)
            pid_item.setForeground(QColor("#D2A8FF"))
            pid_item.setFont(QFont("Consolas", 11))

            ecu = p.get("ecu_address", "")
            ecu_item = QTableWidgetItem(ecu if ecu else "—")
            ecu_item.setTextAlignment(Qt.AlignCenter)
            ecu_item.setForeground(QColor("#8B949E"))

            name = p.get("name") or ""
            name_item = QTableWidgetItem(name)
            if name:
                name_item.setForeground(QColor("#2EA043"))
                name_item.setFont(QFont("Segoe UI", 11, QFont.Bold))
            else:
                name_item.setForeground(QColor("#6E7681"))
                name_item.setText("(unlabeled)")

            sem_type = p.get("semantic_type", "unknown")
            type_item = QTableWidgetItem(sem_type)
            type_item.setTextAlignment(Qt.AlignCenter)
            type_color = SEMANTIC_COLORS.get(sem_type, SEMANTIC_COLORS["unknown"])
            type_item.setForeground(type_color)

            unit = p.get("unit") or "—"
            unit_item = QTableWidgetItem(unit)
            unit_item.setTextAlignment(Qt.AlignCenter)
            unit_item.setForeground(QColor("#C9D1D9"))

            is_dynamic = p.get("is_dynamic", False)
            dyn_item = QTableWidgetItem("Yes" if is_dynamic else "No")
            dyn_item.setTextAlignment(Qt.AlignCenter)
            dyn_item.setForeground(
                QColor("#58A6FF") if is_dynamic else QColor("#6E7681")
            )

            is_verified = p.get("is_verified", False)
            ver_item = QTableWidgetItem("✓" if is_verified else "—")
            ver_item.setTextAlignment(Qt.AlignCenter)
            ver_item.setForeground(
                QColor("#2EA043") if is_verified else QColor("#6E7681")
            )

            disc = p.get("discovery_count", 0)
            disc_item = QTableWidgetItem(str(disc))
            disc_item.setTextAlignment(Qt.AlignCenter)
            disc_item.setForeground(QColor("#C9D1D9"))

            self._pid_table.setItem(i, 0, svc_item)
            self._pid_table.setItem(i, 1, pid_item)
            self._pid_table.setItem(i, 2, ecu_item)
            self._pid_table.setItem(i, 3, name_item)
            self._pid_table.setItem(i, 4, type_item)
            self._pid_table.setItem(i, 5, unit_item)
            self._pid_table.setItem(i, 6, dyn_item)
            self._pid_table.setItem(i, 7, ver_item)
            self._pid_table.setItem(i, 8, disc_item)

        self._pid_table.setSortingEnabled(True)

    def _on_pid_load_error(self, error_msg):
        self._detail_header.setText(
            f"{self._selected_make} {self._selected_model} — Error loading PIDs"
        )
        self._detail_header.setStyleSheet("color: #F85149; padding: 4px;")
        logger.error(f"PID detail load error: {error_msg}")
