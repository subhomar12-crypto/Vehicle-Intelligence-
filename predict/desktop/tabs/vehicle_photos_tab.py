"""
Vehicle Photos Management Tab — Upload, view, and manage vehicle photos.

Tab 8 of 8 in the PREDICT Desktop GUI.
Allows uploading vehicle photos with metadata, viewing a gallery of uploaded
photos, filtering by match status, and deleting photos.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QLineEdit,
    QSpinBox, QFileDialog, QProgressBar, QScrollArea, QGridLayout,
    QComboBox, QMessageBox, QFrame, QSizePolicy, QGroupBox,
)
from PySide6.QtCore import Qt, QTimer, QSize
from PySide6.QtGui import QPixmap, QFont, QColor, QImage

from predict.desktop.workers import APIWorker
from predict.desktop.api_client import PredictAPIClient

logger = logging.getLogger(__name__)

# Thumbnail size for the gallery
THUMB_SIZE = 180


class PhotoCard(QFrame):
    """A single photo card in the gallery grid."""

    def __init__(self, photo_data: dict, api_client: PredictAPIClient,
                 on_deleted=None, parent=None):
        super().__init__(parent)
        self._photo_data = photo_data
        self._api = api_client
        self._on_deleted = on_deleted
        self._worker: Optional[APIWorker] = None

        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setStyleSheet(
            "PhotoCard { background-color: #161b22; border: 1px solid #30363d; "
            "border-radius: 6px; }"
        )
        self.setFixedSize(THUMB_SIZE + 20, THUMB_SIZE + 110)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        # Thumbnail
        self._thumb_label = QLabel()
        self._thumb_label.setFixedSize(THUMB_SIZE, THUMB_SIZE)
        self._thumb_label.setAlignment(Qt.AlignCenter)
        self._thumb_label.setStyleSheet(
            "background-color: #0d1117; border: 1px solid #21262d; border-radius: 4px;"
        )

        thumbnail_url = self._photo_data.get("thumbnail_url") or self._photo_data.get("file_url")
        if thumbnail_url:
            self._thumb_label.setText("Loading...")
            self._load_thumbnail(thumbnail_url)
        else:
            self._thumb_label.setText("No Image")

        layout.addWidget(self._thumb_label, alignment=Qt.AlignCenter)

        # Vehicle info
        make = self._photo_data.get("make", "")
        model = self._photo_data.get("model", "")
        year = self._photo_data.get("year", 0)
        vehicle_text = " ".join(filter(None, [str(year) if year else "", make, model])).strip()
        if not vehicle_text:
            vehicle_text = "Unknown Vehicle"

        info_label = QLabel(vehicle_text)
        info_label.setStyleSheet("color: #c9d1d9; font-size: 11px; font-weight: bold;")
        info_label.setAlignment(Qt.AlignCenter)
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Status badge
        is_matched = self._photo_data.get("matched", False) or self._photo_data.get("vehicle_id") is not None
        status_text = "Matched" if is_matched else "Unmatched"
        status_color = "#2ea043" if is_matched else "#d29922"
        status_label = QLabel(status_text)
        status_label.setAlignment(Qt.AlignCenter)
        status_label.setStyleSheet(
            f"color: {status_color}; font-size: 10px; font-weight: bold;"
        )
        layout.addWidget(status_label)

        # Delete button
        delete_btn = QPushButton("Delete")
        delete_btn.setFixedHeight(24)
        delete_btn.setStyleSheet(
            "QPushButton { background-color: #21262d; color: #f85149; "
            "border: 1px solid #f85149; border-radius: 3px; font-size: 10px; }"
            "QPushButton:hover { background-color: #f85149; color: white; }"
        )
        delete_btn.clicked.connect(self._on_delete)
        layout.addWidget(delete_btn)

    def _load_thumbnail(self, url: str):
        """Load thumbnail image in a background thread."""
        self._worker = APIWorker(self._api.get_raw, url.replace(self._api.base_url, ""))
        self._worker.finished.connect(self._on_thumbnail_loaded)
        self._worker.error.connect(lambda _: self._thumb_label.setText("Failed"))
        self._worker.start()

    def _on_thumbnail_loaded(self, response):
        """Handle thumbnail download completion."""
        try:
            img = QImage()
            img.loadFromData(response.content)
            if not img.isNull():
                pixmap = QPixmap.fromImage(img).scaled(
                    THUMB_SIZE, THUMB_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._thumb_label.setPixmap(pixmap)
            else:
                self._thumb_label.setText("No Preview")
        except Exception:
            self._thumb_label.setText("Error")

    def _on_delete(self):
        photo_id = self._photo_data.get("photo_id") or self._photo_data.get("id")
        if not photo_id:
            return

        reply = QMessageBox.question(
            self, "Delete Photo",
            "Are you sure you want to delete this photo?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply != QMessageBox.Yes:
            return

        self._worker = APIWorker(self._api.delete_vehicle_photo, photo_id)
        self._worker.finished.connect(self._on_delete_complete)
        self._worker.error.connect(lambda err: QMessageBox.critical(
            self, "Delete Failed", f"Could not delete photo:\n{err}"
        ))
        self._worker.start()

    def _on_delete_complete(self, _):
        if self._on_deleted:
            self._on_deleted()


class VehiclePhotosTab(QWidget):
    """Tab for uploading and managing vehicle photos."""

    def __init__(self, api_client: PredictAPIClient, parent=None):
        super().__init__(parent)
        self._api = api_client
        self._worker: Optional[APIWorker] = None
        self._selected_file: str = ""
        self._photo_cards: list = []

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # =====================================================================
        # LEFT PANEL — Upload Form
        # =====================================================================
        left_panel = QGroupBox("Upload Vehicle Photo")
        left_panel.setFixedWidth(320)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # File picker
        file_label = QLabel("Photo File:")
        file_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(file_label)

        file_row = QHBoxLayout()
        self._file_path_input = QLineEdit()
        self._file_path_input.setReadOnly(True)
        self._file_path_input.setPlaceholderText("No file selected")
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.setFixedWidth(80)
        file_row.addWidget(self._file_path_input)
        file_row.addWidget(self._browse_btn)
        left_layout.addLayout(file_row)

        # Image preview
        self._preview_label = QLabel()
        self._preview_label.setFixedSize(280, 180)
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setStyleSheet(
            "background-color: #0d1117; border: 1px solid #21262d; border-radius: 4px;"
        )
        self._preview_label.setText("No image selected")
        left_layout.addWidget(self._preview_label, alignment=Qt.AlignCenter)

        # Vehicle detail fields
        details_label = QLabel("Vehicle Details (optional):")
        details_label.setStyleSheet("font-weight: bold;")
        left_layout.addWidget(details_label)

        self._make_input = QLineEdit()
        self._make_input.setPlaceholderText("Make (e.g. Toyota)")
        left_layout.addWidget(self._make_input)

        self._model_input = QLineEdit()
        self._model_input.setPlaceholderText("Model (e.g. Camry)")
        left_layout.addWidget(self._model_input)

        year_row = QHBoxLayout()
        year_label = QLabel("Year:")
        self._year_spin = QSpinBox()
        self._year_spin.setRange(1980, 2030)
        self._year_spin.setValue(2024)
        self._year_spin.setSpecialValueText(" ")
        year_row.addWidget(year_label)
        year_row.addWidget(self._year_spin)
        year_row.addStretch()
        left_layout.addLayout(year_row)

        self._color_input = QLineEdit()
        self._color_input.setPlaceholderText("Color (e.g. White)")
        left_layout.addWidget(self._color_input)

        self._vin_input = QLineEdit()
        self._vin_input.setPlaceholderText("VIN (17 characters)")
        self._vin_input.setMaxLength(17)
        left_layout.addWidget(self._vin_input)

        self._plate_input = QLineEdit()
        self._plate_input.setPlaceholderText("License Plate")
        left_layout.addWidget(self._plate_input)

        # Upload button
        self._upload_btn = QPushButton("Upload && Process")
        self._upload_btn.setStyleSheet(
            "QPushButton { background-color: #C40000; color: white; "
            "padding: 10px 16px; border-radius: 4px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background-color: #e04040; }"
            "QPushButton:disabled { background-color: #484f58; color: #8b949e; }"
        )
        self._upload_btn.setEnabled(False)
        left_layout.addWidget(self._upload_btn)

        # Progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)  # Indeterminate
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(8)
        left_layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setStyleSheet("color: #8b949e; font-size: 11px;")
        left_layout.addWidget(self._status_label)

        left_layout.addStretch()
        main_layout.addWidget(left_panel)

        # =====================================================================
        # RIGHT PANEL — Photo Gallery
        # =====================================================================
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # Top bar
        gallery_top = QHBoxLayout()
        gallery_label = QLabel("Photo Gallery")
        gallery_label.setStyleSheet("font-size: 14px; font-weight: bold;")
        gallery_top.addWidget(gallery_label)

        gallery_top.addStretch()

        filter_label = QLabel("Filter:")
        self._filter_combo = QComboBox()
        self._filter_combo.addItems(["All", "Unmatched", "Matched"])
        self._filter_combo.setMinimumWidth(120)
        gallery_top.addWidget(filter_label)
        gallery_top.addWidget(self._filter_combo)

        self._refresh_btn = QPushButton("Refresh")
        gallery_top.addWidget(self._refresh_btn)

        self._photo_count_label = QLabel("")
        self._photo_count_label.setStyleSheet("color: #8b949e;")
        gallery_top.addWidget(self._photo_count_label)

        right_panel.addLayout(gallery_top)

        # Scroll area for photo grid
        self._scroll_area = QScrollArea()
        self._scroll_area.setWidgetResizable(True)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll_area.setStyleSheet(
            "QScrollArea { border: 1px solid #30363d; border-radius: 4px; "
            "background-color: #0d1117; }"
        )

        self._gallery_container = QWidget()
        self._gallery_layout = QGridLayout(self._gallery_container)
        self._gallery_layout.setSpacing(12)
        self._gallery_layout.setContentsMargins(12, 12, 12, 12)
        self._gallery_layout.setAlignment(Qt.AlignTop | Qt.AlignLeft)

        self._scroll_area.setWidget(self._gallery_container)
        right_panel.addWidget(self._scroll_area)

        # Empty state label (shown when no photos)
        self._empty_label = QLabel("No photos uploaded yet.\nUse the form on the left to upload vehicle photos.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #484f58; font-size: 13px;")
        self._empty_label.setVisible(False)

        main_layout.addLayout(right_panel, stretch=1)

    def _connect_signals(self):
        self._browse_btn.clicked.connect(self._on_browse)
        self._upload_btn.clicked.connect(self._on_upload)
        self._refresh_btn.clicked.connect(self._load_data)
        self._filter_combo.currentTextChanged.connect(self._load_data)

    def _on_browse(self):
        """Open file dialog to select an image."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Vehicle Photo", "",
            "Images (*.jpg *.jpeg *.png *.bmp *.webp);;All Files (*)"
        )
        if file_path:
            self._selected_file = file_path
            self._file_path_input.setText(os.path.basename(file_path))
            self._upload_btn.setEnabled(True)

            # Show preview
            pixmap = QPixmap(file_path)
            if not pixmap.isNull():
                scaled = pixmap.scaled(
                    280, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation
                )
                self._preview_label.setPixmap(scaled)
            else:
                self._preview_label.setText("Cannot preview")

    def _on_upload(self):
        """Upload the selected photo with metadata."""
        if not self._selected_file or not os.path.isfile(self._selected_file):
            QMessageBox.warning(self, "No File", "Please select a photo file first.")
            return

        self._upload_btn.setEnabled(False)
        self._progress_bar.setVisible(True)
        self._status_label.setText("Uploading...")
        self._status_label.setStyleSheet("color: #58a6ff; font-size: 11px;")

        self._worker = APIWorker(
            self._api.upload_vehicle_photo,
            file_path=self._selected_file,
            make=self._make_input.text().strip(),
            model=self._model_input.text().strip(),
            year=self._year_spin.value(),
            color=self._color_input.text().strip(),
            vin=self._vin_input.text().strip().upper(),
            license_plate=self._plate_input.text().strip().upper(),
        )
        self._worker.finished.connect(self._on_upload_complete)
        self._worker.error.connect(self._on_upload_error)
        self._worker.start()

    def _on_upload_complete(self, result: dict):
        """Handle successful upload."""
        self._progress_bar.setVisible(False)
        self._upload_btn.setEnabled(True)
        self._status_label.setText("Upload successful!")
        self._status_label.setStyleSheet("color: #2ea043; font-size: 11px; font-weight: bold;")

        # Clear form
        self._selected_file = ""
        self._file_path_input.clear()
        self._preview_label.clear()
        self._preview_label.setText("No image selected")
        self._make_input.clear()
        self._model_input.clear()
        self._year_spin.setValue(2024)
        self._color_input.clear()
        self._vin_input.clear()
        self._plate_input.clear()
        self._upload_btn.setEnabled(False)

        # Refresh gallery
        QTimer.singleShot(500, self._load_data)

    def _on_upload_error(self, error_msg: str):
        """Handle upload failure."""
        self._progress_bar.setVisible(False)
        self._upload_btn.setEnabled(True)
        self._status_label.setText(f"Upload failed: {error_msg}")
        self._status_label.setStyleSheet("color: #f85149; font-size: 11px;")
        logger.error(f"Photo upload failed: {error_msg}")

    def _load_data(self):
        """Load photos from server."""
        if self._worker and self._worker.isRunning():
            return

        self._worker = APIWorker(self._api.get_unmatched_photos)
        self._worker.finished.connect(self._on_data_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_data_loaded(self, data: dict):
        """Populate the gallery grid with photo cards."""
        photos = data.get("photos", [])
        if isinstance(data, list):
            photos = data

        # Apply filter
        filter_text = self._filter_combo.currentText()
        if filter_text == "Unmatched":
            photos = [p for p in photos if not p.get("matched") and p.get("vehicle_id") is None]
        elif filter_text == "Matched":
            photos = [p for p in photos if p.get("matched") or p.get("vehicle_id") is not None]

        # Clear existing cards
        self._photo_cards.clear()
        while self._gallery_layout.count():
            item = self._gallery_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

        # Update count
        self._photo_count_label.setText(f"{len(photos)} photo(s)")

        if not photos:
            self._empty_label.setVisible(True)
            self._gallery_layout.addWidget(self._empty_label, 0, 0)
            return

        self._empty_label.setVisible(False)

        # Calculate columns based on available width
        cols = max(1, (self._scroll_area.width() - 40) // (THUMB_SIZE + 32))
        if cols < 1:
            cols = 3  # default

        for idx, photo in enumerate(photos):
            row = idx // cols
            col = idx % cols
            card = PhotoCard(photo, self._api, on_deleted=self._load_data, parent=self)
            self._photo_cards.append(card)
            self._gallery_layout.addWidget(card, row, col)

    def _on_load_error(self, error_msg: str):
        """Handle gallery load failure."""
        logger.error(f"Photo gallery load failed: {error_msg}")
        self._photo_count_label.setText("Load failed")

    def cleanup(self):
        """Clean up resources."""
        pass
