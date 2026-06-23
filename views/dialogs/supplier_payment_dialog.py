"""
Supplier Payment Dialog for recording payments to suppliers
"""
try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QMessageBox,
        QTextEdit, QDateEdit, QGroupBox, QTableWidget, QTableWidgetItem,
        QHeaderView, QFrame, QSizePolicy, QGridLayout
    )
    from PySide6.QtCore import Qt, QDate
except ImportError:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFormLayout, QLineEdit, QComboBox, QDoubleSpinBox, QMessageBox,
        QTextEdit, QDateEdit, QGroupBox, QTableWidget, QTableWidgetItem,
        QHeaderView, QFrame, QSizePolicy, QGridLayout
    )
    from PyQt6.QtCore import Qt, QDate
from pos_app.models.database import PaymentMethod, Purchase
from pos_app.utils.logger import app_logger


_STYLESHEET = """
QDialog { background-color: #f4f6fb; }
QLabel { color: #1e293b; }
QFrame#card {
    background-color: #ffffff; border: 1px solid #e2e8f0;
    border-radius: 12px;
}
QFrame#cardDue {
    background-color: #fef2f2; border: 1px solid #fecaca;
    border-left: 4px solid #dc2626; border-radius: 10px;
}
QLabel#cardTitle {
    color: #64748b; font-size: 11px; font-weight: 700;
    letter-spacing: 0.08em; padding: 2px 0;
}
QLabel#fieldLabel { color: #475569; font-size: 12px; font-weight: 600; }
QLabel#title { font-size: 20px; font-weight: 800; color: #0f172a; }
QLabel#subtitle { color: #64748b; font-size: 12px; }
QLabel#dueValue { color: #dc2626; font-size: 22px; font-weight: 800; }
QLabel#dueCaption { color: #b91c1c; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; }
QTableWidget {
    background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px;
    gridline-color: #cbd5e1; selection-background-color: #dbeafe;
    selection-color: #0f172a; alternate-background-color: #f1f5f9; font-size: 13px;
}
QTableWidget::item { padding: 6px 6px; border: none; color: #0f172a; }
QTableWidget::item:selected { background-color: #dbeafe; color: #0f172a; }
QHeaderView::section {
    background-color: #1e293b; color: #ffffff; padding: 8px 8px;
    border: none; font-weight: 700; font-size: 12px;
}
QPushButton {
    background-color: #2563eb; color: white; border: none;
    padding: 9px 18px; border-radius: 8px; font-weight: 600; font-size: 13px;
}
QPushButton:hover { background-color: #1d4ed8; }
QPushButton:pressed { background-color: #1e40af; }
QPushButton[accent="Qt.red"] { background-color: #dc2626; }
QPushButton[accent="Qt.red"]:hover { background-color: #b91c1c; }
QPushButton[accent="Qt.green"] { background-color: #16a34a; }
QPushButton[accent="Qt.green"]:hover { background-color: #15803d; }
QDoubleSpinBox, QComboBox, QLineEdit, QDateEdit {
    background-color: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 7px 8px; min-height: 22px; font-size: 13px;
}
QDoubleSpinBox:focus, QComboBox:focus, QLineEdit:focus, QDateEdit:focus {
    border: 1px solid #2563eb;
}
QTextEdit {
    background-color: #ffffff; border: 1px solid #cbd5e1;
    border-radius: 6px; padding: 6px; font-size: 13px;
}
"""


class SupplierPaymentDialog(QDialog):
    def __init__(self, controllers, supplier_id, parent=None):
        super().__init__(parent)
        self.controllers = controllers
        self.supplier_id = supplier_id
        self.payment_id = None
        self.setup_ui()
        self.load_supplier_data()
        self.load_outstanding_purchases()
        self.showFullScreen()

    def setup_ui(self):
        self.setWindowTitle("💰 Pay Supplier")
        self.setStyleSheet(_STYLESHEET)
        self.setMinimumSize(560, 680)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        # Header
        title = QLabel("💰 Pay Supplier")
        title.setObjectName("title")
        subtitle = QLabel("Record a payment to this supplier")
        subtitle.setObjectName("subtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        # Supplier info card
        info_card = QFrame()
        info_card.setObjectName("card")
        info_lay = QVBoxLayout(info_card)
        info_lay.setContentsMargins(16, 14, 16, 14)
        info_lay.setSpacing(8)
        info_title = QLabel("SUPPLIER")
        info_title.setObjectName("cardTitle")
        info_lay.addWidget(info_title)
        info_grid = QGridLayout()
        info_grid.setHorizontalSpacing(16)
        info_grid.setVerticalSpacing(6)
        self.supplier_name_label = QLabel("—")
        self.supplier_contact_label = QLabel("—")
        self.supplier_email_label = QLabel("—")
        def _field(text):
            lbl = QLabel(text)
            lbl.setObjectName("fieldLabel")
            return lbl
        info_grid.addWidget(_field("Name"), 0, 0)
        info_grid.addWidget(self.supplier_name_label, 0, 1)
        info_grid.addWidget(_field("Contact"), 1, 0)
        info_grid.addWidget(self.supplier_contact_label, 1, 1)
        info_grid.addWidget(_field("Email"), 2, 0)
        info_grid.addWidget(self.supplier_email_label, 2, 1)
        info_grid.setColumnStretch(1, 1)
        info_lay.addLayout(info_grid)
        layout.addWidget(info_card)

        # Outstanding amount — prominent due card
        due_card = QFrame()
        due_card.setObjectName("cardDue")
        due_lay = QHBoxLayout(due_card)
        due_lay.setContentsMargins(16, 12, 16, 12)
        due_left = QVBoxLayout()
        due_left.setSpacing(2)
        due_caption = QLabel("OUTSTANDING AMOUNT")
        due_caption.setObjectName("dueCaption")
        due_left.addWidget(due_caption)
        due_left.addStretch()
        due_lay.addLayout(due_left)
        due_lay.addStretch()
        self.outstanding_label = QLabel("Rs 0.00")
        self.outstanding_label.setObjectName("dueValue")
        self.outstanding_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        due_lay.addWidget(self.outstanding_label)
        layout.addWidget(due_card)

        # Payment details card
        pay_card = QFrame()
        pay_card.setObjectName("card")
        pay_lay = QVBoxLayout(pay_card)
        pay_lay.setContentsMargins(16, 14, 16, 14)
        pay_lay.setSpacing(10)
        pay_title = QLabel("PAYMENT DETAILS")
        pay_title.setObjectName("cardTitle")
        pay_lay.addWidget(pay_title)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft)
        form.setHorizontalSpacing(14)
        form.setVerticalSpacing(10)

        self.amount_input = QDoubleSpinBox()
        self.amount_input.setMaximum(1000000.0)
        self.amount_input.setDecimals(2)
        self.amount_input.setPrefix("Rs ")

        self.payment_method_combo = QComboBox()
        self.payment_method_combo.addItems(["Cash", "Bank Transfer", "Check", "Credit Card"])

        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText("Payment reference (optional)")

        self.notes_input = QTextEdit()
        self.notes_input.setMaximumHeight(70)
        self.notes_input.setPlaceholderText("Payment notes (optional)")

        self.payment_date_input = QDateEdit()
        self.payment_date_input.setDate(QDate.currentDate())
        self.payment_date_input.setCalendarPopup(True)
        self.payment_date_input.setDisplayFormat("yyyy-MM-dd")

        form.addRow(_field("Amount"), self.amount_input)
        form.addRow(_field("Payment Method"), self.payment_method_combo)
        form.addRow(_field("Reference"), self.reference_input)
        form.addRow(_field("Date"), self.payment_date_input)
        form.addRow(_field("Notes"), self.notes_input)
        pay_lay.addLayout(form)
        layout.addWidget(pay_card)

        # Outstanding purchases card — real table, not a text blob
        pur_card = QFrame()
        pur_card.setObjectName("card")
        pur_lay = QVBoxLayout(pur_card)
        pur_lay.setContentsMargins(16, 14, 16, 14)
        pur_lay.setSpacing(8)
        pur_title = QLabel("OUTSTANDING PURCHASES")
        pur_title.setObjectName("cardTitle")
        pur_lay.addWidget(pur_title)
        self.purchases_list = QTableWidget()
        self.purchases_list.setColumnCount(5)
        self.purchases_list.setHorizontalHeaderLabels(
            ["Purchase #", "Date", "Total", "Paid", "Outstanding"]
        )
        self.purchases_list.setAlternatingRowColors(True)
        self.purchases_list.verticalHeader().setVisible(False)
        self.purchases_list.setEditTriggers(QTableWidget.NoEditTriggers)
        self.purchases_list.setSelectionBehavior(QTableWidget.SelectRows)
        ph = self.purchases_list.horizontalHeader()
        ph.setSectionResizeMode(QHeaderView.Stretch)
        self.purchases_list.setMinimumHeight(160)
        self.purchases_list.setMaximumHeight(220)
        pur_lay.addWidget(self.purchases_list)
        layout.addWidget(pur_card, 1)

        # Buttons
        buttons_layout = QHBoxLayout()
        self.pay_button = QPushButton("💰 Record Payment")
        self.pay_button.setMinimumHeight(42)
        self.pay_button.setProperty('accent', 'Qt.green')
        self.pay_button.clicked.connect(self.record_payment)
        cancel_button = QPushButton("❌ Cancel")
        cancel_button.setMinimumHeight(42)
        cancel_button.setProperty('accent', 'Qt.red')
        cancel_button.clicked.connect(self.reject)
        buttons_layout.addStretch()
        buttons_layout.addWidget(cancel_button)
        buttons_layout.addWidget(self.pay_button)
        layout.addLayout(buttons_layout)

    def load_supplier_data(self):
        """Load supplier information"""
        try:
            # Use PostgreSQL models
            from pos_app.models.database import Supplier
            supplier = self.controllers['inventory'].session.get(Supplier, self.supplier_id)
            if supplier:
                self.supplier_name_label.setText(supplier.name or "")
                self.supplier_contact_label.setText(supplier.contact or "")
                self.supplier_email_label.setText(supplier.email or "")
            else:
                QMessageBox.warning(self, "Error", "Supplier not found")
                self.reject()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load supplier data: {str(e)}")

    def load_outstanding_purchases(self):
        """Load outstanding purchases for this supplier into the table."""
        try:
            # Use PostgreSQL models
            from pos_app.models.database import Purchase
            try:
                from PySide6.QtGui import QColor
            except ImportError:
                from PyQt6.QtGui import QColor
            red = QColor("#dc2626")
            gray = QColor("#94a3b8")

            purchases = self.controllers['inventory'].session.query(Purchase).filter(
                Purchase.supplier_id == self.supplier_id,
                (Purchase.total_amount - Purchase.paid_amount) > 0
            ).all()

            self.purchases_list.setRowCount(0)
            total_outstanding = 0.0
            if purchases:
                self.purchases_list.setRowCount(len(purchases))
                for row, purchase in enumerate(purchases):
                    total = float(purchase.total_amount or 0)
                    paid = float(purchase.paid_amount or 0)
                    outstanding = total - paid
                    total_outstanding += outstanding
                    pnum = getattr(purchase, 'purchase_number', None) or f"#{purchase.id}"
                    odate = getattr(purchase, 'order_date', None)
                    odate_txt = odate.strftime('%Y-%m-%d') if odate else '—'
                    cells = [
                        str(pnum), odate_txt,
                        f"Rs {total:,.2f}", f"Rs {paid:,.2f}", f"Rs {outstanding:,.2f}",
                    ]
                    for col, txt in enumerate(cells):
                        item = QTableWidgetItem(txt)
                        item.setTextAlignment(Qt.AlignCenter)
                        if col == 4 and outstanding > 0:
                            item.setForeground(red)
                        self.purchases_list.setItem(row, col, item)
            else:
                self.purchases_list.setRowCount(1)
                self.purchases_list.setSpan(0, 0, 1, 5)
                empty = QTableWidgetItem("No outstanding purchases")
                empty.setTextAlignment(Qt.AlignCenter)
                empty.setForeground(gray)
                self.purchases_list.setItem(0, 0, empty)

            self.outstanding_label.setText(f"Rs {total_outstanding:,.2f}")
            # Set default amount to total outstanding
            if total_outstanding > 0:
                self.amount_input.setValue(total_outstanding)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to load purchases: {str(e)}")

    def record_payment(self):
        """Record the supplier payment"""
        try:
            amount = float(self.amount_input.value())
            if amount <= 0:
                QMessageBox.warning(self, "Validation", "Please enter a valid amount greater than 0.")
                return

            # Convert amount to Decimal for precise calculations
            from decimal import Decimal
            amount = Decimal(str(amount))

            payment_method = self.payment_method_combo.currentText()
            reference = self.reference_input.text().strip()
            notes = self.notes_input.toPlainText().strip()
            payment_date = self.payment_date_input.date().toPython()

            # Map payment method to enum
            method_map = {
                "Cash": PaymentMethod.CASH,
                "Bank Transfer": PaymentMethod.BANK_TRANSFER,
                "Check": PaymentMethod.BANK_TRANSFER,  # Treat check as bank transfer
                "Credit Card": PaymentMethod.CREDIT_CARD
            }
            payment_method_enum = method_map.get(payment_method, PaymentMethod.CASH)

            # Apply payment to outstanding purchases
            from pos_app.models.database import Purchase
            outstanding_purchases = self.controllers['inventory'].session.query(Purchase).filter(
                Purchase.supplier_id == self.supplier_id,
                (Purchase.total_amount - Purchase.paid_amount) > 0
            ).order_by(Purchase.order_date).all()
            
            remaining_payment = amount
            payments_applied = []
            
            for purchase in outstanding_purchases:
                if remaining_payment <= 0:
                    break
                
                outstanding = (purchase.total_amount or 0) - (purchase.paid_amount or 0)
                payment_for_this = min(remaining_payment, outstanding)
                # Ensure payment_for_this is always a Decimal
                from decimal import Decimal
                if not isinstance(payment_for_this, Decimal):
                    payment_for_this = Decimal(str(payment_for_this))
                
                # Record purchase payment
                try:
                    pp = self.controllers['inventory'].record_purchase_payment(
                        purchase_id=purchase.id,
                        supplier_id=self.supplier_id,
                        amount=payment_for_this,
                        payment_method=payment_method_enum.value,
                        reference=reference,
                        notes=notes,
                        payment_date=payment_date
                    )
                    payments_applied.append(f"Purchase #{purchase.purchase_number}: Rs {payment_for_this:.2f}")
                    remaining_payment -= payment_for_this
                except Exception as e:
                    print(f"Error applying payment to purchase {purchase.id}: {e}")
            
            # Update outstanding purchases display
            self.load_outstanding_purchases()
            
            # Show success message with details
            if payments_applied:
                details = "\n".join(payments_applied)
                message = f"Payment of Rs {amount:.2f} applied to:\n\n{details}"
                if remaining_payment > 0:
                    message += f"\n\nRemaining Rs {remaining_payment:.2f} (no outstanding purchases to apply to)"
            else:
                message = f"Payment of Rs {amount:.2f} recorded, but no outstanding purchases found."

            QMessageBox.information(
                self,
                "Success",
                message
            )

            # Ask if user wants to make another payment
            reply = QMessageBox.question(
                self,
                "Another Payment?",
                "Would you like to make another payment to this supplier?",
                QMessageBox.Yes | QMessageBox.No
            )

            if reply == QMessageBox.No:
                self.accept()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to record payment: {str(e)}")
            app_logger.exception("Error recording supplier payment")

    def keyPressEvent(self, event):
        """Handle keyboard navigation in the payment dialog"""
        try:
            from PySide6.QtCore import Qt
        except ImportError:
            from PyQt6.QtCore import Qt
        
        # Allow normal arrow key navigation
        if event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            # Let arrow keys work normally for form navigation
            super().keyPressEvent(event)
            return
        
        # Handle Enter key to record payment
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            # Find which widget has focus and handle appropriately
            focused_widget = self.focusWidget()
            if focused_widget == self.pay_button:
                self.record_payment()
                return
            else:
                # Default Enter behavior - move to next field
                super().keyPressEvent(event)
                return
        
        # Default handling for all other keys
        super().keyPressEvent(event)
