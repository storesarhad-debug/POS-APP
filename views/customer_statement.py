import os
import html

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTableWidget, QTableWidgetItem, QComboBox, QDateEdit,
        QFrame, QMessageBox, QGroupBox, QGridLayout, QHeaderView,
        QAbstractItemView, QScrollArea, QWidget, QSizePolicy
    )
    from PySide6.QtPrintSupport import QPrinter, QPrintDialog
    from PySide6.QtGui import QFont, QColor, QPageSize, QPageLayout, QTextDocument
    from PySide6.QtCore import Qt, QDate, QSizeF, QMarginsF
    qt_version = "PySide6"
except ImportError:
    try:
        from PyQt6.QtWidgets import (
            QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
            QTableWidget, QTableWidgetItem, QComboBox, QDateEdit,
            QFrame, QMessageBox, QGroupBox, QGridLayout, QHeaderView,
            QAbstractItemView, QScrollArea, QWidget, QSizePolicy
        )
        from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
        from PyQt6.QtGui import QFont, QColor, QPageSize, QPageLayout, QTextDocument
        from PyQt6.QtCore import Qt, QDate, QSizeF, QMarginsF
        qt_version = "PyQt6"
    except ImportError:
        raise ImportError("Neither PySide6 nor PyQt6 is available. Please install one of them.")
from pos_app.models.database import Customer, Sale, Payment, SaleItem
from datetime import datetime, time


# Shared light-theme styling for the dialog body and cards.
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
"""

_CARD_QSS = """
QFrame#card {
    background-color: #ffffff;
    border: 1px solid #e2e8f0;
    border-radius: 10px;
}
"""


class CustomerStatementDialog(QDialog):
    def __init__(self, controllers, customer_id, parent=None):
        super().__init__(parent)
        self.controllers = controllers
        self.customer_id = customer_id
        self.output_dir = os.path.join(os.getcwd(), "documents")
        os.makedirs(self.output_dir, exist_ok=True)
        self.customer = None
        self.setup_ui()
        self.load_customer_data()
        self.load_statement_data()
        self.showFullScreen()

    # ------------------------------------------------------------------ UI
    def setup_ui(self):
        self.setWindowTitle("Customer Statement")
        self.setStyleSheet(_STYLESHEET)
        self.setMinimumSize(720, 560)
        self.resize(1040, 820)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Header: customer info (stretch) + Export / Print
        header_row = QHBoxLayout()
        self.customer_info_label = QLabel("Customer: Loading...")
        self.customer_info_label.setStyleSheet(
            "font-size: 16px; font-weight: 700; color: #0f172a; "
            "padding: 10px 14px; background: #ffffff; border: 1px solid #e2e8f0; "
            "border-radius: 10px;"
        )
        self.customer_info_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        header_row.addWidget(self.customer_info_label, 1)

        export_btn = QPushButton("Export PDF")
        export_btn.setMinimumHeight(38)
        export_btn.clicked.connect(self.export_pdf)
        print_btn = QPushButton("Print")
        print_btn.setProperty('accent', 'Qt.green')
        print_btn.setMinimumHeight(38)
        print_btn.clicked.connect(self.print_statement)
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setMinimumHeight(38)
        refresh_btn.clicked.connect(self.load_statement_data)
        header_row.addWidget(refresh_btn)
        header_row.addWidget(export_btn)
        header_row.addWidget(print_btn)
        root.addLayout(header_row)

        # Filters
        filters_group = QGroupBox("Filters")
        fl = QHBoxLayout(filters_group)
        fl.setSpacing(8)
        fl.addWidget(QLabel("From:"))
        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setDate(QDate.currentDate().addMonths(-3))
        self.start_date.setDisplayFormat("yyyy-MM-dd")
        fl.addWidget(self.start_date)
        fl.addWidget(QLabel("To:"))
        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.setDisplayFormat("yyyy-MM-dd")
        fl.addWidget(self.end_date)
        fl.addWidget(QLabel("Type:"))
        self.transaction_type = QComboBox()
        self.transaction_type.addItems(["All", "Sales", "Payments", "Discounts"])
        fl.addWidget(self.transaction_type)
        filter_btn = QPushButton("🔍 Filter")
        filter_btn.clicked.connect(self.load_statement_data)
        fl.addWidget(filter_btn)
        fl.addStretch()
        root.addWidget(filters_group)

        # Summary cards — single horizontal row, compact, no groupbox title clutter
        summary_row = QHBoxLayout()
        summary_row.setSpacing(10)
        self.total_sales_label = self._make_summary_card("Total Sales", "Rs 0.00", accent="blue")
        self.total_payments_label = self._make_summary_card("Total Payments", "Rs 0.00", accent="green")
        self.total_discounts_label = self._make_summary_card("Total Discounts", "Rs 0.00", accent="amber")
        self.outstanding_label = self._make_summary_card("Amount Due", "Rs 0.00", accent="red")
        for card in (self.total_sales_label, self.total_payments_label,
                     self.total_discounts_label, self.outstanding_label):
            summary_row.addWidget(card, 1)
        root.addLayout(summary_row)

        # Statement table — single focused view, reduced fixed widths to prevent overlap
        table_group = QGroupBox("Transaction History")
        tl = QVBoxLayout(table_group)
        tl.setContentsMargins(10, 12, 10, 10)
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Date", "Description", "Invoice #", "Method", "Debit", "Credit", "Balance"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setWordWrap(False)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)  # Description flexes
        for col, w in ((0, 95), (2, 110), (3, 95), (4, 100), (5, 100), (6, 110)):
            self.table.setColumnWidth(col, w)
        self.table.setMinimumHeight(260)
        self.table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        tl.addWidget(self.table)
        root.addWidget(table_group, 1)

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
        v.setObjectName("value")
        v.setStyleSheet(f"color: {value_color}; font-size: 20px; font-weight: 800;")
        v.setTextInteractionFlags(Qt.TextSelectableByMouse)
        lay.addWidget(t)
        lay.addWidget(v)
        card._value_label = v  # convenience for updates
        return card

    # ------------------------------------------------------------------ data
    def load_customer_data(self):
        """Load customer information."""
        try:
            customer = self.controllers['customers'].session.get(Customer, self.customer_id)
            if customer:
                self.customer = customer
                self.customer_info_label.setText(
                    f"Customer: {customer.name}   (ID: {customer.id})"
                )
            else:
                self.customer_info_label.setText("Customer not found")
        except Exception as e:
            self.customer_info_label.setText(f"Error loading customer: {str(e)}")

    def load_statement_data(self):
        """Populate the on-screen table from the shared _gather_statement_data
        helper, so the screen shows ALL invoices in the period (not just the
        latest one) and matches the PDF/print output exactly."""
        try:
            start_date, end_date = self._get_selected_dates()
            data = self._gather_statement_data(start_date, end_date)

            transactions = data.get("transactions", [])
            trans_type = self.transaction_type.currentText()

            # Type filter
            if trans_type == "Sales":
                transactions = [t for t in transactions if t['type'] in ('Sale', 'Discount')]
            elif trans_type == "Payments":
                transactions = [t for t in transactions if t['type'] == 'Payment']
            elif trans_type == "Discounts":
                transactions = [t for t in transactions if t['type'] == 'Discount']

            # Display newest-first (balance already computed chronologically)
            transactions = list(reversed(transactions))

            self.table.setRowCount(0)
            if not transactions:
                self.table.setRowCount(1)
                self.table.setSpan(0, 0, 1, 7)
                empty = QTableWidgetItem("No transactions found for the selected period")
                empty.setTextAlignment(Qt.AlignCenter)
                empty.setForeground(QColor('#94a3b8'))
                self.table.setItem(0, 0, empty)
            else:
                self.table.setRowCount(len(transactions))
                for row, t in enumerate(transactions):
                    self._set_cell(row, 0, t.get('date', ''), Qt.AlignCenter)
                    self._set_cell(row, 1, t.get('description', ''), Qt.AlignLeft | Qt.AlignVCenter)
                    self._set_cell(row, 2, t.get('invoice', '—'), Qt.AlignCenter)
                    self._set_cell(row, 3, t.get('method', '—'), Qt.AlignCenter)
                    self._set_cell(row, 4,
                                   self._format_currency(t['debit']) if t.get('debit', 0) > 0 else "",
                                   Qt.AlignRight | Qt.AlignVCenter)
                    self._set_cell(row, 5,
                                   self._format_currency(t['credit']) if t.get('credit', 0) > 0 else "",
                                   Qt.AlignRight | Qt.AlignVCenter)
                    bal_item = QTableWidgetItem(self._format_currency(t.get('balance', 0)))
                    bal_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                    if float(t.get('balance', 0)) < 0:
                        bal_item.setForeground(QColor('#dc2626'))
                    self.table.setItem(row, 6, bal_item)

            # Summary cards — use the UNFILTERED totals from _gather_statement_data
            # so the cards keep showing real totals even when a Type filter is applied
            # (the on-screen table is filtered, but the summary should not blank out).
            total_sales = float(data.get('total_sales', 0) or 0)
            total_payments = float(data.get('total_payments', 0) or 0)
            total_discounts = float(data.get('total_discounts', 0) or 0)
            amount_due = float(data.get('closing_balance', 0) or 0)

            self.total_sales_label._value_label.setText(self._format_currency(total_sales))
            self.total_payments_label._value_label.setText(self._format_currency(total_payments))
            self.total_discounts_label._value_label.setText(self._format_currency(total_discounts))
            self.outstanding_label._value_label.setText(self._format_currency(amount_due))
            due_color = '#dc2626' if amount_due > 0 else '#16a34a'
            self.outstanding_label._value_label.setStyleSheet(
                f"color: {due_color}; font-size: 18px; font-weight: 700;"
            )

        except Exception as e:
            print(f"CRITICAL ERROR in load_statement_data: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Error", f"Failed to load statement data: {str(e)}")

    def _set_cell(self, row, col, text, alignment):
        item = QTableWidgetItem(str(text))
        item.setTextAlignment(alignment)
        self.table.setItem(row, col, item)

    # ------------------------------------------------------------------ print/pdf
    def export_pdf(self):
        """Export statement to PDF using HTML rendering."""
        filename = f"customer_statement_{self.customer_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        filepath = os.path.join(self.output_dir, filename)

        printer = QPrinter()
        printer.setOutputFormat(QPrinter.PdfFormat)
        printer.setOutputFileName(filepath)
        printer.setPageSize(QPageSize(QPageSize.Legal))
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)
        printer.setPageMargins(QMarginsF(12.7, 12.7, 12.7, 18), QPageLayout.Unit.Millimeter)

        html_content = self._build_statement_html()
        self._print_html_document(printer, html_content)

        QMessageBox.information(self, "Exported", f"Statement exported to:\n{filepath}")

    def _build_statement_html(self):
        try:
            start_date, end_date = self._get_selected_dates()
            data = self._gather_statement_data(start_date, end_date)

            shop_info = self._get_shop_info()
            period_text = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            generated_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        except Exception as e:
            print(f"[ERROR] _build_statement_html error: {e}")
            raise

        def esc(value):
            return html.escape(str(value) if value is not None else "")

        txns = data.get("transactions", [])
        if not txns:
            rows_html = "<tr><td colspan='7' class='empty'>No transactions found for the selected period.</td></tr>"
        else:
            rows_html = ""
            for t in txns:
                debit_txt = self._format_currency(t['debit']) if t.get('debit', 0) > 0 else "—"
                credit_txt = self._format_currency(t['credit']) if t.get('credit', 0) > 0 else "—"
                rows_html += (
                    "<tr>"
                    f"<td>{esc(t['date'])}</td>"
                    f"<td class='desc'>{esc(t['description'])}</td>"
                    f"<td>{esc(t['invoice'])}</td>"
                    f"<td>{esc(t['method'])}</td>"
                    f"<td class='numeric'>{esc(debit_txt)}</td>"
                    f"<td class='numeric'>{esc(credit_txt)}</td>"
                    f"<td class='numeric'>{self._format_currency(t['balance'])}</td>"
                    "</tr>"
                )

        summary_cards = [
            ("Opening Balance", self._format_currency(data["opening_balance"])),
            ("Total Sales", self._format_currency(data["total_sales"])),
            ("Total Payments", self._format_currency(data["total_payments"])),
        ]

        total_discounts = float(data.get('total_discounts', 0) or 0)
        if total_discounts > 0:
            summary_cards.append(("Total Discounts", self._format_currency(-total_discounts)))

        summary_cards.append(("Closing Balance (Amount Due)", self._format_currency(data["closing_balance"])))

        # Build a compact, Qt-safe print layout.  QTextDocument is *not* a browser:
        # it does not support flexbox, inline-block, gradients, or percentage
        # widths reliably.  We use plain HTML tables with explicit <col> widths
        # and a single compact font stack so nothing overlaps or overflows.
        opening = self._format_currency(data["opening_balance"])
        total_sales = self._format_currency(data["total_sales"])
        total_payments = self._format_currency(data["total_payments"])
        closing = self._format_currency(data["closing_balance"])
        total_discounts = self._format_currency(data.get("total_discounts", 0) or 0)
        has_discount = float(data.get("total_discounts", 0) or 0) > 0

        discount_row = ""
        if has_discount:
            discount_row = (
                f"<div class='discount-line'>Discounts given: {esc(total_discounts)}</div>"
            )

        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8" />
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
            border: 1.5pt solid #000; table-layout: fixed;
        }}
        .summary-table td {{
            width: 25%; padding: 7pt 4pt; text-align: center;
            border: 1pt solid #666; vertical-align: top;
            background-color: #f9fafb;
        }}
        .summary-table .slabel {{ font-size: 7pt; color: #333; }}
        .summary-table .sval {{ font-size: 11pt; font-weight: bold; }}
        .due {{ color: #c00000; }}
        .discount-line {{
            font-size: 9pt; color: #c00000; margin-bottom: 6pt; text-align: right;
        }}
        table.txn {{
            width: 100%; border-collapse: collapse; table-layout: fixed;
            font-size: 9pt; border: 1.5pt solid #000;
        }}
        table.txn th, table.txn td {{
            padding: 6pt 5pt; border: 1pt solid #666; vertical-align: top;
        }}
        table.txn th {{
            background-color: #e2e8f0; color: #000; font-weight: bold;
            text-align: center; font-size: 8.5pt;
        }}
        table.txn td.numeric {{
            text-align: right; font-variant-numeric: tabular-nums;
        }}
        table.txn td.desc {{ text-align: left; }}
        table.txn td.empty {{ text-align: center; color: #666; }}
        table.txn tfoot td {{
            border-top: 1.5pt solid #000; border-bottom: 1.5pt solid #000;
            font-weight: bold; background-color: #f9fafb;
        }}
        .empty {{ text-align: center; padding: 12pt 0; color: #666; }}
        .footer {{
            margin-top: 12pt; text-align: center; font-size: 8pt; color: #666;
        }}
    </style>
</head>
<body>
    <div class="center">
        <div class="shop">{esc(shop_info['name'])}</div>
        <div class="shop-meta">{esc(shop_info['address'])} &nbsp;|&nbsp; {esc(shop_info['phone'])}</div>
        <div class="title">CUSTOMER STATEMENT</div>
    </div>

    <table class="info-table">
        <tr>
            <td style="width:55%;">
                <span class="label">Bill To:</span> {esc(data['customer_name'])}<br>
                {esc(data['customer_address'])}<br>
                {esc(data['customer_phone'])}
            </td>
            <td style="width:45%; text-align:right;">
                <span class="label">Period:</span> {esc(period_text)}<br>
                <span class="label">Generated:</span> {esc(generated_text)}
            </td>
        </tr>
    </table>

    <table class="summary-table">
        <tr>
            <td><div class="slabel">OPENING BALANCE</div><div class="sval">{esc(opening)}</div></td>
            <td><div class="slabel">TOTAL SALES</div><div class="sval">{esc(total_sales)}</div></td>
            <td><div class="slabel">TOTAL PAYMENTS</div><div class="sval">{esc(total_payments)}</div></td>
            <td><div class="slabel">AMOUNT DUE</div><div class="sval due">{esc(closing)}</div></td>
        </tr>
    </table>
    {discount_row}

    <table class="txn" border="1" cellpadding="4">
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
                <th>Invoice #</th>
                <th>Method</th>
                <th>Debit</th>
                <th>Credit</th>
                <th>Balance</th>
            </tr>
        </thead>
        <tbody>{rows_html}</tbody>
        <tfoot>
            <tr>
                <td colspan="6" style="text-align:right;">CLOSING BALANCE (AMOUNT DUE):</td>
                <td class="numeric due">{esc(closing)}</td>
            </tr>
        </tfoot>
    </table>

    <div class="footer">
        Generated on {esc(generated_text)} &nbsp;|&nbsp; Thank you for your business!
    </div>
</body>
</html>
"""
        return html_content

    def _gather_statement_data(self, start_date, end_date):
        """Gather ALL transactions (sales items + discounts + payments) in the
        period with a true running balance, for both the on-screen table and the
        printout. Single source of truth for the dialog."""
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        session = self.controllers['customers'].session

        customer = session.get(Customer, self.customer_id)
        current_credit = float(getattr(customer, 'current_credit', 0) or 0)

        from sqlalchemy.orm import joinedload

        sales = session.query(Sale).options(
            joinedload(Sale.items).joinedload(SaleItem.product)
        ).filter(
            Sale.customer_id == self.customer_id,
            Sale.sale_date >= start_dt,
            Sale.sale_date <= end_dt
        ).order_by(Sale.sale_date.asc(), Sale.id.asc()).all()

        payments = session.query(Payment).filter(
            Payment.customer_id == self.customer_id,
            Payment.payment_date >= start_dt,
            Payment.payment_date <= end_dt,
            Payment.payment_method != 'CREDIT'
        ).order_by(Payment.payment_date.asc(), Payment.id.asc()).all()

        def _fmt_method(pm):
            try:
                return str(pm) if pm is not None else '—'
            except Exception:
                return '—'

        transactions = []

        for sale in sales:
            sale_date_text = sale.sale_date.strftime('%Y-%m-%d') if sale.sale_date else ""
            invoice_no = getattr(sale, 'invoice_number', '') or f"INV-{sale.id}"
            items = list(getattr(sale, 'items', []) or [])
            sale_total = float(getattr(sale, 'total_amount', 0) or 0)
            sale_subtotal = float(getattr(sale, 'subtotal', 0) or 0)

            if not items:
                transactions.append({
                    'date': sale_date_text, 'type': 'Sale', 'invoice': invoice_no,
                    'method': '—', 'description': 'Sale Items',
                    'debit': sale_total, 'credit': 0.0,
                })
            else:
                for item in items:
                    product = getattr(item, 'product', None)
                    product_name = getattr(product, 'name', 'Unknown Item') if product else 'Unknown Item'
                    quantity = getattr(item, 'quantity', 1) or 1
                    unit_price = float(getattr(item, 'unit_price', getattr(item, 'price', 0)) or 0)
                    if sale_subtotal > 0:
                        item_total = float(getattr(item, 'total', (unit_price * quantity)) or (unit_price * quantity))
                        proportion = item_total / sale_subtotal
                        final_amount = sale_total * proportion
                    else:
                        final_amount = float(getattr(item, 'total', (unit_price * quantity)) or (unit_price * quantity))
                    transactions.append({
                        'date': sale_date_text, 'type': 'Sale', 'invoice': invoice_no,
                        'method': '—',
                        'description': f"{product_name} (Qty {quantity} @ {self._format_currency(unit_price)})",
                        'debit': final_amount, 'credit': 0.0,
                    })

            discount_amount = float(getattr(sale, 'discount_amount', 0) or 0)
            if discount_amount > 0:
                transactions.append({
                    'date': sale_date_text, 'type': 'Discount', 'invoice': invoice_no,
                    'method': '—', 'description': 'Discount Given',
                    'debit': 0.0, 'credit': discount_amount,
                })

        for payment in payments:
            payment_amount = float(getattr(payment, 'amount', 0) or 0)
            transactions.append({
                'date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else "",
                'type': 'Payment', 'invoice': '—',
                'method': _fmt_method(getattr(payment, 'payment_method', None)),
                'description': 'Payment Received', 'debit': 0.0, 'credit': payment_amount,
            })

        transactions.sort(key=lambda x: (x['date'] or ''))

        total_debit = sum(t['debit'] for t in transactions)
        total_credit = sum(t['credit'] for t in transactions)
        opening_balance = current_credit - (total_debit - total_credit)

        running = opening_balance
        for t in transactions:
            running += t['debit'] - t['credit']
            t['balance'] = running

        return {
            "transactions": transactions,
            "opening_balance": opening_balance,
            "total_sales": sum(t['debit'] for t in transactions if t['type'] == 'Sale'),
            "total_payments": sum(t['credit'] for t in transactions if t['type'] == 'Payment'),
            "total_discounts": sum(t['credit'] for t in transactions if t['type'] == 'Discount'),
            "closing_balance": current_credit,
            "customer_name": getattr(customer, 'name', '') if customer else '',
            "customer_address": getattr(customer, 'address', '') if customer else '',
            # Customer model uses `contact`, not `phone`
            "customer_phone": getattr(customer, 'contact', '') if customer else '',
        }

    def _print_html_document(self, printer, html_content):
        document = QTextDocument()
        document.setDocumentMargin(24)
        document.setDefaultFont(QFont("Segoe UI", 12))
        document.setHtml(html_content)

        try:
            page_layout = printer.pageLayout()
            paint_rect = page_layout.paintRectPixels(printer.resolution())
            document.setPageSize(QSizeF(paint_rect.width(), paint_rect.height()))
        except Exception as e:
            print(f"ERROR setting page size: {e}")
            document.setPageSize(QSizeF(printer.width(), printer.height()))

        if hasattr(document, "print"):
            document.print(printer)
        else:
            document.print_(printer)

    def _get_selected_dates(self):
        def to_py_date(qdate):
            try:
                return qdate.toPython()
            except AttributeError:
                return datetime.strptime(qdate.toString("yyyy-MM-dd"), "%Y-%m-%d").date()
        return to_py_date(self.start_date.date()), to_py_date(self.end_date.date())

    def _format_currency(self, value):
        try:
            return f"Rs {float(value):,.2f}"
        except Exception:
            return f"Rs {value}"

    def _get_shop_info(self):
        """Get shop information from settings."""
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

    def print_statement(self):
        """Print customer statement with proper formatting and printer selection."""
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
        dialog.setWindowTitle("Print Customer Statement")
        if dialog.exec() != QPrintDialog.Accepted:
            return

        html_content = self._build_statement_html()
        self._print_html_document(printer, html_content)

    def add_print_button(self):
        """Legacy compatibility hook — printing is already in the header."""
        pass
