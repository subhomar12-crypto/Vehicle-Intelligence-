"""
PREDICT - Vehicle Intelligence Platform
Copyright © 2026 PREDICT
All rights reserved.

This file is proprietary and confidential.
Unauthorized copying, modification, distribution, or use is strictly prohibited.

Created: January 2026
Module: Vehicle Catalog Editor
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGroupBox, QGridLayout, QLineEdit, QTextEdit, QListWidget,
    QComboBox, QMessageBox, QFormLayout, QSpinBox, QListWidgetItem,
    QDialog, QDialogButtonBox, QInputDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QTabWidget
)
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt

try:
    from pid_profiles import VehicleCatalog
except ImportError:
    VehicleCatalog = None

try:
    from ui_common import PredictTheme
except ImportError:
    PredictTheme = None


class VehicleCatalogEditor(QWidget):
    """Admin tab for editing vehicle catalog"""
    
    def _get_button_style(self, style_type: str = 'primary') -> str:
        """Get consistent button style based on type."""
        styles = {
            'primary': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 12px 24px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'secondary': """
                QPushButton {
                    background-color: #21262D;
                    color: #F0F6FC;
                    border: 1px solid #30363D;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #30363D;
                    border-color: #8B949E;
                }
                QPushButton:pressed {
                    background-color: #161B22;
                }
                QPushButton:disabled {
                    background-color: #161B22;
                    color: #484F58;
                    border-color: #30363D;
                }
            """,
            'danger': """
                QPushButton {
                    background-color: #C40000;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #E53935;
                }
                QPushButton:pressed {
                    background-color: #B71C1C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'success': """
                QPushButton {
                    background-color: #4CAF50;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #66BB6A;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'warning': """
                QPushButton {
                    background-color: #FFC107;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #FFB300;
                }
                QPushButton:pressed {
                    background-color: #FF8F00;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """,
            'info': """
                QPushButton {
                    background-color: #2196F3;
                    color: #F0F6FC;
                    border: none;
                    padding: 10px 20px;
                    font-size: 14px;
                    font-weight: 600;
                    border-radius: 6px;
                }
                QPushButton:hover {
                    background-color: #42A5F5;
                }
                QPushButton:pressed {
                    background-color: #1976D2;
                }
                QPushButton:disabled {
                    background-color: #484F58;
                    color: #8B949E;
                }
            """
        }
        return styles.get(style_type, styles['primary'])
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.catalog = None
        self._init_catalog()
        self._build_ui()
        self._load_data()
    
    def _init_catalog(self):
        """Initialize the vehicle catalog"""
        try:
            if VehicleCatalog:
                self.catalog = VehicleCatalog()
            else:
                self.catalog = None
        except Exception as e:
            print(f"Error initializing catalog: {e}")
            self.catalog = None
    
    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(12)
        
        # Header
        header = QHBoxLayout()
        title = QLabel("Vehicle Catalog Editor")
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        if PredictTheme:
            title.setStyleSheet(f"color: {PredictTheme.PRIMARY};")
        header.addWidget(title)
        
        header.addStretch()
        
        self.btn_reload = QPushButton("🔄 Reload")
        self.btn_reload.setStyleSheet(self._get_button_style('secondary'))
        self.btn_reload.clicked.connect(self._reload_catalog)
        header.addWidget(self.btn_reload)
        
        self.btn_save = QPushButton("💾 Save Changes")
        self.btn_save.setStyleSheet(self._get_button_style('success'))
        self.btn_save.clicked.connect(self._save_catalog)
        header.addWidget(self.btn_save)
        
        layout.addLayout(header)
        
        # Main content with tabs
        self.tabs = QTabWidget()
        
        # Brands tab
        brands_tab = QWidget()
        self._build_brands_tab(brands_tab)
        self.tabs.addTab(brands_tab, "Brands")
        
        # Models tab
        models_tab = QWidget()
        self._build_models_tab(models_tab)
        self.tabs.addTab(models_tab, "Models")
        
        # Years tab
        years_tab = QWidget()
        self._build_years_tab(years_tab)
        self.tabs.addTab(years_tab, "Years")
        
        layout.addWidget(self.tabs)
        
        # Status
        self.status_label = QLabel("Ready")
        self.status_label.setStyleSheet("color: #888;")
        layout.addWidget(self.status_label)
    
    def _build_brands_tab(self, parent):
        layout = QHBoxLayout(parent)
        
        # Left side - brand list
        left_group = QGroupBox("Brands")
        left_layout = QVBoxLayout(left_group)
        
        self.brand_list = QListWidget()
        self.brand_list.currentRowChanged.connect(self._on_brand_selected)
        left_layout.addWidget(self.brand_list)
        
        btn_row = QHBoxLayout()
        self.btn_add_brand = QPushButton("+ Add Brand")
        self.btn_add_brand.setStyleSheet(self._get_button_style('secondary'))
        self.btn_add_brand.clicked.connect(self._add_brand)
        btn_row.addWidget(self.btn_add_brand)
        left_layout.addLayout(btn_row)
        
        layout.addWidget(left_group, 1)
        
        # Right side - brand details
        right_group = QGroupBox("Brand Details")
        right_layout = QFormLayout(right_group)
        
        self.brand_name_edit = QLineEdit()
        self.brand_name_edit.setPlaceholderText("e.g., nissan")
        right_layout.addRow("Internal Name:", self.brand_name_edit)
        
        self.brand_display_edit = QLineEdit()
        self.brand_display_edit.setPlaceholderText("e.g., Nissan")
        right_layout.addRow("Display Name:", self.brand_display_edit)
        
        self.brand_models_count = QLabel("0")
        right_layout.addRow("Models:", self.brand_models_count)
        
        layout.addWidget(right_group, 1)
    
    def _build_models_tab(self, parent):
        layout = QHBoxLayout(parent)
        
        # Left side - model list
        left_group = QGroupBox("Models")
        left_layout = QVBoxLayout(left_group)
        
        # Brand selector
        brand_row = QHBoxLayout()
        brand_row.addWidget(QLabel("Brand:"))
        self.model_brand_combo = QComboBox()
        self.model_brand_combo.currentTextChanged.connect(self._on_model_brand_changed)
        brand_row.addWidget(self.model_brand_combo)
        left_layout.addLayout(brand_row)
        
        self.model_list = QListWidget()
        self.model_list.currentRowChanged.connect(self._on_model_selected)
        left_layout.addWidget(self.model_list)
        
        btn_row = QHBoxLayout()
        self.btn_add_model = QPushButton("+ Add Model")
        self.btn_add_model.setStyleSheet(self._get_button_style('secondary'))
        self.btn_add_model.clicked.connect(self._add_model)
        btn_row.addWidget(self.btn_add_model)
        left_layout.addLayout(btn_row)
        
        layout.addWidget(left_group, 1)
        
        # Right side - model details
        right_group = QGroupBox("Model Details")
        right_layout = QFormLayout(right_group)
        
        self.model_name_edit = QLineEdit()
        right_layout.addRow("Internal Name:", self.model_name_edit)
        
        self.model_display_edit = QLineEdit()
        right_layout.addRow("Display Name:", self.model_display_edit)
        
        self.model_submodels_edit = QLineEdit()
        self.model_submodels_edit.setPlaceholderText("Comma separated: y61, y62")
        right_layout.addRow("Submodels:", self.model_submodels_edit)
        
        self.model_pid_profiles_edit = QLineEdit()
        self.model_pid_profiles_edit.setPlaceholderText("e.g., nissan_altima_2017")
        right_layout.addRow("PID Profile IDs:", self.model_pid_profiles_edit)
        
        layout.addWidget(right_group, 1)
    
    def _build_years_tab(self, parent):
        layout = QVBoxLayout(parent)
        
        # Selectors
        select_row = QHBoxLayout()
        
        select_row.addWidget(QLabel("Brand:"))
        self.year_brand_combo = QComboBox()
        self.year_brand_combo.currentTextChanged.connect(self._on_year_brand_changed)
        select_row.addWidget(self.year_brand_combo)
        
        select_row.addWidget(QLabel("Model:"))
        self.year_model_combo = QComboBox()
        self.year_model_combo.currentTextChanged.connect(self._on_year_model_changed)
        select_row.addWidget(self.year_model_combo)
        
        select_row.addStretch()
        layout.addLayout(select_row)
        
        # Years list
        years_group = QGroupBox("Years")
        years_layout = QVBoxLayout(years_group)
        
        self.years_list = QListWidget()
        years_layout.addWidget(self.years_list)
        
        btn_row = QHBoxLayout()
        
        self.year_from_spin = QSpinBox()
        self.year_from_spin.setRange(1990, 2030)
        self.year_from_spin.setValue(2020)
        btn_row.addWidget(QLabel("From:"))
        btn_row.addWidget(self.year_from_spin)
        
        self.year_to_spin = QSpinBox()
        self.year_to_spin.setRange(1990, 2030)
        self.year_to_spin.setValue(2024)
        btn_row.addWidget(QLabel("To:"))
        btn_row.addWidget(self.year_to_spin)
        
        self.btn_add_years = QPushButton("+ Add Years")
        self.btn_add_years.setStyleSheet(self._get_button_style('secondary'))
        self.btn_add_years.clicked.connect(self._add_years)
        btn_row.addWidget(self.btn_add_years)
        
        btn_row.addStretch()
        years_layout.addLayout(btn_row)
        
        layout.addWidget(years_group)
    
    def _load_data(self):
        """Load data from catalog"""
        if not self.catalog:
            self.status_label.setText("Catalog not available")
            return
        
        # Load brands
        self.brand_list.clear()
        self.model_brand_combo.clear()
        self.year_brand_combo.clear()
        
        brands = self.catalog.get_brands()
        for brand in brands:
            display = brand.get('display_name', brand.get('name', ''))
            self.brand_list.addItem(display)
            self.model_brand_combo.addItem(display)
            self.year_brand_combo.addItem(display)
        
        self.status_label.setText(f"Loaded {len(brands)} brands")
    
    def _reload_catalog(self):
        """Reload catalog from disk"""
        if self.catalog:
            self.catalog.reload()
            self._load_data()
            self.status_label.setText("Catalog reloaded")
    
    def _save_catalog(self):
        """Save catalog to disk"""
        if self.catalog:
            if self.catalog.save():
                self.status_label.setText("Catalog saved successfully")
                QMessageBox.information(self, "Saved", "Vehicle catalog saved successfully!")
            else:
                self.status_label.setText("Save failed")
                QMessageBox.warning(self, "Error", "Failed to save catalog")
    
    def _on_brand_selected(self, row):
        """Handle brand selection"""
        if row < 0 or not self.catalog:
            return
        
        brands = self.catalog.get_brands()
        if row < len(brands):
            brand = brands[row]
            self.brand_name_edit.setText(brand.get('name', ''))
            self.brand_display_edit.setText(brand.get('display_name', ''))
            models = brand.get('models', [])
            self.brand_models_count.setText(str(len(models)))
    
    def _on_model_brand_changed(self, brand_name):
        """Handle brand change in models tab"""
        if not self.catalog or not brand_name:
            return
        
        self.model_list.clear()
        models = self.catalog.get_model_names_for_brand(brand_name)
        self.model_list.addItems(models)
    
    def _on_model_selected(self, row):
        """Handle model selection"""
        if row < 0 or not self.catalog:
            return
        
        brand_name = self.model_brand_combo.currentText()
        models = self.catalog.get_models_for_brand(brand_name)
        
        if row < len(models):
            model = models[row]
            self.model_name_edit.setText(model.get('name', ''))
            self.model_display_edit.setText(model.get('display_name', ''))
            
            submodels = model.get('submodels', [])
            self.model_submodels_edit.setText(', '.join(submodels))
            
            pid_profiles = model.get('pid_profile_ids', [])
            self.model_pid_profiles_edit.setText(', '.join(pid_profiles))
    
    def _on_year_brand_changed(self, brand_name):
        """Handle brand change in years tab"""
        if not self.catalog or not brand_name:
            return
        
        self.year_model_combo.clear()
        models = self.catalog.get_model_names_for_brand(brand_name)
        self.year_model_combo.addItems(models)
    
    def _on_year_model_changed(self, model_name):
        """Handle model change in years tab"""
        if not self.catalog or not model_name:
            return
        
        brand_name = self.year_brand_combo.currentText()
        years = self.catalog.get_years_for_model(brand_name, model_name)
        
        self.years_list.clear()
        for year in years:
            self.years_list.addItem(str(year))
    
    def _add_brand(self):
        """Add a new brand"""
        name, ok = QInputDialog.getText(self, "Add Brand", "Enter brand name (lowercase):")
        if ok and name and self.catalog:
            display, ok2 = QInputDialog.getText(self, "Add Brand", "Enter display name:")
            if ok2:
                if self.catalog.add_brand(name.lower().strip(), display.strip()):
                    self._load_data()
                    self.status_label.setText(f"Brand '{display}' added")
                else:
                    QMessageBox.warning(self, "Error", "Brand already exists or save failed")
    
    def _add_model(self):
        """Add a new model"""
        brand_name = self.model_brand_combo.currentText()
        if not brand_name:
            QMessageBox.warning(self, "Error", "Please select a brand first")
            return
        
        name, ok = QInputDialog.getText(self, "Add Model", "Enter model name:")
        if ok and name and self.catalog:
            display, ok2 = QInputDialog.getText(self, "Add Model", "Enter display name:")
            if ok2:
                if self.catalog.add_model(brand_name, name.strip(), display.strip()):
                    self._on_model_brand_changed(brand_name)
                    self.status_label.setText(f"Model '{display}' added to {brand_name}")
                else:
                    QMessageBox.warning(self, "Error", "Model already exists or save failed")
    
    def _add_years(self):
        """Add years to selected model"""
        brand_name = self.year_brand_combo.currentText()
        model_name = self.year_model_combo.currentText()
        
        if not brand_name or not model_name:
            QMessageBox.warning(self, "Error", "Please select brand and model first")
            return
        
        year_from = self.year_from_spin.value()
        year_to = self.year_to_spin.value()
        
        if year_to < year_from:
            year_from, year_to = year_to, year_from
        
        years = list(range(year_from, year_to + 1))
        
        if self.catalog.add_years_to_model(brand_name, model_name, years):
            self._on_year_model_changed(model_name)
            self.status_label.setText(f"Added years {year_from}-{year_to} to {model_name}")
        else:
            QMessageBox.warning(self, "Error", "Failed to add years")
