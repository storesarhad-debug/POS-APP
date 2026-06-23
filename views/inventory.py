try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
        QLineEdit, QMessageBox, QSpinBox, QDoubleSpinBox, QComboBox,
        QDialogButtonBox, QRadioButton, QButtonGroup, QScrollArea, QFrame,
        QAbstractItemView
    )
    from PySide6.QtCore import Signal, Qt, QTimer
    from datetime import datetime, timedelta
    from decimal import Decimal, InvalidOperation
    from pathlib import Path
    from typing import Optional, Dict, Any, List, Union
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QDialog, QFormLayout,
        QLineEdit, QMessageBox, QSpinBox, QDoubleSpinBox, QComboBox,
        QDialogButtonBox, QRadioButton, QButtonGroup, QScrollArea, QFrame,
        QAbstractItemView
    )
    from PyQt6.QtCore import pyqtSignal as Signal, Qt, QTimer
    from datetime import datetime, timedelta
    from decimal import Decimal, InvalidOperation
    from pathlib import Path
    from typing import Optional, Dict, Any, List, Union
    import sys
    import os
    _this_file = Path(__file__).resolve()
    _project_root = _this_file.parents[2]  # pos_app is 2 levels up
    if str(_project_root) not in sys.path:
        sys.path.insert(0, str(_project_root))
    from pos_app.models.database import Product, Supplier, InventoryLocation, ProductCategory, ProductSubcategory
    from pos_app.views.suppliers import SupplierDialog
    from pos_app.models.database import Product as ProductModel

class InventoryWidget(QWidget):
    product_added = Signal()
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.selected_product_id = None
        self._last_sync_ts = None
        # Add search debounce timer to prevent UI freeze
        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._perform_search)
        self._pending_search_text = ""
        
        # Add real-time sync timer for server updates
        self._sync_timer = QTimer()
        self._sync_timer.setSingleShot(True)
        self._sync_timer.timeout.connect(self._check_for_updates)
        self._last_sync_check = datetime.now()
        
        self.setup_ui()
        self.load_products()
        self._init_sync_timer()
        
        # Register with connection monitor for auto-reload
        try:
            from pos_app.utils.connection_monitor import get_connection_monitor
            monitor = get_connection_monitor()
            monitor.add_reload_callback('products', self.refresh_products_keep_page)
            monitor.reload_data.connect(self._on_reload_signal)
            print("[Inventory] Registered with connection monitor for auto-reload")
        except Exception as e:
            print(f"[Inventory] Failed to register with connection monitor: {e}")
    
    def _on_reload_signal(self, data_type):
        """Handle reload signal from connection monitor"""
        if data_type == 'products':
            print("[Inventory] Auto-reloading products due to server restart")
            try:
                self.refresh_products_keep_page()
            except Exception as e:
                print(f"[Inventory] Error during auto-reload: {e}")

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)

        # Header with action buttons
        header_layout = QHBoxLayout()
        header = QLabel("📦 Inventory Management")
        header.setProperty('role', 'heading')
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #f8fafc;")
        header_layout.addWidget(header)
        header_layout.addStretch()
        
        # Action buttons (initially disabled)
        self.edit_product_btn = QPushButton("✏️ Edit Product")
        self.edit_product_btn.setProperty('accent', 'Qt.blue')
        self.edit_product_btn.setMinimumHeight(36)
        self.edit_product_btn.setEnabled(False)
        self.edit_product_btn.clicked.connect(self.edit_selected_product)
        
        self.delete_product_btn = QPushButton("🗑️ Delete Product")
        self.delete_product_btn.setProperty('accent', 'Qt.red')
        self.delete_product_btn.setMinimumHeight(36)
        self.delete_product_btn.setEnabled(False)
        self.delete_product_btn.clicked.connect(self.delete_selected_product)
        
        header_layout.addWidget(self.edit_product_btn)
        header_layout.addWidget(self.delete_product_btn)
        layout.addLayout(header_layout)
        
        # Barcode search widget for quick product lookup
        from pos_app.widgets.barcode_search import BarcodeSearchWidget
        self.barcode_widget = BarcodeSearchWidget(
            session=self.controller.session,
            parent=self,
            show_quantity=False,
            auto_add=False
        )
        self.barcode_widget.product_selected.connect(self._on_product_scanned)
        layout.addWidget(self.barcode_widget)

        # Toolbar
        toolbar_layout = QHBoxLayout()
        add_btn = QPushButton("✨ Add New Product")
        add_btn.setProperty('accent', 'Qt.green')
        add_btn.setMinimumHeight(44)
        add_btn.clicked.connect(self.show_add_product_dialog)

        manage_cats_btn = QPushButton("🗂️ Categories")
        manage_cats_btn.setToolTip("Manage Categories and Subcategories")
        manage_cats_btn.setMinimumHeight(44)
        manage_cats_btn.clicked.connect(self.show_category_manager)
        
        low_btn = QPushButton("⚠️ Low Stock")
        low_btn.setToolTip("Show products at or below reorder level")
        low_btn.setProperty('accent', 'orange')
        low_btn.setMinimumHeight(44)
        low_btn.clicked.connect(self.show_low_stock_only)
        
        self.show_all_btn = QPushButton("📦 Show All")
        self.show_all_btn.setToolTip("Show all products")
        self.show_all_btn.setProperty('accent', 'Qt.blue')
        self.show_all_btn.setMinimumHeight(44)
        self.show_all_btn.clicked.connect(self.show_all_products)
        self.show_all_btn.setVisible(False)  # Initially hidden
        
        # Add refresh items button
        refresh_btn = QPushButton("🔄 Refresh Items")
        refresh_btn.setToolTip("Reload all products from database")
        refresh_btn.setProperty('accent', 'Qt.cyan')
        refresh_btn.setMinimumHeight(44)
        refresh_btn.clicked.connect(self.load_products)
        
        toolbar_layout.addWidget(add_btn)
        toolbar_layout.addWidget(manage_cats_btn)
        toolbar_layout.addWidget(low_btn)
        toolbar_layout.addWidget(self.show_all_btn)  # Add Show All button to toolbar
        toolbar_layout.addWidget(refresh_btn)  # Add Refresh button
        toolbar_layout.addStretch()
        layout.addLayout(toolbar_layout)

        # Search bar + pagination
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Search products... (type to search)')
        # Use debounced search instead of immediate filter
        self.search_input.textChanged.connect(self._on_search_text_changed)
        search_layout.addWidget(self.search_input)

        # Pagination
        self.page_size = 12
        self.current_page = 0
        self.prev_btn = QPushButton("Prev")
        self.next_btn = QPushButton("Next")
        self.page_label = QLabel("Page 1")
        self.prev_btn.clicked.connect(self._prev_page)
        self.next_btn.clicked.connect(self._next_page)
        search_layout.addStretch()
        search_layout.addWidget(self.prev_btn)
        search_layout.addWidget(self.page_label)
        search_layout.addWidget(self.next_btn)
        layout.addLayout(search_layout)

        # Products Table with purchase price
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Name", "Barcode", "Description", "Purchase Price",
            "Retail Price", "Wholesale Price", "Stock Level", "Location"
        ])
        
        # Set column widths
        self.table.setColumnWidth(0, 200)  # Name
        self.table.setColumnWidth(1, 120)  # Barcode
        self.table.setColumnWidth(2, 250)  # Description
        self.table.setColumnWidth(3, 120)  # Purchase Price
        self.table.setColumnWidth(4, 120)  # Retail Price
        self.table.setColumnWidth(5, 140)  # Wholesale Price
        self.table.setColumnWidth(6, 120)  # Stock Level
        self.table.setColumnWidth(7, 100)  # Location
        
        # Table selection
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        
        try:
            from PySide6.QtWidgets import QHeaderView
            self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            # Show vertical header (row numbers) and set proper width
            self.table.verticalHeader().setVisible(True)
            self.table.verticalHeader().setDefaultSectionSize(32)  # Set row height
            self.table.verticalHeader().setMinimumWidth(50)  # Set minimum width for row numbers
            self.table.setWordWrap(True)
        except Exception:
            pass
        
        layout.addWidget(self.table)

        # Total stock valuation summary (based on purchase price)
        valuation_layout = QHBoxLayout()
        self.valuation_label = QLabel("Total Stock Valuation (Purchase Price): Rs 0.00")
        self.valuation_label.setStyleSheet("""
            padding: 12px 16px;
            background: #f1f5f9;
            border-radius: 8px;
            font-size: 15px;
            font-weight: bold;
            color: #1e293b;
        """)
        valuation_layout.addWidget(self.valuation_label)
        valuation_layout.addStretch()
        layout.addLayout(valuation_layout)

    def _update_valuation(self):
        """Recalculate and display total stock valuation at purchase price across ALL products."""
        try:
            total = 0.0
            products = getattr(self, '_products_cache', None) or []
            for p in products:
                try:
                    qty = float(getattr(p, 'stock_level', 0) or 0)
                    price = float(getattr(p, 'purchase_price', 0) or 0)
                except Exception:
                    qty = price = 0.0
                total += qty * price
            self.valuation_label.setText(f"Total Stock Valuation (Purchase Price): Rs {total:,.2f}")
        except Exception as e:
            print(f"[Inventory] Error computing valuation: {e}")

    def on_selection_changed(self):
        """Enable/disable action buttons based on selection"""
        selected_rows = self.table.selectionModel().selectedRows()
        if selected_rows:
            row = selected_rows[0].row()
            # Get product ID from the current page items
            items = getattr(self, '_current_page_items', [])
            if 0 <= row < len(items):
                self.selected_product_id = items[row].id
                self.edit_product_btn.setEnabled(True)
                self.delete_product_btn.setEnabled(True)
            else:
                self.selected_product_id = None
                self.edit_product_btn.setEnabled(False)
                self.delete_product_btn.setEnabled(False)
        else:
            self.selected_product_id = None
            self.edit_product_btn.setEnabled(False)
            self.delete_product_btn.setEnabled(False)

    def edit_selected_product(self):
        if self.selected_product_id:
            self._edit_product(self.selected_product_id)

    def delete_selected_product(self):
        if self.selected_product_id:
            self._delete_product(self.selected_product_id)
    
    def _edit_product(self, product_id):
        """Open ProductDialog to edit an existing product and update stock/prices."""
        try:
            from pos_app.models.database import Product as ProductModel
            product = self.controller.session.get(ProductModel, product_id)
            if not product:
                QMessageBox.warning(self, "Error", "Product not found")
                return
            
            # CRITICAL: Expire the product to ensure fresh data from database
            # This prevents stale session data from overwriting correct stock values
            self.controller.session.expire(product)

            # Get product dialog type from settings
            from PySide6.QtCore import QSettings
            settings = QSettings("POSApp", "Settings")
            product_dialog_type = settings.value("product_dialog_type", "Detailed")
            # Convert to string and strip to handle different types/casing
            product_dialog_type = str(product_dialog_type).strip()
            print(f"[DEBUG] Product dialog type from settings: '{product_dialog_type}'")
            print(f"[DEBUG] Comparison: '{product_dialog_type}' == 'Simple' = {product_dialog_type == 'Simple'}")
            
            # Choose dialog type based on settings (same logic as add product)
            if product_dialog_type == "Simple":
                print(f"[DEBUG] Opening SIMPLE product dialog for product ID: {product_id}")
                from pos_app.views.simple_product_dialog import ProductDialog as SimpleProductDialog
                dialog = SimpleProductDialog(self, product)
                if dialog.exec() == QDialog.Accepted:
                    pdata = dialog.get_product_data()
                    # Map returned dict onto existing product (schema-safe)
                    for key, val in pdata.items():
                        if hasattr(product, key):
                            setattr(product, key, val)
                    # Commit
                    try:
                        self.controller.session.commit()
                        self.refresh_products_keep_page()
                    except Exception as e:
                        self.controller.session.rollback()
                        QMessageBox.critical(self, "Error", f"Failed to save product:\n\n{e}")
                return  # done
            else:
                print(f"[DEBUG] Opening DETAILED product dialog for product ID: {product_id}")
            # Otherwise use detailed dialog
            from pos_app.views.inventory_new import ProductDialog, safe_get_current_data
            dialog = ProductDialog(self, product)
            if dialog.exec() == QDialog.Accepted:
                # Apply edits
                product.name = dialog.name_input.text()
                # Description field was removed from ProductDialog
                product.description = None
                product.sku = dialog.sku_input.text()
                product.barcode = dialog.barcode_input.text().strip() or None
                product.purchase_price = dialog.purchase_price_input.value()
                product.wholesale_price = dialog.wholesale_price_input.value()
                product.retail_price = dialog.retail_price_input.value()
                
                # Handle stock with + operator support (e.g., "12+2" becomes 14)
                stock_text = dialog.stock_input.text().strip()
                original_stock = getattr(product, 'stock_level', 0)
                
                try:
                    if '+' in stock_text:
                        # Evaluate the expression (e.g., "12+2" = 14)
                        stock_value = int(eval(stock_text, {"__builtins__": {}}, {}))
                    elif stock_text:
                        # Only convert to int if there's actual text
                        stock_value = int(stock_text)
                    else:
                        # Preserve original stock if input is empty
                        stock_value = original_stock
                except:
                    # If conversion fails, preserve original stock
                    stock_value = original_stock
                    print(f"[DEBUG] Stock conversion failed for '{stock_text}', preserving original stock: {original_stock}")
                
                product.stock_level = stock_value
                print(f"[DEBUG] Stock updated: {original_stock} -> {stock_value}")
                
                product.reorder_level = dialog.reorder_input.value()
                product.supplier_id = safe_get_current_data(dialog.supplier_input)
                
                # Handle new fields
                try:
                    product.product_category_id = dialog.category_input.currentData()
                except Exception:
                    product.product_category_id = None
                try:
                    product.product_subcategory_id = dialog.subcategory_input.currentData()
                except Exception:
                    product.product_subcategory_id = None

                # Packaging type (optional)
                try:
                    cols = set(getattr(getattr(Product, '__table__', None), 'columns', {}).keys())
                except Exception:
                    cols = set()
                if ('packaging_type_id' in cols or hasattr(product, 'packaging_type_id')) and hasattr(dialog, 'packaging_type_input'):
                    try:
                        product.packaging_type_id = dialog.packaging_type_input.currentData()
                    except Exception:
                        try:
                            product.packaging_type_id = None
                        except Exception:
                            pass

                # Optional fields: brand/colors (schema-safe)
                try:
                    cols = set(getattr(getattr(Product, '__table__', None), 'columns', {}).keys())
                except Exception:
                    cols = set()
                if ('brand' in cols or hasattr(product, 'brand')) and hasattr(dialog, 'brand_input'):
                    try:
                        product.brand = (dialog.brand_input.currentText() or '').strip() or None
                    except Exception:
                        try:
                            product.brand = None
                        except Exception:
                            pass
                if ('colors' in cols or hasattr(product, 'colors')) and hasattr(dialog, 'colors_input'):
                    try:
                        product.colors = (dialog.colors_input.currentText() or '').strip() or None
                    except Exception:
                        try:
                            product.colors = None
                        except Exception:
                            pass

                # New fields (schema-safe)
                try:
                    cols = set(getattr(getattr(Product, '__table__', None), 'columns', {}).keys())
                except Exception:
                    cols = set()
                if ('product_type' in cols or hasattr(product, 'product_type')) and hasattr(dialog, 'product_type_input'):
                    try:
                        product.product_type = (dialog.product_type_input.currentText() or '').strip() or None
                    except Exception:
                        pass
                if ('unit' in cols or hasattr(product, 'unit')) and hasattr(dialog, 'unit_input'):
                    try:
                        product.unit = (dialog.unit_input.currentText() or '').strip() or None
                    except Exception:
                        pass
                if ('low_stock_alert' in cols or hasattr(product, 'low_stock_alert')) and hasattr(dialog, 'low_stock_alert_checkbox'):
                    try:
                        product.low_stock_alert = bool(dialog.low_stock_alert_checkbox.isChecked())
                    except Exception:
                        pass
                if ('warranty' in cols or hasattr(product, 'warranty')) and hasattr(dialog, 'warranty_input'):
                    try:
                        product.warranty = (dialog.warranty_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('weight' in cols or hasattr(product, 'weight')) and hasattr(dialog, 'weight_input'):
                    try:
                        product.weight = float(dialog.weight_input.value())
                    except Exception:
                        pass

                # Extended fields (schema-safe)
                if ('model' in cols or hasattr(product, 'model')) and hasattr(dialog, 'model_input'):
                    try:
                        product.model = (dialog.model_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('size' in cols or hasattr(product, 'size')) and hasattr(dialog, 'size_input'):
                    try:
                        product.size = (dialog.size_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('dimensions' in cols or hasattr(product, 'dimensions')) and hasattr(dialog, 'dimensions_input'):
                    try:
                        product.dimensions = (dialog.dimensions_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('shelf_location' in cols or hasattr(product, 'shelf_location')) and hasattr(dialog, 'shelf_location_input'):
                    try:
                        product.shelf_location = (dialog.shelf_location_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('warehouse_location' in cols or hasattr(product, 'warehouse_location')) and hasattr(dialog, 'warehouse_location_input'):
                    try:
                        product.warehouse_location = (dialog.warehouse_location_input.text() or '').strip() or None
                    except Exception:
                        pass
                if ('tax_rate' in cols or hasattr(product, 'tax_rate')) and hasattr(dialog, 'tax_rate_input'):
                    try:
                        product.tax_rate = float(dialog.tax_rate_input.value())
                    except Exception:
                        pass
                if ('discount_percentage' in cols or hasattr(product, 'discount_percentage')) and hasattr(dialog, 'discount_percentage_input'):
                    try:
                        product.discount_percentage = float(dialog.discount_percentage_input.value())
                    except Exception:
                        pass
                if ('notes' in cols or hasattr(product, 'notes')) and hasattr(dialog, 'notes_input'):
                    try:
                        product.notes = (dialog.notes_input.toPlainText() if hasattr(dialog.notes_input, 'toPlainText') else dialog.notes_input.text()).strip() or None
                    except Exception:
                        pass
                if ('is_active' in cols or hasattr(product, 'is_active')) and hasattr(dialog, 'is_active_checkbox'):
                    try:
                        product.is_active = bool(dialog.is_active_checkbox.isChecked())
                    except Exception:
                        pass

                # Legacy text fields (keep for older screens/reports)
                try:
                    cols = set(getattr(getattr(Product, '__table__', None), 'columns', {}).keys())
                except Exception:
                    cols = set()
                if 'category' in cols or hasattr(product, 'category'):
                    try:
                        product.category = (dialog.category_input.currentText() or '').strip() or None
                    except Exception:
                        try:
                            product.category = None
                        except Exception:
                            pass
                if 'subcategory' in cols or hasattr(product, 'subcategory'):
                    try:
                        product.subcategory = (dialog.subcategory_input.currentText() or '').strip() or None
                    except Exception:
                        try:
                            product.subcategory = None
                        except Exception:
                            pass
                try:
                    exp_str = None
                    try:
                        has_exp = bool(getattr(dialog, 'has_expiry_checkbox', None) and dialog.has_expiry_checkbox.isChecked())
                    except Exception:
                        has_exp = False
                    if has_exp:
                        try:
                            d = dialog.expiry_input.date()
                            exp_str = d.toString('yyyy-MM-dd')
                        except Exception:
                            exp_str = None
                    product.expiry_date = exp_str or None
                except Exception:
                    product.expiry_date = None

                # Commit and broadcast inventory sync
                self.controller.session.commit()
                self.refresh_products_keep_page()
                try:
                    from pos_app.models.database import mark_sync_changed
                    mark_sync_changed(self.controller.session, 'products')
                    mark_sync_changed(self.controller.session, 'stock')
                    self.controller.session.commit()
                except Exception:
                    try:
                        self.controller.session.commit()
                    except Exception:
                        pass

                self.load_products()
        except Exception as e:
            import traceback
            print(f"[ERROR] Edit product failed: {e}")
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to edit product:\n\n{str(e)}")

    def _delete_product(self, product_id):
        """Safely delete a product if it is not referenced in sales or purchases."""
        try:
            product = self.controller.session.get(Product, product_id)
            if not product:
                QMessageBox.warning(self, "Error", "Product not found")
                return

            # Check for foreign key dependencies
            from pos_app.models.database import SaleItem, PurchaseItem, StockMovement

            sale_items = self.controller.session.query(SaleItem).filter(
                SaleItem.product_id == product_id
            ).count()

            purchase_items = self.controller.session.query(PurchaseItem).filter(
                PurchaseItem.product_id == product_id
            ).count()

            if sale_items > 0 or purchase_items > 0:
                QMessageBox.warning(
                    self,
                    "Cannot Delete Product",
                    f"Cannot delete '{product.name}' because it is referenced in:\n\n"
                    f"• {sale_items} sale transaction(s)\n"
                    f"• {purchase_items} purchase transaction(s)\n\n"
                    f"You can mark it as inactive instead of deleting it."
                )
                return

            res = QMessageBox.question(
                self,
                "Confirm Delete",
                f"Are you sure you want to delete '{product.name}'?\n\n"
                f"This action cannot be undone.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if res != QMessageBox.Yes:
                return

            # Delete related stock movements first
            self.controller.session.query(StockMovement).filter(
                StockMovement.product_id == product_id
            ).delete()

            # Now delete the product
            self.controller.session.delete(product)
            self.controller.session.commit()

            # Broadcast sync change so all clients refresh inventory
            try:
                from pos_app.models.database import mark_sync_changed
                mark_sync_changed(self.controller.session, 'products')
                mark_sync_changed(self.controller.session, 'stock')
                self.controller.session.commit()
            except Exception:
                try:
                    self.controller.session.commit()
                except Exception:
                    pass

            QMessageBox.information(self, "Success", f"Product '{product.name}' deleted successfully")
            self.load_products()
        except Exception as e:
            try:
                self.controller.session.rollback()
            except Exception:
                pass
            QMessageBox.critical(self, "Error", f"Failed to delete product:\n\n{str(e)}")
    
    def show_add_product_dialog(self):
        """Open appropriate product dialog based on settings (simple or detailed)"""
        try:
            # Get product dialog type from settings
            from PySide6.QtCore import QSettings
            settings = QSettings("POSApp", "Settings")
            product_dialog_type = settings.value("product_dialog_type", "Detailed")
            product_dialog_type = str(product_dialog_type).strip()
            print(f"[DEBUG] ADD PRODUCT - Dialog type from settings: '{product_dialog_type}'")
            print(f"[DEBUG] ADD PRODUCT - Comparison: '{product_dialog_type}' == 'Simple' = {product_dialog_type == 'Simple'}")
            
            if product_dialog_type == "Simple":
                # Use simple product dialog
                print(f"[DEBUG] ADD PRODUCT - Opening SIMPLE dialog")
                from pos_app.views.simple_product_dialog import ProductDialog
                dialog = ProductDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    # Get product data from simple dialog
                    product_data = dialog.get_product_data()
                    self.controller.add_product(**product_data)
            else:
                # Use detailed product dialog (default)
                print(f"[DEBUG] ADD PRODUCT - Opening DETAILED dialog")
                from pos_app.views.inventory_new import ProductDialog, safe_get_current_data
                dialog = ProductDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    # Handle stock with + operator support (e.g., "12+2" becomes 14)
                    stock_text = dialog.stock_input.text().strip()
                    try:
                        if '+' in stock_text:
                            # Evaluate the expression (e.g., "12+2" = 14)
                            stock_value = int(eval(stock_text, {"__builtins__": {}}, {}))
                        else:
                            stock_value = int(stock_text) if stock_text else 0
                    except:
                        stock_value = 0
                    
                    # Create product via controller
                    self.controller.add_product(
                        name=dialog.name_input.text(),
                        description=None,
                        sku=dialog.sku_input.text(),
                        barcode=(dialog.barcode_input.text().strip() or None),
                        purchase_price=dialog.purchase_price_input.value(),
                        wholesale_price=dialog.wholesale_price_input.value(),
                        retail_price=dialog.retail_price_input.value(),
                        stock_level=stock_value,
                        reorder_level=dialog.reorder_input.value(),
                        supplier_id=(safe_get_current_data(dialog.supplier_input) or None),
                        unit=(dialog.unit_input.currentText() if hasattr(dialog, 'unit_input') else "pcs"),
                        shelf_location=(dialog.shelf_location_input.text().strip() if hasattr(dialog, 'shelf_location_input') else ""),
                        warehouse_location=(dialog.warehouse_location_input.text().strip() if hasattr(dialog, 'warehouse_location_input') else None),
                        product_category_id=(dialog.category_input.currentData() if hasattr(dialog, 'category_input') else None),
                        product_subcategory_id=(dialog.subcategory_input.currentData() if hasattr(dialog, 'subcategory_input') else None),
                        packaging_type_id=(dialog.packaging_type_input.currentData() if hasattr(dialog, 'packaging_type_input') else None),
                        category=(dialog.category_input.currentText() or '').strip() or None,
                        subcategory=(dialog.subcategory_input.currentText() or '').strip() or None,
                        brand=(dialog.brand_input.currentText().strip() or None) if hasattr(dialog, 'brand_input') else None,
                        colors=(dialog.colors_input.currentText().strip() or None) if hasattr(dialog, 'colors_input') else None,
                        model=(dialog.model_input.text().strip() or None) if hasattr(dialog, 'model_input') else None,
                        size=(dialog.size_input.text().strip() or None) if hasattr(dialog, 'size_input') else None,
                        dimensions=(dialog.dimensions_input.text().strip() or None) if hasattr(dialog, 'dimensions_input') else None,
                        tax_rate=(dialog.tax_rate_input.value() if hasattr(dialog, 'tax_rate_input') else None),
                        discount_percentage=(dialog.discount_percentage_input.value() if hasattr(dialog, 'discount_percentage_input') else None),
                        notes=((dialog.notes_input.toPlainText() if hasattr(dialog.notes_input, 'toPlainText') else dialog.notes_input.text()).strip() or None) if hasattr(dialog, 'notes_input') else None,
                        is_active=(bool(dialog.is_active_checkbox.isChecked()) if hasattr(dialog, 'is_active_checkbox') else None),
                        product_type=(dialog.product_type_input.currentText() if hasattr(dialog, 'product_type_input') else None),
                        low_stock_alert=(bool(dialog.low_stock_alert_checkbox.isChecked()) if hasattr(dialog, 'low_stock_alert_checkbox') else None),
                        warranty=(dialog.warranty_input.text().strip() or None) if hasattr(dialog, 'warranty_input') else None,
                        weight=(dialog.weight_input.value() if hasattr(dialog, 'weight_input') else None),
                        expiry_date=(dialog.expiry_input.date().toString('yyyy-MM-dd') if hasattr(dialog, 'expiry_input') and dialog.has_expiry_checkbox.isChecked() else None),
                    )
            
            # Refresh product list
            self.load_products()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add product: {str(e)}")

    def show_category_manager(self):
        try:
            session = getattr(getattr(self, 'controller', None), 'session', None)
            if session is None:
                return
        except Exception:
            return

        try:
            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QMessageBox, QInputDialog
        except ImportError:
            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QPushButton, QMessageBox, QInputDialog

        try:
            from sqlalchemy import text
        except Exception:
            text = None

        try:
            from pos_app.models.database import ProductCategory, ProductSubcategory
        except Exception:
            return

        dlg = QDialog(self)
        dlg.setWindowTitle("Manage Categories")
        dlg.setMinimumWidth(520)

        root = QVBoxLayout(dlg)
        title = QLabel("Product Categories & Subcategories")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        root.addWidget(title)

        lists_row = QHBoxLayout()

        cat_col = QVBoxLayout()
        cat_col.addWidget(QLabel("Categories"))
        categories_list = QListWidget()
        cat_col.addWidget(categories_list)

        sub_col = QVBoxLayout()
        sub_col.addWidget(QLabel("Subcategories"))
        subcategories_list = QListWidget()
        sub_col.addWidget(subcategories_list)

        lists_row.addLayout(cat_col, 1)
        lists_row.addLayout(sub_col, 1)
        root.addLayout(lists_row)

        btns = QHBoxLayout()
        add_cat_btn = QPushButton("+ Category")
        del_cat_btn = QPushButton("Delete Category")
        add_sub_btn = QPushButton("+ Subcategory")
        del_sub_btn = QPushButton("Delete Subcategory")
        close_btn = QPushButton("Close")
        btns.addWidget(add_cat_btn)
        btns.addWidget(del_cat_btn)
        btns.addStretch()
        btns.addWidget(add_sub_btn)
        btns.addWidget(del_sub_btn)
        btns.addStretch()
        btns.addWidget(close_btn)
        root.addLayout(btns)

        def _item_id(it):
            try:
                return it.data(32) if it is not None else None
            except Exception:
                return None

        def load_subs_for_selected():
            try:
                subcategories_list.clear()
            except Exception:
                return
            cat_id = _item_id(categories_list.currentItem())
            if not cat_id:
                return
            try:
                subs = session.query(ProductSubcategory).filter(ProductSubcategory.category_id == int(cat_id)).order_by(ProductSubcategory.name.asc()).all()
            except Exception:
                subs = []
            for s in subs or []:
                try:
                    subcategories_list.addItem(f"{s.name}")
                    subcategories_list.item(subcategories_list.count() - 1).setData(32, getattr(s, 'id', None))
                except Exception:
                    pass

        def load_lists(select_cat_id=None):
            try:
                categories_list.clear()
                subcategories_list.clear()
            except Exception:
                return
            try:
                cats = session.query(ProductCategory).order_by(ProductCategory.name.asc()).all()
            except Exception:
                cats = []
            for c in cats or []:
                try:
                    categories_list.addItem(f"{c.name}")
                    categories_list.item(categories_list.count() - 1).setData(32, getattr(c, 'id', None))
                except Exception:
                    pass
            try:
                if categories_list.count() > 0:
                    idx = 0
                    if select_cat_id is not None:
                        for i in range(categories_list.count()):
                            if _item_id(categories_list.item(i)) == select_cat_id:
                                idx = i
                                break
                    categories_list.setCurrentRow(idx)
            except Exception:
                pass
            load_subs_for_selected()

        def add_category():
            name, ok = QInputDialog.getText(dlg, "Add Category", "Category name:")
            if not ok:
                return
            name = (name or '').strip()
            if not name:
                return
            try:
                existing = session.query(ProductCategory).filter(ProductCategory.name.ilike(name)).first()
                if existing is None:
                    obj = ProductCategory(name=name)
                    session.add(obj)
                    session.commit()
                else:
                    obj = existing
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
                return
            load_lists(select_cat_id=getattr(obj, 'id', None))

        def add_subcategory():
            cat_id = _item_id(categories_list.currentItem())
            if not cat_id:
                QMessageBox.warning(dlg, "Subcategory", "Select a category first.")
                return
            name, ok = QInputDialog.getText(dlg, "Add Subcategory", "Subcategory name:")
            if not ok:
                return
            name = (name or '').strip()
            if not name:
                return
            try:
                existing = session.query(ProductSubcategory).filter(
                    ProductSubcategory.category_id == int(cat_id),
                    ProductSubcategory.name.ilike(name)
                ).first()
                if existing is None:
                    obj = ProductSubcategory(category_id=int(cat_id), name=name)
                    session.add(obj)
                    session.commit()
                else:
                    obj = existing
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
                return
            load_lists(select_cat_id=int(cat_id))
            try:
                for i in range(subcategories_list.count()):
                    if _item_id(subcategories_list.item(i)) == getattr(obj, 'id', None):
                        subcategories_list.setCurrentRow(i)
                        break
            except Exception:
                pass

        def delete_category():
            cat_id = _item_id(categories_list.currentItem())
            if not cat_id:
                return
            used = 0
            if text is not None:
                try:
                    used = session.execute(text("SELECT COUNT(1) FROM products WHERE product_category_id = :cid"), {'cid': int(cat_id)}).scalar() or 0
                except Exception:
                    used = 0
            if used:
                QMessageBox.warning(dlg, "Category", "Category is in use by products and cannot be deleted.")
                return
            try:
                session.query(ProductSubcategory).filter(ProductSubcategory.category_id == int(cat_id)).delete(synchronize_session=False)
                session.query(ProductCategory).filter(ProductCategory.id == int(cat_id)).delete(synchronize_session=False)
                session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
                return
            load_lists()

        def delete_subcategory():
            sub_id = _item_id(subcategories_list.currentItem())
            if not sub_id:
                return
            used = 0
            if text is not None:
                try:
                    used = session.execute(text("SELECT COUNT(1) FROM products WHERE product_subcategory_id = :sid"), {'sid': int(sub_id)}).scalar() or 0
                except Exception:
                    used = 0
            if used:
                QMessageBox.warning(dlg, "Subcategory", "Subcategory is in use by products and cannot be deleted.")
                return
            try:
                session.query(ProductSubcategory).filter(ProductSubcategory.id == int(sub_id)).delete(synchronize_session=False)
                session.commit()
            except Exception:
                try:
                    session.rollback()
                except Exception:
                    pass
                return
            load_subs_for_selected()

        close_btn.clicked.connect(dlg.accept)
        add_cat_btn.clicked.connect(add_category)
        add_sub_btn.clicked.connect(add_subcategory)
        del_cat_btn.clicked.connect(delete_category)
        del_sub_btn.clicked.connect(delete_subcategory)
        categories_list.currentItemChanged.connect(lambda *_: load_subs_for_selected())

        load_lists()
        dlg.exec()

        try:
            self.load_products()
        except Exception:
            pass
    
    def _on_product_scanned(self, product):
        """Handle product scanned from barcode widget"""
        try:
            # Select the product in the table
            for row in range(self.table.rowCount()):
                sku_item = self.table.item(row, 0)
                if sku_item and hasattr(product, 'sku') and sku_item.text() == (product.sku or ""):
                    self.table.selectRow(row)
                    self.selected_product_id = product.id
                    self.edit_product_btn.setEnabled(True)
                    self.delete_product_btn.setEnabled(True)
                    
                    # Show product details
                    QMessageBox.information(
                        self,
                        "Product Found",
                        f"<b>{product.name}</b><br><br>"
                        f"SKU: {product.sku or 'N/A'}<br>"
                        f"Barcode: {product.barcode or 'N/A'}<br>"
                        f"Stock: {product.stock_level or 0}<br>"
                        f"Retail Price: Rs {product.retail_price or 0:,.2f}<br>"
                        f"Purchase Price: Rs {product.purchase_price or 0:,.2f}<br><br>"
                        f"Product selected in table. You can now edit or delete it."
                    )
                    return
                    
            # Product not found in current table view
            QMessageBox.information(
                self,
                "Product Found",
                f"<b>{product.name}</b><br><br>"
                f"SKU: {product.sku or 'N/A'}<br>"
                f"Barcode: {product.barcode or 'N/A'}<br>"
                f"Stock: {product.stock_level or 0}<br>"
                f"Retail Price: Rs {product.retail_price or 0:,.2f}<br><br>"
                f"Product found but not visible in current table view.<br>"
                f"Try refreshing the product list."
            )
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to process scanned product: {str(e)}")

    def load_products(self):
        try:
            # Get products with purchase price, sorted by creation date (newest first)
            from pos_app.models.database import Product
            print("[DEBUG] Starting to load products...")
            try:
                # For network performance, load ALL products into RAM at startup
                # This eliminates database queries during search in network environments
                print("[Inventory] Loading ALL products into RAM for optimal network performance...")
                products = self.controller.session.query(Product).order_by(Product.created_at.desc()).all()
                total_count = len(products)
                print(f"[DEBUG] Loaded {total_count} products from database")
                
                # Store all products in cache for instant search
                self._products_cache = products
                self._total_products_count = total_count
                print(f"[DEBUG] Products cache created with {total_count} items")
                
                # Create search-optimized data structures for even faster lookup
                print("[DEBUG] Creating search indexes...")
                self._product_names = [p.name.lower() if p.name else '' for p in products]
                self._product_barcodes = [p.barcode.lower() if p.barcode else '' for p in products]
                self._product_skus = [p.sku.lower() if p.sku else '' for p in products]
                
                # Create unified search index for maximum performance
                self._search_index = []
                for i, product in enumerate(products):
                    searchable_text = f"{self._product_names[i]} {self._product_barcodes[i]} {self._product_skus[i]}"
                    self._search_index.append(searchable_text)
                
                print(f"[DEBUG] Search index created with {len(self._search_index)} entries")
                print(f"[Inventory] Loaded {total_count} products into RAM cache")
                
            except Exception as e:
                print(f"[DEBUG] Error in main loading: {e}")
                # Fallback if created_at doesn't exist
                products = self.controller.session.query(Product).order_by(Product.id.desc()).all()
                total_count = len(products)
                self._products_cache = products
                self._total_products_count = total_count
                
                # Create search-optimized data structures
                self._product_names = [p.name.lower() if p.name else '' for p in products]
                self._product_barcodes = [p.barcode.lower() if p.barcode else '' for p in products]
                self._product_skus = [p.sku.lower() if p.sku else '' for p in products]
                
                # Create unified search index for maximum performance
                self._search_index = []
                for i, product in enumerate(products):
                    searchable_text = f"{self._product_names[i]} {self._product_barcodes[i]} {self._product_skus[i]}"
                    self._search_index.append(searchable_text)
                
                print(f"[DEBUG] Fallback search index created with {len(self._search_index)} entries")
            
            # Reset to first page
            self.current_page = 0
            
            # Only populate visible page items (much faster than loading all)
            self._update_page()

            # Update total stock valuation summary
            self._update_valuation()

            # Update sync timestamp snapshot
            try:
                from pos_app.models.database import get_sync_timestamp
                ts = get_sync_timestamp(self.controller.session, 'products')
                self._last_sync_ts = ts
            except Exception:
                pass
            
            # Start polling for sync state changes
            self._init_sync_timer()
            
            print(f"[DEBUG] Product loading completed successfully")
                
        except Exception as e:
            print(f"[DEBUG] Error loading products: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                self.controller.session.rollback()
            except Exception:
                pass
    
    def refresh_products_keep_page(self):
        """Refresh products list but stay on current page (network optimized)"""
        try:
            # For network performance, reload ALL products into RAM cache
            # This ensures search remains instant after refresh
            print("[Inventory] Refreshing ALL products into RAM cache...")
            from pos_app.models.database import Product
            try:
                products = self.controller.session.query(Product).order_by(Product.created_at.desc()).all()
                total_count = len(products)
                
                # Update cache
                self._products_cache = products
                self._total_products_count = total_count
                
                # Update search-optimized data structures
                self._product_names = [p.name.lower() if p.name else '' for p in products]
                self._product_barcodes = [p.barcode.lower() if p.barcode else '' for p in products]
                self._product_skus = [p.sku.lower() if p.sku else '' for p in products]
                
                # Create unified search index for maximum performance
                self._search_index = []
                for i, product in enumerate(products):
                    searchable_text = f"{self._product_names[i]} {self._product_barcodes[i]} {self._product_skus[i]}"
                    self._search_index.append(searchable_text)
                
                print(f"[Inventory] Refreshed search index with {len(self._search_index)} entries")
                
                print(f"[Inventory] Refreshed {total_count} products in RAM cache")
                
            except Exception as e:
                print(f"[Inventory] Error during refresh: {e}")
                # Fallback if created_at doesn't exist
                try:
                    products = self.controller.session.query(Product).order_by(Product.id.desc()).all()
                    total_count = len(products)
                    
                    # Update cache and search structures
                    self._products_cache = products
                    self._total_products_count = total_count
                    self._product_names = [p.name.lower() if p.name else '' for p in products]
                    self._product_barcodes = [p.barcode.lower() if p.barcode else '' for p in products]
                    self._product_skus = [p.sku.lower() if p.sku else '' for p in products]
                    
                    # Create unified search index for maximum performance
                    self._search_index = []
                    for i, product in enumerate(products):
                        searchable_text = f"{self._product_names[i]} {self._product_barcodes[i]} {self._product_skus[i]}"
                        self._search_index.append(searchable_text)
                    
                    print(f"[Inventory] Refreshed search index with {len(self._search_index)} entries (fallback)")
                    
                    print(f"[Inventory] Refreshed {total_count} products in RAM cache (fallback)")
                except Exception as fallback_e:
                    print(f"[Inventory] Fallback refresh failed: {fallback_e}")
            
            # Update current page (maintain user's position)
            self._update_page()

            # Update total stock valuation summary
            self._update_valuation()

        except Exception as e:
            print(f"[Inventory] Error refreshing products: {e}")
        finally:
            try:
                self.controller.session.rollback()
            except Exception:
                pass

    def _update_page(self):
        """Update the product table with current page data"""
        try:
            # Get items to display (either filtered or all products)
            items = getattr(self, '_filtered_products', self._products_cache)
            
            # Calculate pagination
            start = self.current_page * self.page_size
            page_items = items[start:start + self.page_size]
            self._current_page_items = page_items

            self.table.setRowCount(len(page_items))
            for row, product in enumerate(page_items):
                self.table.setItem(row, 0, QTableWidgetItem(product.name or ""))
                self.table.setItem(row, 1, QTableWidgetItem(product.barcode or ""))
                self.table.setItem(row, 2, QTableWidgetItem(product.description or ""))
                
                purchase_price = QTableWidgetItem(f"Rs {product.purchase_price:,.2f}" if product.purchase_price else "N/A")
                retail_price = QTableWidgetItem(f"Rs {product.retail_price:,.2f}" if product.retail_price else "N/A")
                wholesale_price = QTableWidgetItem(f"Rs {product.wholesale_price:,.2f}" if product.wholesale_price else "N/A")
                stock_qty = QTableWidgetItem(str(product.stock_level) if product.stock_level is not None else "0")
                
                self.table.setItem(row, 3, purchase_price)
                self.table.setItem(row, 4, retail_price)
                self.table.setItem(row, 5, wholesale_price)
                self.table.setItem(row, 6, stock_qty)
                
                stock_item = stock_qty
                stock_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                if product.stock_level is not None and product.reorder_level is not None:
                    if product.stock_level <= product.reorder_level:
                        stock_item.setForeground(Qt.red)
                        stock_item.setToolTip(f"Low stock! Reorder level: {product.reorder_level}")
                self.table.setItem(row, 6, stock_item)
                
                # Location display logic
                location_text = ""
                if product.warehouse_location and not product.shelf_location:
                    location_text = "Warehouse"
                elif product.shelf_location and not product.warehouse_location:
                    location_text = "Shelf"
                elif product.warehouse_location and product.shelf_location:
                    location_text = "Both"
                
                location_item = QTableWidgetItem(location_text)
                self.table.setItem(row, 7, location_item)
            
            # Auto-select first row if there's only one item and ensure correct ID is set
            if len(page_items) == 1:
                self.table.selectRow(0)
                # Always ensure selected_product_id is set correctly for single result
                self.selected_product_id = page_items[0].id
                self.edit_product_btn.setEnabled(True)
                self.delete_product_btn.setEnabled(True)
                print(f"[DEBUG] Auto-selected single product: ID={self.selected_product_id}")
            
            # Update pagination controls - simple and straightforward
            total_pages = max(1, (len(items) + self.page_size - 1) // self.page_size)
            self.page_label.setText(f"Page {self.current_page+1} / {total_pages}")
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled((self.current_page + 1) < total_pages)
            self.next_btn.setText("Next")
            
        except Exception as e:
            print(f"[Inventory] Error updating page: {e}")
    
    def _update_pagination_controls(self):
        """Update pagination controls"""
        try:
            items = getattr(self, '_filtered_products', self._products_cache)
            total_pages = max(1, (len(items) + self.page_size - 1) // self.page_size)
            self.page_label.setText(f"Page {self.current_page+1} / {total_pages}")
            self.prev_btn.setEnabled(self.current_page > 0)
            self.next_btn.setEnabled((self.current_page + 1) < total_pages)
        except Exception as e:
            print(f"[Inventory] Error updating pagination: {e}")

    def _on_search_text_changed(self, text):
        """Handle search text change with debouncing to prevent UI freeze"""
        try:
            print(f"[DEBUG] Search text changed: '{text}'")
            # Store the search text
            self._pending_search_text = text
            # Stop any existing timer
            self._search_timer.stop()
            
            # Instant search - no minimum character requirement for RAM-based search
            # Start new timer - search will execute after 50ms of no typing (truly instant)
            self._search_timer.start(50)  # Reduced to 50ms for truly instant feel
        except Exception:
            pass
    
    def _perform_search(self):
        """Perform the actual search (called after debounce delay)"""
        try:
            import time
            start_time = time.time()
            text = self._pending_search_text.strip().lower()
            print(f"[DEBUG] Performing search for: '{text}'")
            self.apply_filter(text)
            end_time = time.time()
            print(f"[DEBUG] Search completed in {(end_time - start_time)*1000:.1f}ms")
        except Exception:
            pass
    
    def apply_filter(self, text):
        """Apply search filter to products (optimized for network performance using RAM cache)"""
        try:
            import time
            start_time = time.time()
            print(f"[DEBUG] Apply filter called with: '{text}'")
            print(f"[DEBUG] Has _products_cache: {hasattr(self, '_products_cache')}")
            print(f"[DEBUG] Products cache size: {len(getattr(self, '_products_cache', []))}")
            
            if not hasattr(self, '_products_cache'):
                print("[DEBUG] No products cache - returning")
                return
            
            if not text:
                print("[DEBUG] Empty text - clearing filter")
                if hasattr(self, '_filtered_products'):
                    del self._filtered_products
                self.current_page = 0
                self._update_page()
                end_time = time.time()
                print(f"[DEBUG] Clear filter completed in {(end_time - start_time)*1000:.1f}ms")
                return
            
            # Simple fast search strategy
            search_text = text.lower()
            filtered = []
            products = self._products_cache
            
            print(f"[DEBUG] Starting search through {len(products)} products")
            search_start_time = time.time()
            
            # Simple search through all products - no limits, no complexity
            filtered = self._simple_fast_search(search_text, products)
            
            search_end_time = time.time()
            print(f"[DEBUG] Search completed: {len(filtered)} results found in {(search_end_time - search_start_time)*1000:.1f}ms")
            
            # Store filtered results and update UI instantly
            self._filtered_products = filtered
            self.current_page = 0
            
            ui_start_time = time.time()
            self._update_page()
            ui_end_time = time.time()
            print(f"[DEBUG] UI update completed in {(ui_end_time - ui_start_time)*1000:.1f}ms")
            
            end_time = time.time()
            print(f"[DEBUG] Total apply_filter completed in {(end_time - start_time)*1000:.1f}ms")
            
        except Exception as e:
            print(f"[Inventory] Error in apply_filter: {e}")
            import traceback
            traceback.print_exc()
    
    def _simple_fast_search(self, search_text, products):
        """Simple fast search through all products - no limits, just fast"""
        filtered = []
        
        # Use pre-computed search index for maximum performance
        if hasattr(self, '_search_index'):
            print(f"[DEBUG] Using search index for simple fast search")
            # Single pass search through unified index - no limits
            for i, searchable_text in enumerate(self._search_index):
                if search_text in searchable_text:
                    filtered.append(products[i])
        else:
            print(f"[DEBUG] Using fallback simple search")
            # Fallback to individual field search - no limits
            for i, product in enumerate(products):
                name_lower = (product.name or '').lower()
                barcode_lower = (product.barcode or '').lower()
                sku_lower = (product.sku or '').lower()
                if search_text in name_lower or search_text in barcode_lower or search_text in sku_lower:
                    filtered.append(product)
        
        print(f"[DEBUG] Simple fast search found {len(filtered)} results")
        return filtered
    
    def _full_catalog_search(self, search_text, products):
        """Optimized full catalog search using pre-computed indexes"""
        filtered = []
        
        # Use pre-computed search index for maximum performance
        if hasattr(self, '_search_index'):
            # Single pass search through unified index
            for i, searchable_text in enumerate(self._search_index):
                if search_text in searchable_text:
                    filtered.append(products[i])
                    # For full catalog search, show all results but limit to 200 for performance
                    if len(filtered) >= 200:
                        break
        else:
            # Fallback to individual field search
            for i, product in enumerate(products):
                name_lower = (product.name or '').lower()
                barcode_lower = (product.barcode or '').lower()
                sku_lower = (product.sku or '').lower()
                if search_text in name_lower or search_text in barcode_lower or search_text in sku_lower:
                    filtered.append(product)
                    if len(filtered) >= 200:
                        break
        
        return filtered
    
    def _early_termination_search(self, search_text, products):
        """Fast search with early termination for common use cases"""
        filtered = []
        
        # Direct search through products - optimized for early termination
        for i, product in enumerate(products):
            # Simple string matching - fastest possible
            name_match = search_text in (product.name or '').lower()
            barcode_match = search_text in (product.barcode or '').lower()
            sku_match = search_text in (product.sku or '').lower()
            
            if name_match or barcode_match or sku_match:
                filtered.append(product)
                # Early termination for instant results - increased to 100 for better UX
                if len(filtered) >= 100:  # Show 100 results for longer searches
                    print(f"[DEBUG] Early termination at {i} products with {len(filtered)} results")
                    break
            
            # Debug every 1000 products to see progress
            if i % 1000 == 0 and i > 0:
                print(f"[DEBUG] Searched {i} products, found {len(filtered)} results")
        
        return filtered

    def _prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self._update_page()

    def _next_page(self):
        """Simple next page functionality"""
        try:
            items = getattr(self, '_filtered_products', self._products_cache)
            total_pages = max(1, (len(items) + self.page_size - 1) // self.page_size)
            if (self.current_page + 1) < total_pages:
                self.current_page += 1
                self._update_page()
        except Exception as e:
            print(f"[Inventory] Error in next page: {e}")

    def show_low_stock_only(self):
        try:
            products = getattr(self, '_products_cache', [])
            lows = []
            for p in products:
                try:
                    lvl = (p.stock_level or 0)
                    thr = (p.reorder_level or 0)
                    if lvl <= thr:
                        lows.append(p)
                except Exception:
                    pass
            self._filtered_products = lows
            self.current_page = 0
            self._update_page()
            self.show_all_btn.setVisible(True)
        except Exception:
            pass

    def show_all_products(self):
        try:
            if hasattr(self, '_filtered_products'):
                del self._filtered_products
            self.current_page = 0
            self._update_page()
            self.show_all_btn.setVisible(False)
            self._check_for_updates()
        except Exception:
            pass

    def _check_for_updates(self):
        """Check for server updates and refresh if needed"""
        try:
            # Check if server has new products
            from pos_app.models.database import get_sync_timestamp
            current_sync = get_sync_timestamp(self.controller.session, 'products')
            
            if current_sync and self._last_sync_ts and current_sync > self._last_sync_ts:
                print("[Inventory] Server updates detected - refreshing product cache")
                self.refresh_products_keep_page()
                self._last_sync_ts = current_sync
            
            # Schedule next check (every 30 seconds)
            self._sync_timer.start(30000)  # 30 seconds
            
        except Exception as e:
            print(f"[Inventory] Error checking for updates: {e}")
            # Schedule next check even if there was an error
            self._sync_timer.start(30000)
        finally:
            try:
                self.controller.session.rollback()
            except Exception:
                pass

    def _init_sync_timer(self):
        """Initialize the sync timer"""
        try:
            from pos_app.models.database import get_sync_timestamp
            self._last_sync_ts = get_sync_timestamp(self.controller.session, 'products')
            
            # Start periodic sync checks
            self._sync_timer.start(30000)  # Check every 30 seconds
            
        except Exception as e:
            print(f"[Inventory] Error initializing sync timer: {e}")
            # Fallback - check anyway
            self._sync_timer.start(30000)

    def load_categories(self):
        """Load product categories from database"""
        try:
            categories = self.controller.session.query(ProductCategory).order_by(ProductCategory.name.asc()).all()
            return [(c.name, c.id) for c in categories] if categories else []
        except Exception as e:
            print(f"[DEBUG] Error loading categories: {e}")
            return []

    def load_subcategories(self, category_id=None):
        """Load product subcategories from database, optionally filtered by category"""
        try:
            query = self.controller.session.query(ProductSubcategory).order_by(ProductSubcategory.name.asc())
            if category_id:
                query = query.filter(ProductSubcategory.category_id == category_id)
            subcategories = query.all()
            return [(s.name, s.id) for s in subcategories] if subcategories else []
        except Exception as e:
            print(f"[DEBUG] Error loading subcategories: {e}")
            return []

    def load_suppliers(self):
        """Load active suppliers from database"""
        try:
            suppliers = self.controller.session.query(Supplier).filter(Supplier.is_active == True).order_by(Supplier.name.asc()).all()
            return [(s.name, s.id) for s in suppliers] if suppliers else []
        except Exception as e:
            print(f"[DEBUG] Error loading suppliers: {e}")
            return []

    def _check_for_remote_changes(self):
        try:
            from pos_app.models.database import get_sync_timestamp
            ts = get_sync_timestamp(self.controller.session, 'products')
            if ts is None:
                return
            if self._last_sync_ts is None or ts > self._last_sync_ts:
                self._last_sync_ts = ts
                self.load_products()
        except Exception:
            pass

# If anything goes wrong, err on the side of not submitting
            return True

    def load_product_data(self):
        if not self.product:
            return
            
        self.sku_input.setText(self.product.sku or "")
        self.name_input.setText(self.product.name or "")
        self.description_input.setText(self.product.description or "")
        self.purchase_price_input.setValue(float(self.product.purchase_price or 0))
        self.retail_price_input.setValue(float(self.product.retail_price or 0))
        self.wholesale_price_input.setValue(float(self.product.wholesale_price or 0))
        self.stock_input.setValue(int(self.product.stock_level or 0))
        self.reorder_level_input.setValue(int(self.product.reorder_level or 5))
        # Set supplier selection if available
        try:
            if self.product.supplier_id is not None:
                for i in range(self.supplier_input.count()):
                    if self.supplier_input.itemData(i) == self.product.supplier_id:
                        self.supplier_input.setCurrentIndex(i)
                        break
        except Exception:
            pass
            
        # Set location selection based on product data
        try:
            # Default to "Both" if no specific location is set
            location_choice = 2  # Both
            
            # Check if product has location preferences
            if hasattr(self.product, 'warehouse_location') and self.product.warehouse_location:
                if hasattr(self.product, 'shelf_location') and self.product.shelf_location:
                    location_choice = 2  # Both
                else:
                    location_choice = 0  # Warehouse
            elif hasattr(self.product, 'shelf_location') and self.product.shelf_location:
                location_choice = 1  # Retail
            
            self.location_group.button(location_choice).setChecked(True)
        except Exception:
            # Default to Both if there's any issue
            self.both_radio.setChecked(True)

    def get_selected_location(self):
        """Get the selected storage location"""
        location_id = self.location_group.checkedId()
        if location_id == 0:  # Warehouse
            return InventoryLocation.WAREHOUSE
        elif location_id == 1:  # Retail
            return InventoryLocation.RETAIL
        else:  # Both or default
            return InventoryLocation.BOTH
