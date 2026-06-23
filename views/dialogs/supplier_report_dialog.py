"""
Detailed supplier purchase history report.

Rewritten to:
- Treat `get_supplier_purchase_history` results as Purchase ORM objects
  (they are — not dicts), so item details, CSV export, and the payment→purchase
  cross-link actually work.
- Use a single query for payment history instead of N+1 per-purchase queries.
- Lay out responsively with a vertical QSplitter and Stretch columns so the
  dialog resizes cleanly at any window size.
"""
try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox, QScrollArea,
        QWidget, QHeaderView, QComboBox, QDateEdit, QFrame, QSizePolicy,
        QSplitter, QGridLayout
    )
    from PySide6.QtCore import Qt, QDate
except ImportError:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QMessageBox, QGroupBox, QScrollArea,
        QWidget, QHeaderView, QComboBox, QDateEdit, QFrame, QSizePolicy,
        QSplitter, QGridLayout
    )
    from PyQt6.QtCore import Qt, QDate
from pos_app.models.database import Supplier


_STYLESHEET = """
QDialog { background-color: #f4f6fb; }
QGroupBox {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
    color: #334155;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: #2563eb;
}
QLabel { color: #1e293b; }
QTableWidget {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    gridline-color: #cbd5e1;
    selection-background-color: #dbeafe;
    selection-color: #0f172a;
    alternate-background-color: #f1f5f9;
    font-size: 13px;
}
QTableWidget::item { padding: 7px 6px; border: none; color: #0f172a; }
QTableWidget::item:selected { background-color: #dbeafe; color: #0f172a; }
QHeaderView::section {
    background-color: #1e293b;
    color: #ffffff;
    padding: 9px 8px;
    border: none;
    font-weight: 700;
    font-size: 12px;
}
QPushButton {
    background-color: #2563eb; color: white; border: none;
    padding: 8px 16px; border-radius: 8px; font-weight: 600;
}
QPushButton:hover { background-color: #1d4ed8; }
QPushButton:pressed { background-color: #1e40af; }
QPushButton[accent="Qt.red"] { background-color: #dc2626; }
QPushButton[accent="Qt.red"]:hover { background-color: #b91c1c; }
QPushButton[accent="Qt.green"] { background-color: #16a34a; }
QPushButton[accent="Qt.green"]:hover { background-color: #15803d; }
QDateEdit, QComboBox {
    background-color: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 6px 8px; min-height: 22px;
}
QSplitter::handle { background-color: #e2e8f0; height: 4px; }
"""

_CARD_QSS = """
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
"""


class SupplierReportDialog(QDialog):
    def __init__(self, controller, supplier_id, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.supplier_id = supplier_id
        self.supplier = None
        self.history = []              # period-filtered Purchase ORM objects
        self._all_purchases = []       # all-time Purchase ORM objects (for payment links)
        self._purchase_row_by_number = {}  # purchase_number -> row index in purchases table
        self.setup_ui()
        self.load_report()
        self.showFullScreen()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        self.setWindowTitle("Supplier Purchase History Report")
        self.setStyleSheet(_STYLESHEET)
        self.setMinimumSize(900, 640)
        self.resize(1200, 800)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(12)

        # Header
        header_row = QHBoxLayout()
        self.header_label = QLabel()
        self.header_label.setStyleSheet("font-size: 18px; font-weight: 700; color: #0f172a;")
        self.header_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_row.addWidget(self.header_label, 1)

        export_btn = QPushButton("Export to CSV")
        export_btn.setMinimumHeight(36)
        export_btn.clicked.connect(self.export_csv)
        print_btn = QPushButton("🖨️ Print")
        print_btn.setProperty('accent', 'Qt.green')
        print_btn.setMinimumHeight(36)
        print_btn.clicked.connect(self.print_statement)
        header_row.addWidget(export_btn)
        header_row.addWidget(print_btn)
        layout.addLayout(header_row)

        # Period filter
        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Period:"))
        self.period_preset = QComboBox()
        self.period_preset.addItems(["Last 30 days", "Last 60 days", "Last 90 days", "All time"])
        self.period_preset.currentIndexChanged.connect(self._apply_period_preset)
        filter_row.addWidget(self.period_preset)
        filter_row.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addDays(-30))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        filter_row.addWidget(self.start_date)
        filter_row.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        filter_row.addWidget(self.end_date)
        filter_btn = QPushButton("🔍 Filter")
        filter_btn.clicked.connect(self.load_report)
        filter_row.addWidget(filter_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        # Summary row — horizontal, no groupbox, less clutter
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.total_purchases_card = self._make_summary_card("Total Purchases", "0", accent="blue")
        self.total_value_card = self._make_summary_card("Total Value", "Rs 0.00", accent="blue")
        self.total_paid_card = self._make_summary_card("Total Paid", "Rs 0.00", accent="green")
        self.total_outstanding_card = self._make_summary_card("Total Outstanding", "Rs 0.00", accent="red")
        for card in (self.total_purchases_card, self.total_value_card,
                     self.total_paid_card, self.total_outstanding_card):
            summary_row.addWidget(card, 1)
        layout.addLayout(summary_row)
        self.status_breakdown_label = QLabel()
        self.status_breakdown_label.setStyleSheet(
            "color: #475569; font-size: 12px; padding: 4px 2px;"
        )
        layout.addWidget(self.status_breakdown_label)

        # Two-pane splitter: Purchases (with inline items detail) + Payments
        splitter = QSplitter(Qt.Vertical)
        splitter.setChildrenCollapsible(False)

        # Purchases pane
        purchases_group = QGroupBox("Purchases")
        purchases_layout = QVBoxLayout(purchases_group)
        purchases_layout.setContentsMargins(10, 12, 10, 10)
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Purchase #", "Date", "Status", "Total", "Paid", "Outstanding"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        h = self.table.horizontalHeader()
        h.setSectionResizeMode(QHeaderView.Interactive)
        for col, w in ((0, 160), (1, 140), (2, 100), (3, 130), (4, 130), (5, 130)):
            self.table.setColumnWidth(col, w)
        self.table.itemSelectionChanged.connect(self.on_purchase_selected)
        purchases_layout.addWidget(self.table)

        # Items detail below the purchases table (compact, not a separate splitter pane)
        details_label = QLabel("Selected Purchase Items")
        details_label.setStyleSheet("font-weight: 700; font-size: 12px; margin-top: 6px;")
        purchases_layout.addWidget(details_label)
        self.items_table = QTableWidget()
        self.items_table.setColumnCount(5)
        self.items_table.setHorizontalHeaderLabels([
            "Product", "Ordered Qty", "Received Qty", "Unit Cost", "Total"
        ])
        self.items_table.setAlternatingRowColors(True)
        self.items_table.verticalHeader().setVisible(False)
        self.items_table.setEditTriggers(QTableWidget.NoEditTriggers)
        ih = self.items_table.horizontalHeader()
        ih.setSectionResizeMode(QHeaderView.Interactive)
        ih.setSectionResizeMode(0, QHeaderView.Stretch)
        for col, w in ((1, 100), (2, 110), (3, 120), (4, 130)):
            self.items_table.setColumnWidth(col, w)
        self.items_table.setMaximumHeight(160)
        purchases_layout.addWidget(self.items_table)
        splitter.addWidget(purchases_group)

        # Payments pane (only the payment table, no extra detail table)
        payments_group = QGroupBox("Payment History")
        pay_layout = QVBoxLayout(payments_group)
        pay_layout.setContentsMargins(10, 12, 10, 10)
        self.payments_table = QTableWidget()
        self.payments_table.setColumnCount(6)
        self.payments_table.setHorizontalHeaderLabels([
            "Date & Time", "Amount", "Method", "Reference", "Notes", "Purchase #"
        ])
        self.payments_table.setAlternatingRowColors(True)
        self.payments_table.verticalHeader().setVisible(False)
        self.payments_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.payments_table.setSelectionBehavior(QTableWidget.SelectRows)
        ph = self.payments_table.horizontalHeader()
        ph.setSectionResizeMode(QHeaderView.Interactive)
        ph.setSectionResizeMode(4, QHeaderView.Stretch)
        for col, w in ((0, 150), (1, 120), (2, 110), (3, 180), (5, 140)):
            self.payments_table.setColumnWidth(col, w)
        self.payments_table.itemClicked.connect(self._on_payment_selected)
        pay_layout.addWidget(self.payments_table)
        splitter.addWidget(payments_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([360, 240])
        layout.addWidget(splitter, 1)

        # Close
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setProperty('accent', 'Qt.red')
        close_btn.setMinimumHeight(38)
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    def _make_summary_card(self, title, value, accent="blue"):
        card = QFrame()
        card.setObjectName("card")
        accents = {
            "blue":  ("#eef2ff", "#c7d2fe", "#4338ca", "#1e3a8a"),
            "green": ("#ecfdf5", "#a7f3d0", "#047857", "#065f46"),
            "amber": ("#fffbeb", "#fde68a", "#b45309", "#92400e"),
            "red":   ("#fef2f2", "#fecaca", "#b91c1c", "#991b1b"),
        }
        bg, border, label_color, value_color = accents.get(accent, accents["blue"])
        card.setStyleSheet(
            f"QFrame#card {{ background-color: #ffffff; border: 1px solid {border}; "
            f"border-left: 4px solid {value_color}; border-radius: 10px; }}"
        )
        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 12, 14, 12)
        lay.setSpacing(4)
        t = QLabel(title)
        t.setStyleSheet(f"color: {label_color}; font-size: 11px; font-weight: 700; "
                        f"letter-spacing: 0.06em;")
        v = QLabel(value)
        v.setStyleSheet(f"color: {value_color}; font-size: 20px; font-weight: 800;")
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(t)
        lay.addWidget(v)
        card._value_label = v
        return card

    # ------------------------------------------------------------------ data
    def load_report(self):
        try:
            self.supplier = self.controller.session.get(Supplier, self.supplier_id)
            if not self.supplier:
                QMessageBox.critical(self, "Error", "Supplier not found")
                self.reject()
                return

            self.header_label.setText(f"Purchase History: {self.supplier.name}")

            # All purchases for this supplier (ORM objects, all-time).
            # Eager-load items + product so on_purchase_selected / export_csv /
            # _on_payment_selected don't trigger N+1 lazy loads.
            from pos_app.models.database import Purchase, PurchaseItem
            from sqlalchemy.orm import joinedload
            self._all_purchases = self.controller.session.query(Purchase).options(
                joinedload(Purchase.items).joinedload(PurchaseItem.product)
            ).filter(
                Purchase.supplier_id == self.supplier_id
            ).order_by(Purchase.order_date.desc()).all()

            # Apply period filter
            try:
                start_dt, end_dt = self._get_period_datetimes()
                self.history = [
                    p for p in self._all_purchases
                    if getattr(p, 'order_date', None) and start_dt <= p.order_date <= end_dt
                ]
            except Exception as e:
                print(f"[SupplierReport] Period filter error: {e}")
                self.history = list(self._all_purchases)

            # Summary
            total_purchases = len(self.history)
            total_value = sum(float(p.total_amount or 0) for p in self.history)
            total_paid = sum(float(p.paid_amount or 0) for p in self.history)
            total_outstanding = sum(
                max(0.0, float(p.total_amount or 0) - float(p.paid_amount or 0))
                for p in self.history
            )

            self.total_purchases_card._value_label.setText(str(total_purchases))
            self.total_value_card._value_label.setText(self._format_currency(total_value))
            self.total_paid_card._value_label.setText(self._format_currency(total_paid))
            self.total_outstanding_card._value_label.setText(self._format_currency(total_outstanding))
            self.total_outstanding_card._value_label.setStyleSheet(
                f"color: {'#dc2626' if total_outstanding > 0 else '#16a34a'}; "
                f"font-size: 18px; font-weight: 700;"
            )

            ordered = sum(1 for p in self.history if p.status == 'ORDERED')
            received = sum(1 for p in self.history if p.status == 'RECEIVED')
            partial = sum(1 for p in self.history if p.status == 'PARTIAL')
            self.status_breakdown_label.setText(
                f"Status breakdown — Ordered (pending): {ordered}   •   "
                f"Received (complete): {received}   •   Partial delivery: {partial}"
            )

            # Purchases table
            self._purchase_row_by_number = {}
            self.table.setRowCount(len(self.history))
            for i, purchase in enumerate(self.history):
                outstanding = max(0.0, float(purchase.total_amount or 0) - float(purchase.paid_amount or 0))
                pnum = getattr(purchase, 'purchase_number', None) or f"P-{purchase.id}"

                id_item = QTableWidgetItem(str(pnum))
                id_item.setData(Qt.UserRole, purchase)  # store the ORM object for selection
                self.table.setItem(i, 0, id_item)

                date_str = purchase.order_date.strftime('%Y-%m-%d %H:%M') if purchase.order_date else 'N/A'
                self.table.setItem(i, 1, QTableWidgetItem(date_str))

                status_item = QTableWidgetItem(purchase.status or 'UNKNOWN')
                if purchase.status == 'ORDERED':
                    status_item.setForeground(Qt.blue)
                elif purchase.status == 'RECEIVED':
                    status_item.setForeground(Qt.darkGreen)
                elif purchase.status == 'PARTIAL':
                    status_item.setForeground(Qt.darkYellow)
                self.table.setItem(i, 2, status_item)

                self.table.setItem(i, 3, QTableWidgetItem(self._format_currency(abs(float(purchase.total_amount or 0)))))
                self.table.setItem(i, 4, QTableWidgetItem(self._format_currency(abs(float(purchase.paid_amount or 0)))))

                out_item = QTableWidgetItem(self._format_currency(outstanding))
                out_item.setForeground(Qt.red if outstanding > 0 else Qt.darkGreen)
                self.table.setItem(i, 5, out_item)

                self._purchase_row_by_number[str(pnum)] = i

            self.load_payment_history()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load report: {str(e)}")
            import traceback
            traceback.print_exc()

    def load_payment_history(self):
        """Load payment history for the supplier in ONE query (was N+1)."""
        try:
            from pos_app.models.database import PurchasePayment

            start_dt, end_dt = self._get_period_datetimes()
            payments = self.controller.session.query(PurchasePayment).filter(
                PurchasePayment.supplier_id == self.supplier_id,
                PurchasePayment.payment_date >= start_dt,
                PurchasePayment.payment_date <= end_dt
            ).order_by(PurchasePayment.payment_date.desc()).all()

            # Map purchase_id -> purchase_number from already-loaded purchases
            pnum_by_id = {}
            for p in self._all_purchases:
                pnum_by_id[p.id] = getattr(p, 'purchase_number', None) or f"P-{p.id}"

            self.payments_table.setRowCount(len(payments))
            for row, payment in enumerate(payments):
                date_time_str = payment.payment_date.strftime('%Y-%m-%d %H:%M:%S') if payment.payment_date else 'N/A'
                self.payments_table.setItem(row, 0, QTableWidgetItem(date_time_str))

                amount_val = abs(float(getattr(payment, 'amount', 0.0) or 0.0))
                self.payments_table.setItem(row, 1, QTableWidgetItem(self._format_currency(amount_val)))

                self.payments_table.setItem(row, 2, QTableWidgetItem(payment.payment_method or 'N/A'))

                reference_item = QTableWidgetItem(payment.reference or '-')
                reference_item.setForeground(Qt.blue)
                self.payments_table.setItem(row, 3, reference_item)

                self.payments_table.setItem(row, 4, QTableWidgetItem(payment.notes or '-'))

                pnum = pnum_by_id.get(payment.purchase_id, 'N/A')
                purchase_item = QTableWidgetItem(str(pnum))
                if pnum != 'N/A':
                    purchase_item.setForeground(Qt.blue)
                    purchase_item.setData(Qt.UserRole, str(pnum))
                    reference_item.setData(Qt.UserRole, str(pnum))
                self.payments_table.setItem(row, 5, purchase_item)

        except Exception as e:
            print(f"Error loading payment history: {e}")
            self.payments_table.setRowCount(0)

    def on_purchase_selected(self):
        """Show items for the selected purchase using the ORM relationship."""
        try:
            selected_rows = self.table.selectionModel().selectedRows()
            if not selected_rows:
                self.items_table.setRowCount(0)
                return
            row = selected_rows[0].row()
            id_item = self.table.item(row, 0)
            if not id_item:
                self.items_table.setRowCount(0)
                return
            purchase = id_item.data(Qt.UserRole)
            if purchase is None:
                self.items_table.setRowCount(0)
                return
            self._populate_items_table(self.items_table, purchase)
        except Exception as e:
            print(f"Error loading purchase items: {e}")
            self.items_table.setRowCount(0)

    def _populate_items_table(self, table, purchase, for_payment=False):
        """Fill a 5-column items table from a Purchase ORM object's items.

        The two consumer tables have DIFFERENT column layouts, so `for_payment`
        selects which mapping to use:
          items_table       -> Product | Ordered Qty | Received Qty | Unit Cost | Total
          payment_items_table -> Product | SKU | Quantity | Unit Price | Total
        """
        table.setRowCount(0)
        items = list(getattr(purchase, 'items', []) or [])
        table.setRowCount(len(items))
        for i, it in enumerate(items):
            product = getattr(it, 'product', None)
            product_name = product.name if product else f"Product #{it.product_id}"
            table.setItem(i, 0, QTableWidgetItem(product_name))

            qty = float(it.quantity or 0)
            recv = float(getattr(it, 'received_quantity', 0) or 0)
            unit_cost = float(getattr(it, 'unit_cost', 0) or 0)
            total_cost = float(getattr(it, 'total_cost', 0) or (qty * unit_cost))

            if for_payment:
                sku = product.sku if product else ""
                table.setItem(i, 1, QTableWidgetItem(str(sku)))
                table.setItem(i, 2, QTableWidgetItem(str(qty)))
                table.setItem(i, 3, QTableWidgetItem(self._format_currency(unit_cost)))
                table.setItem(i, 4, QTableWidgetItem(self._format_currency(total_cost)))
            else:
                table.setItem(i, 1, QTableWidgetItem(str(qty)))
                table.setItem(i, 2, QTableWidgetItem(str(recv)))
                table.setItem(i, 3, QTableWidgetItem(self._format_currency(unit_cost)))
                table.setItem(i, 4, QTableWidgetItem(self._format_currency(total_cost)))

    def _on_payment_selected(self, item):
        """Highlight the purchase that this payment was applied to."""
        try:
            row = self.payments_table.row(item)
            pnum_item = self.payments_table.item(row, 5)
            if not pnum_item:
                return
            purchase_number = pnum_item.text()

            # Highlight the matching purchase row (triggers on_purchase_selected)
            target_row = self._purchase_row_by_number.get(str(purchase_number))
            if target_row is not None:
                self.table.selectRow(int(target_row))
        except Exception as e:
            print(f"Error selecting payment purchase: {e}")

    def export_csv(self):
        """Export report to CSV using ORM attribute access (was broken on dicts)."""
        try:
            import csv
            from datetime import datetime
            import os

            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_name = (self.supplier.name or 'supplier').replace(' ', '_')
            filename = f"supplier_report_{safe_name}_{timestamp}.csv"
            filepath = os.path.join("exports", filename)
            os.makedirs("exports", exist_ok=True)

            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([f"Supplier Purchase History Report - {self.supplier.name}"])
                writer.writerow([f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([])
                writer.writerow([
                    'Purchase #', 'Date', 'Status', 'Product',
                    'Ordered Qty', 'Received Qty', 'Unit Cost', 'Total'
                ])
                for purchase in self.history:
                    pnum = getattr(purchase, 'purchase_number', None) or f"P-{purchase.id}"
                    date_str = purchase.order_date.strftime('%Y-%m-%d %H:%M') if purchase.order_date else 'N/A'
                    items = list(getattr(purchase, 'items', []) or [])
                    if not items:
                        writer.writerow([pnum, date_str, purchase.status or 'UNKNOWN',
                                         '(no items)', '', '', '', ''])
                        continue
                    for it in items:
                        product = getattr(it, 'product', None)
                        pname = product.name if product else f"Product #{it.product_id}"
                        qty = float(it.quantity or 0)
                        recv = float(getattr(it, 'received_quantity', 0) or 0)
                        unit_cost = float(getattr(it, 'unit_cost', 0) or 0)
                        total_cost = float(getattr(it, 'total_cost', 0) or (qty * unit_cost))
                        writer.writerow([pnum, date_str, purchase.status or 'UNKNOWN',
                                         pname, qty, recv, f"{unit_cost:.2f}", f"{total_cost:.2f}"])

            QMessageBox.information(self, "Export Successful", f"Report exported to:\n{filepath}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Failed to export report: {str(e)}")

    # ------------------------------------------------------------------ helpers
    def _apply_period_preset(self):
        try:
            text = self.period_preset.currentText()
            end = QDate.currentDate()
            if text == "Last 30 days":
                start = end.addDays(-30)
            elif text == "Last 60 days":
                start = end.addDays(-60)
            elif text == "Last 90 days":
                start = end.addDays(-90)
            else:  # All time
                start = QDate(2000, 1, 1)
            self.start_date.setDate(start)
            self.end_date.setDate(end)
            self.load_report()
        except Exception as e:
            print(f"[SupplierReport] Error applying period preset: {e}")

    def _get_period_datetimes(self):
        from datetime import datetime, time
        try:
            sd = self.start_date.date().toPython()
        except AttributeError:
            sd = datetime.strptime(self.start_date.date().toString("yyyy-MM-dd"), "%Y-%m-%d").date()
        try:
            ed = self.end_date.date().toPython()
        except AttributeError:
            ed = datetime.strptime(self.end_date.date().toString("yyyy-MM-dd"), "%Y-%m-%d").date()
        return datetime.combine(sd, time.min), datetime.combine(ed, time.max)

    def _format_currency(self, value):
        try:
            return f"Rs {float(value):,.2f}"
        except Exception:
            return f"Rs {value}"

    def _get_shop_info(self):
        try:
            try:
                from PySide6.QtCore import QSettings
            except ImportError:
                from PyQt6.QtCore import QSettings
            settings = QSettings()
            return {
                'name': settings.value("business_name", "Sarhad General Store"),
                'address': settings.value("business_address", "Madni Chowk"),
                'phone': settings.value("business_phone", "+923225031977"),
            }
        except Exception:
            return {'name': "Your Shop Name", 'address': "Your Address", 'phone': "Your Phone"}

    # ------------------------------------------------------------------ print
    def print_statement(self):
        try:
            try:
                from PySide6.QtPrintSupport import QPrinter, QPrintDialog
                from PySide6.QtGui import QPageSize, QPageLayout
            except ImportError:
                from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
                from PyQt6.QtGui import QPageSize, QPageLayout

            printer = QPrinter()
            printer.setPageSize(QPageSize(QPageSize.Legal))
            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

            dialog = QPrintDialog(printer, self)
            dialog.setWindowTitle("Print Supplier Statement")
            if dialog.exec() != QPrintDialog.Accepted:
                return

            html_content = self._build_statement_html()
            self._print_html_document(printer, html_content)
        except Exception as e:
            QMessageBox.critical(self, "Print Failed", f"Failed to print statement: {str(e)}")
            import traceback
            traceback.print_exc()

    def _print_html_document(self, printer, html_content):
        try:
            from PySide6.QtGui import QTextDocument, QFont
            from PySide6.QtCore import QSizeF
        except ImportError:
            from PyQt6.QtGui import QTextDocument, QFont
            from PyQt6.QtCore import QSizeF

        document = QTextDocument()
        document.setDocumentMargin(24)
        document.setDefaultFont(QFont("Segoe UI", 12))
        document.setHtml(html_content)
        try:
            page_layout = printer.pageLayout()
            paint_rect = page_layout.paintRectPixels(printer.resolution())
            document.setPageSize(QSizeF(paint_rect.width(), paint_rect.height()))
        except Exception as e:
            print(f"[SupplierReport] Error setting page size: {e}")
            document.setPageSize(QSizeF(printer.width(), printer.height()))
        if hasattr(document, "print"):
            document.print(printer)
        else:
            document.print_(printer)

    def _build_statement_html(self):
        """Build an advanced bank-statement-style HTML for the supplier over the selected period."""
        import html as _html
        from datetime import datetime
        from pos_app.models.database import Purchase, PurchasePayment, PurchaseItem, Product

        def esc(v):
            return _html.escape(str(v) if v is not None else "")

        start_dt, end_dt = self._get_period_datetimes()
        session = self.controller.session
        supplier = self.supplier

        all_purchases = session.query(Purchase).filter(Purchase.supplier_id == self.supplier_id).all()
        closing_outstanding = sum(
            (float(getattr(p, 'total_amount', 0) or 0) - float(getattr(p, 'paid_amount', 0) or 0))
            for p in all_purchases
        )

        period_purchases = session.query(Purchase).filter(
            Purchase.supplier_id == self.supplier_id,
            Purchase.order_date >= start_dt,
            Purchase.order_date <= end_dt
        ).order_by(Purchase.order_date.asc(), Purchase.id.asc()).all()

        period_payments = session.query(PurchasePayment).filter(
            PurchasePayment.supplier_id == self.supplier_id,
            PurchasePayment.payment_date >= start_dt,
            PurchasePayment.payment_date <= end_dt
        ).order_by(PurchasePayment.payment_date.asc(), PurchasePayment.id.asc()).all()

        transactions = []
        total_purchases = 0.0
        for p in period_purchases:
            date_txt = p.order_date.strftime('%Y-%m-%d') if p.order_date else ''
            pnum = getattr(p, 'purchase_number', '') or f"P-{p.id}"
            total_purchases += float(getattr(p, 'total_amount', 0) or 0)
            items = session.query(PurchaseItem).filter(PurchaseItem.purchase_id == p.id).all()
            if items:
                for it in items:
                    prod = session.query(Product).filter(Product.id == it.product_id).first()
                    pname = prod.name if prod else f"Product #{it.product_id}"
                    qty = float(getattr(it, 'quantity', 0) or 0)
                    unit_cost = float(getattr(it, 'unit_cost', 0) or 0)
                    line_total = float(getattr(it, 'total_cost', (qty * unit_cost)) or (qty * unit_cost))
                    transactions.append({
                        'date': date_txt, 'type': 'Purchase', 'ref': pnum, 'method': '—',
                        'description': f"{pname} (Qty {qty} @ {self._format_currency(unit_cost)})",
                        'debit': line_total, 'credit': 0.0,
                    })
            else:
                transactions.append({
                    'date': date_txt, 'type': 'Purchase', 'ref': pnum, 'method': '—',
                    'description': 'Purchase', 'debit': float(getattr(p, 'total_amount', 0) or 0), 'credit': 0.0,
                })

        total_payments = 0.0
        for pay in period_payments:
            date_txt = pay.payment_date.strftime('%Y-%m-%d') if pay.payment_date else ''
            amt = float(getattr(pay, 'amount', 0) or 0)
            total_payments += amt
            transactions.append({
                'date': date_txt, 'type': 'Payment',
                'ref': getattr(pay, 'reference', '') or '—',
                'method': getattr(pay, 'payment_method', '') or '—',
                'description': 'Payment Made', 'debit': 0.0, 'credit': amt,
            })

        transactions.sort(key=lambda x: (x['date'] or ''))
        total_debit = sum(t['debit'] for t in transactions)
        total_credit = sum(t['credit'] for t in transactions)
        opening = closing_outstanding - (total_debit - total_credit)
        running = opening
        for t in transactions:
            running += t['debit'] - t['credit']
            t['balance'] = running

        if not transactions:
            rows_html = "<tr><td colspan='7' class='empty'>No transactions found for the selected period.</td></tr>"
        else:
            rows_html = ""
            for t in transactions:
                d = self._format_currency(t['debit']) if t['debit'] > 0 else ''
                c = self._format_currency(t['credit']) if t['credit'] > 0 else ''
                rows_html += (
                    "<tr>"
                    f"<td>{esc(t['date'])}</td>"
                    f"<td class='desc'>{esc(t['description'])}</td>"
                    f"<td>{esc(t['ref'])}</td>"
                    f"<td>{esc(t['method'])}</td>"
                    f"<td class='numeric'>{esc(d)}</td>"
                    f"<td class='numeric'>{esc(c)}</td>"
                    f"<td class='numeric'>{self._format_currency(t['balance'])}</td>"
                    "</tr>"
                )

        shop = self._get_shop_info()
        period_text = f"{start_dt.strftime('%Y-%m-%d')} to {end_dt.strftime('%Y-%m-%d')}"
        generated = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        supplier_name = supplier.name if supplier else ''
        supplier_contact = getattr(supplier, 'contact', '') or ''
        supplier_email = getattr(supplier, 'email', '') or ''
        supplier_address = getattr(supplier, 'address', '') or ''

        # Compact, Qt-safe layout.  QTextDocument is not a browser, so we use
        # plain HTML tables with explicit <col> widths and avoid flex/inline-block.
        opening_val = self._format_currency(opening)
        purchases_val = self._format_currency(total_purchases)
        payments_val = self._format_currency(total_payments)
        closing_val = self._format_currency(closing_outstanding)

        html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8" />
<style>
    @page {{ margin: 12mm; }}
    body {{
        font-family: Arial, 'Helvetica Neue', sans-serif;
        font-size: 10pt; line-height: 1.35; color: #000; background: #fff;
        margin: 0; padding: 0;
    }}
    .center {{ text-align: center; }}
    .shop {{ font-size: 16pt; font-weight: bold; }}
    .shop-meta {{ font-size: 9pt; color: #333; margin-top: 2pt; }}
    .title {{
        font-size: 12pt; font-weight: bold; margin: 8pt 0 6pt 0;
        border-bottom: 1pt solid #000; padding-bottom: 4pt;
    }}
    .info-table {{ width: 100%; margin-bottom: 8pt; }}
    .info-table td {{ vertical-align: top; font-size: 9pt; padding: 2pt 0; }}
    .label {{ font-weight: bold; color: #333; }}
    .summary-table {{
        width: 100%; border-collapse: collapse; margin-bottom: 6pt;
        border: 1pt solid #999; table-layout: fixed;
    }}
    .summary-table td {{
        width: 25%; padding: 6pt 4pt; text-align: center;
        border: 1pt solid #ccc; vertical-align: top; background-color: #f9fafb;
    }}
    .summary-table .slabel {{ font-size: 7pt; color: #555; }}
    .summary-table .sval {{ font-size: 11pt; font-weight: bold; }}
    .due {{ color: #c00000; }}
    table.txn {{
        width: 100%; border-collapse: collapse; table-layout: fixed;
        font-size: 9pt; border: 1pt solid #999;
    }}
    table.txn th, table.txn td {{
        padding: 5pt 4pt; border: 0.5pt solid #999; vertical-align: top;
    }}
    table.txn th {{
        background-color: #eeeeee; font-weight: bold; text-align: center;
    }}
    table.txn td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    table.txn td.desc {{ text-align: left; }}
    table.txn tfoot td {{ border-top: 1pt solid #000; font-weight: bold; }}
    .empty {{ text-align: center; padding: 12pt 0; color: #666; }}
    .footer {{
        margin-top: 12pt; text-align: center; font-size: 8pt; color: #666;
    }}
</style></head>
<body>
    <div class="center">
        <div class="shop">{esc(shop['name'])}</div>
        <div class="shop-meta">{esc(shop['address'])} &nbsp;|&nbsp; {esc(shop['phone'])}</div>
        <div class="title">SUPPLIER STATEMENT</div>
    </div>

    <table class="info-table">
        <tr>
            <td style="width:55%;">
                <span class="label">Supplier:</span> {esc(supplier_name)}<br>
                {esc(supplier_contact)} &nbsp; {esc(supplier_email)}<br>
                {esc(supplier_address)}
            </td>
            <td style="width:45%; text-align:right;">
                <span class="label">Period:</span> {esc(period_text)}<br>
                <span class="label">Generated:</span> {esc(generated)}
            </td>
        </tr>
    </table>

    <table class="summary-table">
        <tr>
            <td><div class="slabel">OPENING OUTSTANDING</div><div class="sval">{esc(opening_val)}</div></td>
            <td><div class="slabel">TOTAL PURCHASES</div><div class="sval">{esc(purchases_val)}</div></td>
            <td><div class="slabel">TOTAL PAYMENTS</div><div class="sval">{esc(payments_val)}</div></td>
            <td><div class="slabel">CLOSING OUTSTANDING</div><div class="sval due">{esc(closing_val)}</div></td>
        </tr>
    </table>

    <table class="txn">
        <colgroup>
            <col width="12%">
            <col width="28%">
            <col width="17%">
            <col width="14%">
            <col width="12%">
            <col width="12%">
            <col width="13%">
        </colgroup>
        <thead>
            <tr>
                <th>Date</th>
                <th>Description</th>
                <th>Ref / Purchase #</th>
                <th>Method</th>
                <th>Debit</th>
                <th>Credit</th>
                <th>Balance</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
        <tfoot>
            <tr>
                <td colspan="6" style="text-align:right;">CLOSING OUTSTANDING:</td>
                <td class="num due">{esc(closing_val)}</td>
            </tr>
        </tfoot>
    </table>

    <div class="footer">Generated on {esc(generated)}</div>
</body></html>"""
        return html_content
