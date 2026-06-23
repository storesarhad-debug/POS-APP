try:

    from PySide6.QtWidgets import (

        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,

        QTableWidget, QTableWidgetItem, QComboBox, QLineEdit, QDoubleSpinBox,

        QFrame, QMessageBox, QDialog, QTextEdit, QSizePolicy, QScrollArea,

        QLineEdit, QGridLayout, QHeaderView, QProgressBar, QCheckBox,

        QSplitter, QGroupBox, QFormLayout, QSpinBox, QDateTimeEdit, QListWidget, QListWidgetItem,

        QAbstractItemView

    )

    from PySide6.QtCore import Qt, QTimer, QUrl, QSizeF, QMarginsF, QPoint, QDateTime, QEvent

    from PySide6.QtGui import (

        QFont, QDesktopServices, QPageSize, QPageLayout, QPainter,

        QShortcut, QKeySequence, QFontMetrics, QPixmap, QPixmapCache,

        QTextDocument, QColor, QIcon, QPalette, QBrush, QLinearGradient

    )

    from PySide6.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo

except ImportError:

    from PyQt6.QtWidgets import (

        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,

        QTableWidget, QTableWidgetItem, QComboBox, QDoubleSpinBox,

        QFrame, QMessageBox, QDialog, QTextEdit, QSizePolicy, QScrollArea,

        QLineEdit, QGridLayout, QHeaderView, QProgressBar, QCheckBox,

        QSplitter, QGroupBox, QFormLayout, QSpinBox, QDateTimeEdit, QListWidget, QListWidgetItem,

        QAbstractItemView

    )

    from PyQt6.QtCore import Qt, QTimer, QUrl, QSizeF, QMarginsF, QPoint, QDateTime, QEvent

    from PyQt6.QtGui import (

        QFont, QDesktopServices, QPageSize, QPageLayout, QPainter,

        QShortcut, QKeySequence, QFontMetrics, QPixmap, QPixmapCache,

        QTextDocument, QColor, QIcon, QPalette, QBrush, QLinearGradient

    )

    from PyQt6.QtPrintSupport import QPrinter, QPrintDialog, QPrinterInfo

import os

import sys

import time

from datetime import datetime

from pos_app.utils.document_generator import DocumentGenerator

try:

    from PySide6.QtCore import QSettings

except ImportError:

    from PyQt6.QtCore import QSettings

import logging



app_logger = logging.getLogger(__name__)



_DEBUG_SALES = os.getenv('POS_DEBUG_SALES', '0') in ('1', 'true', 'yes')



def _dprint(*args, **kwargs):

    if _DEBUG_SALES:

        try:

            print(*args, **kwargs)

        except Exception:

            pass



class ReceiptPreviewDialog(QDialog):

    def __init__(self, receipt_data, parent=None):

        super().__init__(parent)

        # Keep original API name from old implementation

        self.sale_data = receipt_data

        self.setup_ui()

        # Allow Enter key to trigger immediate print & close

        try:

            self.installEventFilter(self)

        except Exception:

            pass



    def setup_ui(self):

        is_refund = self.sale_data.get('is_refund', False) if isinstance(self.sale_data, dict) else False

        self.setWindowTitle("Refund Receipt Preview" if is_refund else "Sales Receipt Preview")

        self.setMinimumSize(450, 600)

        self.setMaximumSize(500, 700)



        layout = QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)



        # Header

        header_layout = QHBoxLayout()

        title = QLabel("Refund Receipt Preview" if is_refund else "Receipt Preview")

        title.setStyleSheet("font-size: 18px; font-weight: bold; color: #f8fafc;")

        header_layout.addWidget(title)

        header_layout.addStretch()



        # Print button

        print_btn = QPushButton("Print Receipt")

        print_btn.setProperty('accent', 'Qt.blue')

        print_btn.setMinimumHeight(36)

        print_btn.clicked.connect(self.print_receipt)

        header_layout.addWidget(print_btn)



        layout.addLayout(header_layout)



        # Receipt preview area

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)



        # Receipt content

        self.receipt_widget = QWidget()

        self.receipt_widget.setStyleSheet("""

            QWidget {

                background-color: Qt.white;

                color: Qt.black;

                padding: 1px;

            }

        """)



        receipt_layout = QVBoxLayout(self.receipt_widget)

        receipt_layout.setContentsMargins(1, 1, 1, 1)

        receipt_layout.setSpacing(1)



        # Generate receipt content

        self.generate_receipt_content(receipt_layout)



        scroll_area.setWidget(self.receipt_widget)

        layout.addWidget(scroll_area)



        # Action buttons

        button_layout = QHBoxLayout()



        close_btn = QPushButton("Close")

        close_btn.setProperty('accent', 'Qt.red')

        close_btn.setMinimumHeight(40)

        close_btn.clicked.connect(self.reject)



        print_and_close_btn = QPushButton("Print & Close")

        print_and_close_btn.setProperty('accent', 'Qt.green')

        print_and_close_btn.setMinimumHeight(40)

        print_and_close_btn.clicked.connect(self.print_and_close)



        button_layout.addWidget(close_btn)

        button_layout.addStretch()

        button_layout.addWidget(print_and_close_btn)



        layout.addLayout(button_layout)



        # Apply font scaling from settings

        try:

            settings = QSettings("POSApp", "Settings")

            size = (settings.value("receipt_font_size", "Small") or "Small").lower()

            base_px = 10 if size == "small" else 12 if size == "medium" else 14

            self.receipt_widget.setStyleSheet(self.receipt_widget.styleSheet() + f"\n* {{ font-size: {base_px}px; }}")

        except Exception:

            pass



        # Bind shortcuts for dialog

        try:

            sc_print = QShortcut(QKeySequence("Ctrl+P"), self)

            sc_print.activated.connect(self.print_receipt)

            sc_close = QShortcut(QKeySequence("Esc"), self)

            sc_close.activated.connect(self.reject)

        except Exception:

            pass



    def generate_receipt_content(self, layout):

        """Generate the receipt content to match the thermal design."""

        try:

            settings = QSettings("POSApp", "Settings")

            biz = self.sale_data.get('business_info', {}) if isinstance(self.sale_data, dict) else {}

            biz_name = biz.get('name') or (settings.value("business_name", "") or "")

            biz_addr = biz.get('address') or (settings.value("business_address", "") or "")

            biz_phone = biz.get('phone') or (settings.value("business_phone", "+923225031977") or "+923225031977")

            logo_path = settings.value("logo_path", "") or ""

            

            # Robust logo path resolution for both dev and frozen environments

            possible_logos = ["Logo.png", "logo.png"]

            logo_search_paths = []

            

            # 1. Check relative to this file's root (dev mode)

            root_dev = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            logo_search_paths.append(root_dev)

            

            # 2. Check PyInstaller temp bundle root

            if hasattr(sys, '_MEIPASS'):

                logo_search_paths.append(sys._MEIPASS)

                # Also check pos_app subdirectory in bundle

                logo_search_paths.append(os.path.join(sys._MEIPASS, "pos_app"))

            

            # 3. Check relative to the executable (for external logos)

            if getattr(sys, 'frozen', False):

                exe_dir = os.path.dirname(sys.executable)

                logo_search_paths.append(exe_dir)

            

            for path in logo_search_paths:

                for name in possible_logos:

                    test_path = os.path.join(path, name)

                    if os.path.exists(test_path):

                        logo_path = test_path

                        print(f"[DEBUG] Found logo at: {logo_path}")

                        break

                if logo_path: break

            

            if not logo_path:

                print(f"[DEBUG] logo.png/Logo.png not found in any standard location")



            # Logo

            print(f"[DEBUG] Logo path: {logo_path}, exists: {os.path.exists(logo_path) if logo_path else False}")

            if logo_path and os.path.exists(logo_path):

                logo_pixmap = QPixmap(logo_path)

                if not logo_pixmap.isNull():

                    # Scale logo to match print size - large

                    scaled_logo = logo_pixmap.scaled(350, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                    logo_label = QLabel()

                    logo_label.setPixmap(scaled_logo)

                    logo_label.setAlignment(Qt.AlignCenter)

                    layout.addWidget(logo_label)



            # Header (do not override business name)

            biz_name = biz_name or "Sarhad General Store and Wholesale Dealer"

            # Always split store name into two lines for better formatting

            if " and " in biz_name:

                parts = biz_name.split(" and ", 1)

                header1 = QLabel(parts[0])

                header1.setAlignment(Qt.AlignCenter)

                header1.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 0px;")

                layout.addWidget(header1)

                header2 = QLabel("and " + parts[1])

                header2.setAlignment(Qt.AlignCenter)

                header2.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 2px;")

                layout.addWidget(header2)

            else:

                # If no "and" found, use single line

                header = QLabel(biz_name)

                header.setAlignment(Qt.AlignCenter)

                header.setStyleSheet("font-size: 20px; font-weight: bold; margin-bottom: 2px;")

                layout.addWidget(header)



            if biz_addr:

                addr_lbl = QLabel(biz_addr)

                addr_lbl.setAlignment(Qt.AlignCenter)

                addr_lbl.setStyleSheet("font-size: 11px;")

                layout.addWidget(addr_lbl)

            if biz_phone:

                phone_lbl = QLabel(f"Contact No : {biz_phone}")

                phone_lbl.setAlignment(Qt.AlignCenter)

                phone_lbl.setStyleSheet("font-size: 11px;")

                layout.addWidget(phone_lbl)



            dotted = QLabel("." * 60)

            dotted.setAlignment(Qt.AlignCenter)

            dotted.setStyleSheet("font-family: monospace; margin: 4px 0;")

            layout.addWidget(dotted)



            # Add REFUND RECEIPT header if this is a refund

            is_refund = self.sale_data.get('is_refund', False) if isinstance(self.sale_data, dict) else False

            if is_refund:

                refund_header = QLabel("REFUND RECEIPT")

                refund_header.setAlignment(Qt.AlignCenter)

                refund_header.setStyleSheet("font-size: 16px; font-weight: bold; color: #dc2626; margin: 4px 0;")

                layout.addWidget(refund_header)

                refund_dotted = QLabel("-" * 40)

                refund_dotted.setAlignment(Qt.AlignCenter)

                refund_dotted.setStyleSheet("font-family: monospace; margin: 4px 0;")

                layout.addWidget(refund_dotted)



            # Info block

            inv = self.sale_data.get('invoice_number') or ''

            cashier = self.sale_data.get('cashier', 'Admin')

            dt = datetime.now()

            date_str = dt.strftime('%Y-%m-%d')

            time_str = dt.strftime('%H:%M')

            info = QLabel(

                f"Invoice No : {inv}      Date {date_str}\n"

                f"Cashier : {cashier}      Time {time_str}"

            )

            info.setAlignment(Qt.AlignLeft)  # Left align

            info.setStyleSheet("font-size: 11px; font-weight: 700; font-family: monospace;")  # Made bold

            layout.addWidget(info)



            # Column widths for alignment - reduced to fit 80mm thermal printer

            QTY_W = 4

            NAME_W = 16

            PRICE_W = 8

            AMT_W = 9

            lbl_w = 12



            # Items header (monospace grid) - highlighted with uppercase for emphasis

            header_line = f"| {'ITEM NAME':^{NAME_W}} | {'QTY':^{QTY_W}} | {'PRICE':^{PRICE_W}} | {'TOTAL':^{AMT_W}} |"

            items_hdr = QLabel(header_line)

            items_hdr.setAlignment(Qt.AlignLeft)  # Left align

            items_hdr.setStyleSheet("font-size: 10px; font-weight: 700; font-family: Arial, monospace; margin-top: 6px;")  # Bold

            layout.addWidget(items_hdr)



            dotted2 = QLabel("=" * 60)  # Changed to = for thicker border

            dotted2.setAlignment(Qt.AlignCenter)

            dotted2.setStyleSheet("font-family: monospace; margin: 2px 0;")

            layout.addWidget(dotted2)



            # Items

            total_amount = 0.0

            is_refund = self.sale_data.get('is_refund', False)

            items_list = self.sale_data.get('items', [])

            print(f"[DEBUG] Receipt items count: {len(items_list)}, is_refund: {is_refund}")

            print(f"[DEBUG] Items: {items_list}")



            for item in items_list:

                name = (item.get('name') or item.get('product_name') or '')

                # Add "R" marker for refunded items

                if is_refund:

                    name = f"{name} R"

                qty = item.get('quantity', 0)

                price = float(item.get('price', 0) or item.get('unit_price', 0) or 0)

                amt = qty * price

                total_amount += amt

                # Truncate name to fit if too long

                name_display = name[:NAME_W] if len(name) > NAME_W else name

                row_line = f"|{name_display:<{NAME_W}} |{qty:>{QTY_W}} |{price:>{PRICE_W}.2f} |{amt:>{AMT_W}.2f} |"

                row = QLabel(row_line)

                row.setAlignment(Qt.AlignLeft)  # Left align

                row.setStyleSheet("font-size: 11px; font-weight: 800; font-family: Arial Black, monospace;")  # Bigger and bolder

                layout.addWidget(row)



            dotted3 = QLabel("=" * 60)  # Changed to = for thicker border

            dotted3.setAlignment(Qt.AlignCenter)

            dotted3.setStyleSheet("font-family: monospace; margin: 4px 0;")

            layout.addWidget(dotted3)



            # Totals (centered)

            sd = self.sale_data if isinstance(self.sale_data, dict) else {}

            subtotal = float(sd.get('subtotal', total_amount))

            tax_rate = float(sd.get('tax_rate', 0.0))

            discount_amount = float(sd.get('discount_amount', 0.0))

            tax_rate = float(sd.get('tax_rate', 0.0))

            tax_amount = float(sd.get('tax_amount', 0.0))

            final_total = float(sd.get('final_total', subtotal - discount_amount + tax_amount))

            cash = float(sd.get('amount_paid', final_total) or final_total)

            change = float(sd.get('change_amount', max(0.0, cash - final_total)))

            payment_method = sd.get('payment_method', 'Cash')

            is_refund = sd.get('sale_type', '').lower() == 'refund'



            eq = QLabel("=" * 52)

            eq.setAlignment(Qt.AlignCenter)

            eq.setStyleSheet("font-family: monospace; margin-top: 6px;")

            layout.addWidget(eq)

            

            # Create totals with center alignment

            totals_layout = QVBoxLayout()

            totals_layout.setContentsMargins(20, 0, 20, 0)



            subtotal_lbl = QLabel(f"Subtotal: {subtotal:>8.2f}")

            subtotal_lbl.setAlignment(Qt.AlignLeft)  # Left align

            subtotal_lbl.setStyleSheet("font-size: 11px; font-weight: 800; font-family: Arial Black, monospace;")  # Bigger and bolder

            totals_layout.addWidget(subtotal_lbl)



            if discount_amount > 0:

                discount_lbl = QLabel(f"Discount: {discount_amount:>8.2f}")

                discount_lbl.setAlignment(Qt.AlignLeft)  # Left align

                discount_lbl.setStyleSheet("font-size: 11px; font-weight: 800; font-family: Arial Black, monospace;")  # Bigger and bolder

                totals_layout.addWidget(discount_lbl)



            if tax_amount > 0:

                tax_lbl = QLabel(f"Tax({tax_rate:.0f}%): {tax_amount:>8.2f}")

                tax_lbl.setAlignment(Qt.AlignLeft)  # Left align

                tax_lbl.setStyleSheet("font-size: 11px; font-weight: 800; font-family: Arial Black, monospace;")  # Bigger and bolder

                totals_layout.addWidget(tax_lbl)

            

            # Show Change first, then Amount Paid below it

            if change > 0:

                change_lbl = QLabel(f"Change: {change:>8.2f}")

                change_lbl.setAlignment(Qt.AlignLeft)  # Left align

                change_lbl.setStyleSheet("font-size: 12px; font-weight: 800; font-family: Arial Black, monospace;")  # Bigger and bolder

                totals_layout.addWidget(change_lbl)



            paid_lbl = QLabel(f"Amount Paid: {cash:>8.2f}")

            paid_lbl.setAlignment(Qt.AlignLeft)

            paid_lbl.setStyleSheet("font-size: 13px; font-weight: 900; font-family: Arial Black, monospace;")  # Bigger and bolder

            totals_layout.addWidget(paid_lbl)



            # TOTAL line comes after Amount Paid

            total_lbl = QLabel(f"TOTAL: {final_total:>8.2f}")

            total_lbl.setAlignment(Qt.AlignLeft)  # Left align

            total_lbl.setStyleSheet("font-size: 14px; font-weight: 900; font-family: Arial Black, monospace;")  # Extra bold and bigger

            totals_layout.addWidget(total_lbl)

            

            layout.addLayout(totals_layout)



            off_lbl = QLabel("THIS IS YOUR OFFICIAL RECEIPT")

            off_lbl.setAlignment(Qt.AlignCenter)

            off_lbl.setStyleSheet("font-size: 11px; font-weight: 700;")  # Made bold

            layout.addWidget(off_lbl)



            thanks = settings.value("receipt_footer", sd.get('receipt_footer', "Thank You Come Again!")) or "Thank You Come Again!"

            thanks_lbl = QLabel(f"{thanks}")

            thanks_lbl.setAlignment(Qt.AlignCenter)

            thanks_lbl.setStyleSheet("font-size: 12px; font-weight: 700;")  # Made bold

            layout.addWidget(thanks_lbl)



            # Return policy notice at the very bottom of the receipt

            policy_lbl = QLabel("Items cannot be returned after 3 days of purchase.")

            policy_lbl.setAlignment(Qt.AlignCenter)

            policy_lbl.setStyleSheet("font-size: 10px; font-weight: 700; margin-top: 4px;")  # Made bold

            layout.addWidget(policy_lbl)



        except Exception as e:

            error_label = QLabel(f"Error generating receipt: {str(e)}")

            error_label.setStyleSheet("color: Qt.red; font-size: 12px;")

            layout.addWidget(error_label)



    def print_receipt(self):

        """Direct-print to the configured thermal printer; fallback to PDF if unavailable."""

        try:

            print("[DEBUG] Starting print_receipt")

            # Read printing preferences

            settings = QSettings("POSApp", "Settings")

            printer_name = settings.value("printer_name", "") or ""

            width_mm = int(settings.value("receipt_width_mm", 80) or 80)  # Default to 80mm

            margin_mm = int(settings.value("receipt_margin_mm", 5) or 5)  # Increased margin to prevent wrapping

            print(f"[DEBUG] Printer: {printer_name}, Width: {width_mm}mm, Margin: {margin_mm}mm")



            # Calculate dynamic height based on content

            item_count = len(self.sale_data.get('items', []))

            # Increased base height and item multiplier to account for larger logo and spacing

            height_mm = max(180, 120 + item_count * 8 + 50)

            # Determine if target printer is a thermal roll printer
            is_thermal = False
            p_name_lower = printer_name.lower() if printer_name else ""
            thermal_keywords = ["thermal", "pos", "xprinter", "epson", "receipt", "80mm", "roll", "star", "bixolon", "citizen", "samsung", "xp-", "sabar", "zjiang"]
            if any(kw in p_name_lower for kw in thermal_keywords):
                is_thermal = True

            # Cap the page height to prevent driver crash on standard page-based printers / PDF fallbacks
            if is_thermal:
                height_mm = min(600, height_mm) # Cap at 600mm even for thermal to be safe
            else:
                height_mm = min(297, height_mm) # Cap at standard A4 height (297mm) for non-thermal/PDF printers

            print(f"[DEBUG] Items: {item_count}, Height: {height_mm}mm (thermal detected: {is_thermal})")



            # Find selected printer, or fallback to first available

            target_printer = None

            printers = list(QPrinterInfo.availablePrinters())

            print(f"[DEBUG] Available printers: {[p.printerName() for p in printers]}")

            if printer_name:

                for p in printers:

                    if p.printerName() == printer_name:

                        target_printer = p

                        break

            if target_printer is None and printers:

                target_printer = printers[0]

                printer_name = target_printer.printerName()

            print(f"[DEBUG] Using printer: {printer_name}")



            if target_printer:

                # Column widths - reduced to fit 80mm thermal printer

                QTY_W = 4

                NAME_W = 16

                PRICE_W = 8

                AMT_W = 9

                lbl_w = 12



                # Prepare text-mode lines using sale_data - MATCH PREVIEW EXACTLY

                sd = self.sale_data if isinstance(self.sale_data, dict) else {}

                settings = QSettings("POSApp", "Settings")

                biz = sd.get('business_info', {})

                biz_name = biz.get('name') or (settings.value("business_name", "") or "")

                biz_addr = biz.get('address') or (settings.value("business_address", "") or "")

                biz_phone = biz.get('phone') or (settings.value("business_phone", "+923225031977") or "+923225031977")

                logo_path = settings.value("logo_path", "") or ""

                

                # Default to Logo.png/logo.png if no logo set in settings

                if not logo_path:

                    possible_logos = ["Logo.png", "logo.png"]

                    logo_search_paths = []

                    root_dev = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

                    logo_search_paths.append(root_dev)

                    if hasattr(sys, '_MEIPASS'):

                        logo_search_paths.append(sys._MEIPASS)

                        logo_search_paths.append(os.path.join(sys._MEIPASS, "pos_app"))

                    if getattr(sys, 'frozen', False):

                        logo_search_paths.append(os.path.dirname(sys.executable))

                    

                    for path in logo_search_paths:

                        for name in possible_logos:

                            test_path = os.path.join(path, name)

                            if os.path.exists(test_path):

                                logo_path = test_path

                                break

                        if logo_path: break

                    

                    if logo_path:

                        print(f"[DEBUG] Using default logo: {logo_path}")

                

                print(f"[DEBUG] Logo path for printing: {logo_path}")

                

                inv = sd.get('invoice_number') or ''

                cashier = sd.get('cashier', 'Admin')

                dt = datetime.now()

                date_str = dt.strftime('%Y-%m-%d')

                time_str = dt.strftime('%H:%M')



                subtotal = float(sd.get('subtotal', 0.0))

                discount_amount = float(sd.get('discount_amount', 0.0))

                tax_rate = float(sd.get('tax_rate', 0.0))

                tax_amount = float(sd.get('tax_amount', 0.0))

                final_total = float(sd.get('final_total', subtotal - discount_amount + tax_amount))

                cash = float(sd.get('amount_paid', final_total) or final_total)

                change = float(sd.get('change_amount', max(0.0, cash - final_total)))

                payment_method = sd.get('payment_method', 'Cash')

                is_refund = sd.get('sale_type', '').lower() == 'refund' or sd.get('is_refund', False)



                txt_lines = []

                # Header - store name (wrapped in two lines if needed)

                print(f"[DEBUG] Business name from settings: '{biz_name}'")

                print(f"[DEBUG] Business name from sale_data: '{sd.get('business_info', {}).get('name', '')}'")

                if biz_name:

                    print(f"[DEBUG] Using business name: '{biz_name}'")

                    # Always split any business name containing "and" or "&" into two lines

                    biz_name_lower = biz_name.lower()

                    if " and " in biz_name_lower:

                        # Find the position of "and" and split there

                        and_index = biz_name_lower.find(" and ")

                        if and_index > 0:

                            # Split the name at "and"

                            part1 = biz_name[:and_index].strip()

                            part2 = "and " + biz_name[and_index + 5:].strip()

                            txt_lines.append(('HEADER', part1))

                            txt_lines.append(('HEADER', part2))

                        else:

                            # Fallback: just use the business name as is

                            txt_lines.append(('HEADER', biz_name))

                    elif "&" in biz_name:

                        # Handle & character - split at &

                        amp_index = biz_name.find("&")

                        if amp_index > 0:

                            # Split the name at &

                            part1 = biz_name[:amp_index].strip()

                            part2 = "&" + biz_name[amp_index + 1:].strip()

                            txt_lines.append(('HEADER', part1))

                            txt_lines.append(('HEADER', part2))

                        else:

                            txt_lines.append(('HEADER', biz_name))

                    else:

                        txt_lines.append(('HEADER', biz_name))

                    txt_lines.append(('HEADER', ''))  # Add space after store name

                else:

                    print("[DEBUG] No business name found, using default")

                    # Split default name into two lines

                    txt_lines.append(('HEADER', 'Sarhad General Store'))

                    txt_lines.append(('HEADER', 'and Wholesale Dealer'))

                    txt_lines.append(('HEADER', ''))  # Add space after store name

                if biz_addr:

                    txt_lines.append(('BODY', biz_addr))

                if biz_phone:

                    txt_lines.append(('BODY', f"Ph: {biz_phone}"))

                txt_lines.append(('BODY', ''))

                

                # Invoice info

                txt_lines.append(('BODY', f"Inv:{inv}  {date_str}  {time_str}"))  # More compact

                txt_lines.append(('BODY', f"Cashier: {cashier}"))

                txt_lines.append(('BODY', f"Payment: {payment_method}"))

                

                # Customer info

                customer = sd.get('customer')

                if customer:

                    txt_lines.append(('BODY', ''))

                    txt_lines.append(('BODY', f"Customer: {customer.get('name', '')}"))

                    # For wholesale customers, show previous and new balance around this sale

                    prev_bal = customer.get('prev_balance')

                    new_bal = customer.get('new_balance')

                    if prev_bal is not None and new_bal is not None:

                        txt_lines.append(('BODY', f"Previous Balance: Rs {prev_bal:,.2f}"))

                        txt_lines.append(('BODY', f"New Balance:      Rs {new_bal:,.2f}"))

                    else:

                        txt_lines.append(('BODY', f"Balance: {customer.get('balance', 0):,.2f}"))

                # Items header - highlighted with thicker border for products section

                border_line = '+' + '='*(NAME_W+1) + '+' + '='*(QTY_W+1) + '+' + '='*(PRICE_W+1) + '+' + '='*(AMT_W+1) + '+'

                txt_lines.append(('BODY', border_line))

                txt_lines.append(('HEADER', f"| {'ITEM NAME':^{NAME_W}} | {'QTY':^{QTY_W}} | {'PRICE':^{PRICE_W}} | {'TOTAL':^{AMT_W}} |"))

                txt_lines.append(('BODY', border_line))

                

                # Items - compact format with grid lines and light background effect

                items_list = sd.get('items', [])

                print(f"[DEBUG] Receipt printing - items count: {len(items_list)}")

                print(f"[DEBUG] Receipt printing - items: {items_list}")

                for it in items_list:

                    n = (it.get('name') or '')

                    q = int(it.get('quantity', 0))

                    prc = float(it.get('price', 0.0))

                    amt = q * prc

                    print(f"[DEBUG] Receipt printing item - name: {n}, qty: {q}, price: {prc}, total: {amt}")

                    # Truncate long names to fit in grid cell (22 chars max now)

                    name_display = n[:NAME_W] if len(n) > NAME_W else n

                    # Format with grid borders - Item Name first, then Qty

                    line = f"|{name_display:<{NAME_W}} |{q:>{QTY_W}} |{prc:>{PRICE_W}.2f} |{amt:>{AMT_W}.2f} |"

                    txt_lines.append(('BODY', line))

                    # Add separator line after each item for grid effect

                    txt_lines.append(('BODY', border_line))

                

                # Totals

                txt_lines.append(('BODY', ''))

                txt_lines.append(('BODY', f"{'Subtotal':<{lbl_w}}: {subtotal:>{AMT_W}.2f}"))

                txt_lines.append(('BODY', f"{'Discount':<{lbl_w}}: {discount_amount:>{AMT_W}.2f}"))

                # Removed tax line as requested

                # Show Change first, then Amount Paid below it

                txt_lines.append(('BODY', f"{'Change':<{lbl_w}}: {change:>{AMT_W}.2f}"))

                txt_lines.append(('BODY', f"{'Amount Paid':<{lbl_w}}: {cash:>{AMT_W}.2f}"))

                txt_lines.append(('HEADER', f"{'TOTAL':<{lbl_w}}: {final_total:>{AMT_W}.2f}"))

                

                txt_lines.append(('BODY', '=' * 42))

                

                # Urdu return policy lines

                txt_lines.append(('BODY', "ہر قسم کی چیز کی واپسی یا تبدیلی"))

                txt_lines.append(('BODY', "رسید کے بغیر نہیں ہوگی۔"))

                txt_lines.append(('BODY', ""))

                txt_lines.append(('BODY', "چارجنگ اشیاء کی تبدیلی یا واپسی ہرگز نہیں ہوگی"))

                txt_lines.append(('BODY', ""))

                txt_lines.append(('BODY', "کاؤنٹر سے جانے سے پہلے براہِ کرم"))

                txt_lines.append(('BODY', "اپنی رقم گِن لیں۔"))

                txt_lines.append(('BODY', ""))

                

                # Thank you message at the bottom

                thanks = settings.value("receipt_footer", sd.get('receipt_footer', "Thank You Come Again!")) or "Thank You Come Again!"

                if thanks:

                    txt_lines.append(('BODY', thanks))

                

                # Add REFUND RECEIPT text at bottom if this is a refund

                if is_refund:

                    txt_lines.append(('BODY', ""))

                    txt_lines.append(('HEADER', "*** REFUND RECEIPT ***"))



                force_text = str(settings.value("force_text_print", "1") or "1") == "1"

                print(f"[DEBUG] Force text print: {force_text}")

                if force_text:

                    print("[DEBUG] Creating printer object")

                    # Create printer in a cross-Qt compatible way

                    try:

                        mode_enum = getattr(QPrinter, 'PrinterMode', None)

                        if mode_enum is not None:

                            printer = QPrinter(mode_enum.HighResolution)

                        else:

                            printer = QPrinter()

                    except Exception:

                        printer = QPrinter()



                    printer.setPrinterName(printer_name)

                    print("[DEBUG] Setting printer name done")

                    # Build page size in millimeters in a way that works across Qt bindings

                    try:

                        unit_enum = getattr(QPageSize, 'Unit', None)

                        if unit_enum is not None:

                            mm_unit = unit_enum.Millimeter

                        else:

                            mm_unit = getattr(QPageSize, 'Millimeter', None)

                        if mm_unit is not None:

                            page_size = QPageSize(QSizeF(width_mm, height_mm), mm_unit)

                        else:

                            # Fallback: use a generic small page size

                            page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Point)

                        printer.setPageSize(page_size)

                        print("[DEBUG] Page size set")

                    except Exception as e:

                        print(f"[DEBUG] Error setting page size: {e}")

                        # Absolute fallback: do not override page size if enum is not available

                        pass

                    try:

                        # Set portrait orientation using proper enum

                        try:

                            from PySide6.QtGui import QPageLayout

                            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

                        except ImportError:

                            from PyQt6.QtGui import QPageLayout

                            printer.setPageOrientation(QPageLayout.Orientation.Portrait)

                        except Exception as orient_error:

                            print(f"[DEBUG] Error setting orientation: {orient_error}")

                            # Try alternative method

                            try:

                                printer.setOrientation(QPrinter.Portrait)

                            except Exception:

                                pass  # Continue without setting orientation

                        print("[DEBUG] Page orientation set")

                    except Exception as e:

                        print(f"[DEBUG] Error setting orientation: {e}")

                        pass

                    try:

                        color_enum = getattr(QPrinter, 'ColorMode', None)

                        if color_enum is not None:

                            printer.setColorMode(color_enum.GrayScale)

                        else:

                            printer.setColorMode(QPrinter.GrayScale)

                        print("[DEBUG] Color mode set")

                    except Exception as e:

                        print(f"[DEBUG] Error setting color mode: {e}")

                        pass

                    printer.setFullPage(True)

                    print("[DEBUG] Creating painter")

                    painter = QPainter()

                    print("[DEBUG] Starting painter on printer")

                    if not painter.begin(printer):

                        raise RuntimeError("Failed to start printer painter")

                    print("[DEBUG] Painter started successfully")

                    try:

                        # Set up painter with dark, bold font

                        painter.setPen(QColor(0, 0, 0))  # Pure black

                        

                        try:

                            unit_enum = getattr(QPrinter, 'Unit', None)

                            if unit_enum is not None:

                                pr = printer.pageRect(unit_enum.DevicePixel)

                            else:

                                pr = printer.pageRect()

                        except Exception:

                            pr = printer.pageRect()

                        try:

                            pw = pr.width()

                        except Exception:

                            pw = printer.width()

                        

                        # Set margins (left, right, and top) - 2-4 pixels as requested

                        margin = 24  # Increased from 20 to add 4 more pixels (2-4px extra)

                        usable_width = pw - (2 * margin)

                        

                        # Add top margin for better spacing

                        y = 64  # Increased from 60 to add 4px top margin

                        

                        # Setup fonts - make all text bold

                        store_name_font = QFont("Arial", 12)

                        store_name_font.setFixedPitch(True)

                        store_name_font.setBold(True)

                        store_name_font.setWeight(QFont.Weight.Bold)



                        header_font = QFont("Arial", 9)

                        header_font.setFixedPitch(True)

                        header_font.setBold(True)

                        header_font.setWeight(QFont.Weight.Bold)



                        body_font = QFont("Arial", 8)

                        body_font.setFixedPitch(True)

                        body_font.setBold(True)

                        body_font.setWeight(QFont.Weight.Bold)

                        

                        painter.setFont(body_font)

                        fm_body = painter.fontMetrics()

                        lh_body = fm_body.height() + 2

                        

                        painter.setFont(header_font)

                        fm_header = painter.fontMetrics()

                        lh_header = fm_header.height() + 2

                        

                        painter.setFont(store_name_font)

                        fm_store = painter.fontMetrics()

                        lh_store = fm_store.height() + 3

                        

                        y = 64  # Top margin with proper spacing

                        

                        # Draw logo if available

                        logo_drawn = False

                        if logo_path and os.path.exists(logo_path):

                            try:

                                logo_pixmap = QPixmap(logo_path)

                                if not logo_pixmap.isNull():

                                    # Scale logo to fill most of the receipt width

                                    target_width = int(pw * 0.9)

                                    scaled_logo = logo_pixmap.scaled(target_width, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                                    # Center the logo

                                    logo_x = (pw - scaled_logo.width()) // 2

                                    print(f"[DEBUG] Drawing logo at y={y}, size={scaled_logo.width()}x{scaled_logo.height()}")

                                    painter.drawPixmap(logo_x, y, scaled_logo)

                                    # CRITICAL: Update y position AFTER drawing logo

                                    old_y = y

                                    y = y + scaled_logo.height() + 70

                                    logo_drawn = True

                                    print(f"[DEBUG] Logo drawn. y moved from {old_y} to {y}")

                            except Exception as e:

                                print(f"[DEBUG] Error drawing logo: {e}")

                        

                        print(f"[DEBUG] Starting text at y={y}, logo_drawn={logo_drawn}")

                        

                        line_index = 0

                        

                        for style, t in txt_lines:

                            # Set font based on style

                            if style == 'HEADER':

                                if t and (line_index == 0 or line_index == 1):

                                    # Store name - large and centered (first two lines for wrapped names)

                                    painter.setFont(store_name_font)

                                    lh = lh_store

                                    text_width = fm_store.horizontalAdvance(t)

                                    x = (pw - text_width) // 2

                                    painter.drawText(x, y, t)

                                elif not t:

                                    # Empty line - just add space

                                    y += lh_body // 2

                                else:

                                    # Other headers - centered

                                    painter.setFont(header_font)

                                    lh = lh_header

                                    text_width = fm_header.horizontalAdvance(t)

                                    x = (pw - text_width) // 2

                                    painter.drawText(x, y, t)

                                y += lh if t else lh_body // 2

                            else:

                                # Body text - centered

                                painter.setFont(body_font)

                                lh = lh_body

                                text_width = fm_body.horizontalAdvance(t)

                                x = (pw - text_width) // 2

                                painter.drawText(x, y, t)

                                y += lh

                            

                            line_index += 1

                            

                            # Check if we need a new page

                            try:

                                page_h = pr.height()

                            except Exception:

                                page_h = printer.height()

                            if y > page_h - lh:

                                printer.newPage()

                                y = 64  # Use same top margin with 4px extra for new pages

                    finally:

                        painter.end()

                    app_logger.info(f"Receipt printed (text mode) to: {printer_name}")

                    return



            # No printers available -> fallback to PDF

            if not target_printer:

                print("[DEBUG] No printer found, creating PDF fallback")

                # Create PDF fallback

                try:

                    from PySide6.QtGui import QPageLayout

                    from PySide6.QtCore import QStandardPaths

                except ImportError:

                    from PyQt6.QtGui import QPageLayout

                    from PyQt6.QtCore import QStandardPaths

                

                # Create PDF printer

                pdf_printer = QPrinter(QPrinter.HighResolution)

                pdf_printer.setOutputFormat(QPrinter.PdfFormat)

                

                # Generate PDF filename with timestamp

                dt = datetime.now()

                timestamp = dt.strftime('%Y%m%d_%H%M%S')

                pdf_filename = f"receipt_{timestamp}.pdf"

                

                # Try to save to Documents folder, fallback to current directory

                try:

                    documents_path = QStandardPaths.writableLocation(QStandardPaths.DocumentsLocation)

                    if not documents_path:

                        documents_path = os.getcwd()

                except:

                    documents_path = os.getcwd()

                

                pdf_path = os.path.join(documents_path, pdf_filename)

                pdf_printer.setOutputFileName(pdf_path)

                

                # Set page size for PDF

                try:

                    unit_enum = getattr(QPageSize, 'Unit', None)

                    if unit_enum is not None:

                        mm_unit = unit_enum.Millimeter

                    else:

                        mm_unit = getattr(QPageSize, 'Millimeter', None)

                    if mm_unit is not None:

                        page_size = QPageSize(QSizeF(width_mm, height_mm), mm_unit)

                    else:

                        page_size = QPageSize(QSizeF(width_mm, height_mm), QPageSize.Point)

                    pdf_printer.setPageSize(page_size)

                    pdf_printer.setPageOrientation(QPageLayout.Orientation.Portrait)

                except Exception as e:

                    print(f"[DEBUG] Error setting PDF page size: {e}")

                

                # Print to PDF

                try:

                    painter = QPainter(pdf_printer)

                    painter.setPen(QColor(0, 0, 0))

                    

                    # Get page dimensions

                    try:

                        unit_enum = getattr(QPrinter, 'Unit', None)

                        if unit_enum is not None:

                            pr = pdf_printer.pageRect(unit_enum.DevicePixel)

                        else:

                            pr = pdf_printer.pageRect()

                    except Exception:

                        pr = pdf_printer.pageRect()

                    

                    try:

                        pw = pr.width()

                        page_h = pr.height()

                    except Exception:

                        pw = pdf_printer.width()

                        page_h = pdf_printer.height()

                    

                    # Setup fonts

                    store_name_font = QFont("Arial", 11)

                    store_name_font.setFixedPitch(True)

                    store_name_font.setBold(True)

                    store_name_font.setWeight(QFont.Weight.Black)

                    

                    header_font = QFont("Arial", 9)

                    header_font.setFixedPitch(True)

                    header_font.setBold(True)

                    header_font.setWeight(QFont.Weight.Black)

                    

                    body_font = QFont("Arial", 8)

                    body_font.setFixedPitch(True)

                    body_font.setBold(True)

                    body_font.setWeight(QFont.Weight.Bold)

                    

                    painter.setFont(body_font)

                    fm_body = painter.fontMetrics()

                    lh_body = fm_body.height() + 2

                    painter.setFont(header_font)

                    fm_header = painter.fontMetrics()

                    lh_header = fm_header.height() + 2

                    painter.setFont(store_name_font)

                    fm_store = painter.fontMetrics()

                    lh_store = fm_store.height() + 3

                    

                    # Print text lines to PDF

                    y = 64

                    

                    # Draw logo if available

                    logo_drawn_pdf = False

                    if logo_path and os.path.exists(logo_path):

                        try:

                            logo_pixmap = QPixmap(logo_path)

                            if not logo_pixmap.isNull():

                                target_width = int(pw * 0.9)

                                scaled_logo = logo_pixmap.scaled(target_width, 180, Qt.KeepAspectRatio, Qt.SmoothTransformation)

                                logo_x = (pw - scaled_logo.width()) // 2

                                print(f"[DEBUG] PDF Drawing logo at y={y}, size={scaled_logo.width()}x{scaled_logo.height()}")

                                painter.drawPixmap(logo_x, y, scaled_logo)

                                old_y = y

                                y = y + scaled_logo.height() + 70

                                logo_drawn_pdf = True

                                print(f"[DEBUG] PDF Logo drawn. y moved from {old_y} to {y}")

                        except Exception as e:

                            print(f"[DEBUG] Error drawing PDF logo: {e}")

                    

                    print(f"[DEBUG] PDF Starting text at y={y}, logo_drawn={logo_drawn_pdf}")

                    

                    line_index = 0

                    

                    for style, t in txt_lines:

                        if style == 'HEADER':

                            if t and (line_index == 0 or line_index == 1):

                                painter.setFont(store_name_font)

                                lh = lh_store

                                text_width = fm_store.horizontalAdvance(t)

                                x = (pw - text_width) // 2

                                painter.drawText(x, y, t)

                            elif not t:

                                y += lh_body // 2

                            else:

                                painter.setFont(header_font)

                                lh = lh_header

                                text_width = fm_header.horizontalAdvance(t)

                                x = (pw - text_width) // 2

                                painter.drawText(x, y, t)

                            y += lh if t else lh_body // 2

                        else:

                            painter.setFont(body_font)

                            lh = lh_body

                            text_width = fm_body.horizontalAdvance(t)

                            x = (pw - text_width) // 2

                            painter.drawText(x, y, t)

                            y += lh

                        

                        line_index += 1

                        

                        # Check for new page

                        if y > page_h - lh:

                            pdf_printer.newPage()

                            y = 64

                    

                    painter.end()

                    

                    # Show success message

                    msg = QMessageBox(self)

                    msg.setIcon(QMessageBox.Information)

                    msg.setWindowTitle("PDF Created")

                    msg.setText(f"No printer found. Receipt saved as PDF:\n\n{pdf_path}\n\nWould you like to open the PDF file?")

                    msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)

                    result = msg.exec()

                    

                    # Open PDF if user clicked Yes

                    if result == QMessageBox.Yes:

                        try:

                            import subprocess

                            import platform

                            if platform.system() == 'Windows':

                                os.startfile(pdf_path)

                            elif platform.system() == 'Darwin':  # macOS

                                subprocess.run(['open', pdf_path])

                            else:  # Linux

                                subprocess.run(['xdg-open', pdf_path])

                        except Exception as e:

                            print(f"[DEBUG] Error opening PDF: {e}")

                    

                    app_logger.info(f"Receipt saved as PDF: {pdf_path}")

                    return

                    

                except Exception as pdf_error:

                    print(f"[DEBUG] Error creating PDF: {pdf_error}")

                    # If PDF creation fails, show error

                    msg = QMessageBox(self)

                    msg.setIcon(QMessageBox.Critical)

                    msg.setWindowTitle("Print Error")

                    msg.setText(f"No printers detected and PDF creation failed.\n\nAvailable printers: {names}\n\nPDF Error: {str(pdf_error)}\n\nPlease configure a printer in Settings→Printing.")

                    msg.setStandardButtons(QMessageBox.Ok)

                    msg.exec()

                    return



        except Exception as e:

            msg = QMessageBox(self)

            msg.setIcon(QMessageBox.Critical)

            msg.setWindowTitle("Print Error")

            msg.setText(f"Failed to print receipt: {str(e)}")

            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec()



    def print_and_close(self):

        """Print the receipt and close dialog"""

        self.print_receipt()

        self.accept()



    def eventFilter(self, obj, event):

        """Handle Enter key in the preview dialog to print & close in one step."""

        try:

            # Resolve cross-Qt KeyPress type

            try:

                key_type_enum = getattr(QEvent, 'Type', None)

                if key_type_enum is not None:

                    KEY_PRESS = key_type_enum.KeyPress

                else:

                    KEY_PRESS = getattr(QEvent, 'KeyPress', None)

            except Exception:

                KEY_PRESS = getattr(QEvent, 'KeyPress', None)

            if KEY_PRESS is None:

                KEY_PRESS = 6



            if event.type() == KEY_PRESS:

                try:

                    from PySide6.QtCore import Qt

                except ImportError:

                    from PyQt6.QtCore import Qt

                if event.key() in (Qt.Key_Return, Qt.Key_Enter):

                    # Single Enter prints and closes the preview

                    self.print_and_close()

                    return True

            return super().eventFilter(obj, event)

        except Exception:

            return super().eventFilter(obj, event)





class SalesWidget(QWidget):

    def __init__(self, controller, current_user=None):

        super().__init__()

        self.controller = controller

        self.current_user = current_user

        self.current_cart = []

        self.tax_rate = 8.0  # Default tax rate

        self.is_refund_mode = False

        self.refund_of_sale_id = None

        self._refund_source_sale = None

        # Internal buffer for global barcode scanning (works even when barcode field not focused)

        self._barcode_buffer = ""

        # Timestamp of last successful barcode add to suppress trailing Enter from scanners

        self._last_barcode_add_ts = 0.0

        # Timestamp of last buffered barcode key to detect timeouts

        self._barcode_last_ts = 0.0

        self.setup_ui()

        self.load_tax_rate()

        try:

            self.update_totals()

        except Exception:

            pass

        self.load_customers()  # Load customers after UI is set up

        self._bind_shortcuts()

        

        # Connect to customer sync signals

        try:

            from pos_app.views.customers import CustomersWidget

            if hasattr(self.controller, 'customers_widget'):

                customers_widget = self.controller.customers_widget

                # Connect to customer added signal if it exists

                if hasattr(customers_widget, 'customer_added'):

                    customers_widget.customer_added.connect(self.refresh_customers)

                    print("[SalesWidget] Connected to customer sync signals")

        except Exception as e:

            print(f"[SalesWidget] Could not connect to customer sync: {e}")

        

        # Track which widget has focus for arrow key navigation

        self._focus_widget = None

        self._editing_price = False

        self._edited_row = None



        # Install event filter at application level so we see scanner keys and

        # navigation arrows even when focus is on child widgets.

        try:

            try:

                from PySide6.QtWidgets import QApplication as _QApplication

            except ImportError:

                from PyQt6.QtWidgets import QApplication as _QApplication

            app = _QApplication.instance()

            if app is not None:

                app.installEventFilter(self)

            else:

                # Fallback: at least watch events on this widget

                self.installEventFilter(self)

        except Exception:

            # Final fallback in case anything above fails

            self.installEventFilter(self)



        # Connect to settings changed signal if available

        try:

            from .settings import SettingsWidget

            SettingsWidget.settings_updated.connect(self.on_settings_updated)

        except (ImportError, AttributeError):

            pass

    

    def _is_worker_user(self):

        """Check if current user is a worker (not admin)"""

        try:

            if self.current_user and hasattr(self.current_user, 'is_admin'):

                return not self.current_user.is_admin

            return False  # Default to admin if no user info

        except Exception:

            return False  # Default to admin if error



    def showEvent(self, event):

        """Focus the Direct Sale Page when it opens so shortcuts can be used"""

        super().showEvent(event)

        # Focus the product search field when the page opens

        try:

            from PySide6.QtCore import QTimer

        except ImportError:

            from PyQt6.QtCore import QTimer

        QTimer.singleShot(100, self._focus_on_open)

        

    def _focus_on_open(self):

        """Focus the appropriate widget when page opens"""

        try:

            # Ensure the widget is properly focused and ready for shortcuts

            if hasattr(self, 'product_search') and self.product_search:

                self.product_search.setFocus()

                self.product_search.selectAll()  # Select all text for easy replacement

                _dprint("[DEBUG] Focused product search field for shortcuts")

            elif hasattr(self, 'barcode_input') and self.barcode_input:

                self.barcode_input.setFocus()

                self.barcode_input.selectAll()  # Select all text for easy replacement

                _dprint("[DEBUG] Focused barcode input field for shortcuts")

            

            # Also ensure cart table is ready for navigation

            if hasattr(self, 'cart_table') and self.cart_table:

                # Make sure cart table can receive focus

                self.cart_table.setFocusPolicy(Qt.StrongFocus)

                _dprint("[DEBUG] Cart table focus policy set for shortcuts")

                

        except Exception as e:

            _dprint(f"[DEBUG] Error in _focus_on_open: {e}")

    

    def _refocus_search(self):

        """Keep focus on search field after adding product - used by add_first_search_result"""

        try:

            if hasattr(self, 'product_search') and self.product_search:

                # Clear the search field

                self.product_search.clear()

                # Set focus back to search

                self.product_search.setFocus()

                _dprint("[DEBUG] Refocused on product search field")

        except Exception as e:

            _dprint(f"[DEBUG] Error in _refocus_search: {e}")



    def _get_discount_amount_value(self) -> float:

        try:

            w = getattr(self, 'discount_amount', None)

            if w is not None:

                return float(w.value())

        except Exception:

            pass

        try:

            w = getattr(self, 'discount_amount_input', None)

            if w is not None:

                txt = (w.text() or '').strip()

                return float(txt) if txt else 0.0

        except Exception:

            pass

        return 0.0



    def _set_discount_amount_value(self, value: float):

        try:

            v = float(value or 0.0)

        except Exception:

            v = 0.0

        try:

            w = getattr(self, 'discount_amount', None)

            if w is not None:

                try:

                    w.blockSignals(True)

                except Exception:

                    pass

                w.setValue(v)

                try:

                    w.blockSignals(False)

                except Exception:

                    pass



                try:

                    self.update_cart_table()

                except Exception:

                    pass

                try:

                    self.update_totals()

                except Exception:

                    pass

                return

        except Exception:

            pass

        try:

            w = getattr(self, 'discount_amount_input', None)

            if w is not None:

                w.setText(str(v))

                try:

                    self.update_cart_table()

                except Exception:

                    pass

                try:

                    self.update_totals()

                except Exception:

                    pass

                return

        except Exception:

            pass



    def _focus_discount_widget(self):

        """Focus the active discount widget (supports both QDoubleSpinBox and QLineEdit variants)."""

        try:

            w = getattr(self, 'discount_amount', None)

            if w is not None:

                w.setFocus()

                try:

                    w.selectAll()

                except Exception:

                    pass

                return True

        except Exception:

            pass

        try:

            w = getattr(self, 'discount_amount_input', None)

            if w is not None:

                w.setFocus()

                try:

                    w.selectAll()

                except Exception:

                    pass

                return True

        except Exception:

            pass

        return False



    def _handle_ctrl_r(self, restore_all=False):

        """Handle Ctrl+R shortcut - in refund mode, mark/unmark selected item for refund



        Args:

            restore_all: If True (Ctrl+Shift+R), restore all items to cart for marking more items

        """

        try:

            print(f"[SHORTCUT] Ctrl+R: Handler called (restore_all={restore_all})")



            # Check if in refund mode

            if getattr(self, 'is_refund_mode', False):

                print("[SHORTCUT] Ctrl+R: In refund mode")



                # Initialize marked items tracking if not exists

                if not hasattr(self, '_refund_marked_items'):

                    self._refund_marked_items = set()

                if not hasattr(self, '_refund_all_items'):

                    # Store all original items from the refund invoice

                    self._refund_all_items = [item.copy() for item in self.current_cart]

                    print(f"[SHORTCUT] Ctrl+R: Stored {len(self._refund_all_items)} original items")



                # If restore_all is True (Ctrl+Shift+R), restore all items to cart

                if restore_all:

                    print("[SHORTCUT] Ctrl+Shift+R: Restoring all items to cart")

                    self.current_cart = [item.copy() for item in self._refund_all_items]

                    self._refund_marked_items.clear()  # Clear markings

                    self.update_cart_table()

                    self.update_totals()

                    print(f"[SHORTCUT] Ctrl+Shift+R: Restored {len(self.current_cart)} items. Markings cleared.")

                    return



                # Get currently selected row

                selected_row = -1

                if hasattr(self, 'cart_table') and self.cart_table:

                    selected_row = self.cart_table.currentRow()

                    print(f"[SHORTCUT] Ctrl+R: Selected row = {selected_row}")



                if selected_row >= 0 and selected_row < len(self.current_cart):

                    # Get the actual item from current cart

                    selected_item = self.current_cart[selected_row]

                    item_id = selected_item.get('id')  # Cart items use 'id' not 'product_id'



                    print(f"[SHORTCUT] Ctrl+R: Selected item id = {item_id}")



                    # Toggle marking for this item

                    if item_id in self._refund_marked_items:

                        # Unmark this item

                        self._refund_marked_items.remove(item_id)

                        print(f"[SHORTCUT] Ctrl+R: Unmarked item (product_id={item_id})")

                    else:

                        # Mark this item for refund

                        self._refund_marked_items.add(item_id)

                        print(f"[SHORTCUT] Ctrl+R: Marked item (product_id={item_id}) for refund")



                    print(f"[SHORTCUT] Ctrl+R: Currently marked product IDs: {self._refund_marked_items}")



                    # SIMPLIFIED: Keep all items in cart, just update display to show which are marked

                    # The actual filtering will happen when processing the refund

                    self.update_cart_table()

                    self.update_totals()

                    print(f"[SHORTCUT] Ctrl+R: {len(self._refund_marked_items)} item(s) marked for refund")

                    print("[SHORTCUT] Ctrl+R: Press Ctrl+Enter to complete refund (only marked items will be refunded)")

                else:

                    print(f"[SHORTCUT] Ctrl+R: No valid item selected (row {selected_row}, cart size {len(self.current_cart or [])})")

            else:

                print("[SHORTCUT] Ctrl+R: Not in refund mode - ignoring")

        except Exception as e:

            print(f"[DEBUG] Error handling Ctrl+R: {e}")

            import traceback

            traceback.print_exc()

    

    def _focus_refund_invoice(self):

        try:

            w = getattr(self, 'refund_invoice_input', None)

            if w is not None:

                w.setFocus()

                try:

                    w.selectAll()

                except Exception:

                    pass

                return True

        except Exception:

            pass

        return False



    def _handle_ctrl_enter_complete_sale(self):

        """Handle Ctrl+Enter shortcut - complete sale from anywhere"""

        try:

            print("[SHORTCUT] Ctrl+Enter: Attempting to complete sale")

            

            # Check if cart has items

            if not hasattr(self, 'current_cart') or not self.current_cart or len(self.current_cart) == 0:

                print("[SHORTCUT] Ctrl+Enter: Cart is empty - cannot complete sale")

                return

            

            # Check if recently added product (prevent accidental completion)

            try:

                import time

                if (time.monotonic() - getattr(self, '_last_barcode_add_ts', 0.0)) < 0.5:

                    print("[SHORTCUT] Ctrl+Enter: Suppressing - recent product added")

                    return

            except Exception:

                pass

            

            # Complete the sale

            print("[SHORTCUT] Ctrl+Enter: Processing sale...")

            # For refunds, don't print receipt. For normal sales, print receipt.

            is_refund = getattr(self, 'is_refund_mode', False)

            print(f"[SHORTCUT] Ctrl+Enter: is_refund_mode={is_refund}, print_receipt={not is_refund}")

            self.process_sale(print_receipt=not is_refund)

            

        except Exception as e:

            print(f"[SHORTCUT] Ctrl+Enter: Error completing sale - {e}")



    def _handle_ctrl_shift_enter_complete_sale_with_receipt(self):

        """Handle Ctrl+Shift+Enter shortcut - complete sale and print receipt"""

        try:

            print("[SHORTCUT] Ctrl+Shift+Enter: Attempting to complete sale with receipt")

            

            # Check if cart has items

            if not hasattr(self, 'current_cart') or not self.current_cart or len(self.current_cart) == 0:

                print("[SHORTCUT] Ctrl+Shift+Enter: Cart is empty - cannot complete sale")

                return

            

            # Check if recently added product (prevent accidental completion)

            try:

                import time

                if (time.monotonic() - getattr(self, '_last_barcode_add_ts', 0.0)) < 0.5:

                    print("[SHORTCUT] Ctrl+Shift+Enter: Suppressing - recent product added")

                    return

            except Exception:

                pass

            

            # Complete the sale with receipt printing

            print("[SHORTCUT] Ctrl+Shift+Enter: Processing sale with receipt...")

            self.process_sale(print_receipt=True)

            

        except Exception as e:

            print(f"[SHORTCUT] Ctrl+Shift+Enter: Error completing sale - {e}")



    def _calculate_totals(self):

        try:

            items_count = sum(float(item.get('quantity', 0) or 0) for item in (self.current_cart or []))

        except Exception:

            items_count = 0

        try:

            if getattr(self, 'is_refund_mode', False):

                subtotal = sum(

                    float(item.get('quantity', 0) or 0)

                    * float(item.get('refund_unit_subtotal', item.get('price', 0.0)) or 0.0)

                    for item in (self.current_cart or [])

                )

            else:

                subtotal = sum(

                    float(item.get('quantity', 0) or 0)

                    * float(item.get('price', 0.0) or 0.0)

                    for item in (self.current_cart or [])

                )

        except Exception:

            subtotal = 0.0

        try:

            total_cost = sum(float(item.get('quantity', 0) or 0) * float(item.get('purchase_price', 0.0) or 0.0) for item in (self.current_cart or []))

        except Exception:

            total_cost = 0.0



        discount = self._get_discount_amount_value()

        try:

            discount = min(float(discount or 0.0), float(subtotal or 0.0))

        except Exception:

            discount = 0.0



        try:

            taxable_amount = float(subtotal or 0.0) - float(discount or 0.0)

        except Exception:

            taxable_amount = 0.0



        try:

            tax = float(taxable_amount) * (float(getattr(self, 'tax_rate', 0.0) or 0.0) / 100.0)

        except Exception:

            tax = 0.0



        total = float(taxable_amount) + float(tax or 0.0)

        profit = float(subtotal or 0.0) - float(total_cost or 0.0)

        return items_count, subtotal, total_cost, profit, discount, tax, total



    def setup_ui(self):

        """Create a completely modern, professional POS interface"""

        main_layout = QVBoxLayout(self)

        main_layout.setContentsMargins(0, 0, 0, 0)

        main_layout.setSpacing(0)



        # Apply modern global styling with improved contrast

        self.setStyleSheet("""

            QWidget {

                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,

                    stop:0 #f8fafc, stop:1 #f1f5f9);

                font-family: 'Segoe UI', 'Arial', sans-serif;

                color: #1e293b;

            }

            QLabel {

                color: #1e293b;

                background: transparent;

            }

            QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 8px 12px;

                font-size: 14px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {

                border-color: #3b82f6;

                background: Qt.white;

                color: #1e293b;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

            QPushButton {

                color: #1e293b;

                background: Qt.white;

                border: 1px solid #e2e8f0;

                border-radius: 6px;

                padding: 8px 16px;

                font-size: 14px;

                font-weight: 500;

            }

            QPushButton:hover {

                background: #f1f5f9;

                color: #1e293b;

            }

            QTableWidget {

                background: Qt.white;

                color: #1e293b;

                gridline-color: #e2e8f0;

            }

            QTableWidget::item {

                color: #1e293b;

                background: Qt.white;

                padding: 8px 12px;

            }

            QTableWidget::item:selected {

                background: #eff6ff;

                color: #1e40af;

            }

            QHeaderView::section {

                background: #f8fafc;

                color: #374151;

                font-weight: 600;

                border: none;

                border-bottom: 1px solid #e2e8f0;

                padding: 12px;

            }

        """)



        # Create scrollable main content

        scroll_area = QScrollArea()

        scroll_area.setWidgetResizable(True)

        try:

            # PyQt6

            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        except AttributeError:

            # PySide6

            scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        scroll_area.setStyleSheet("""

            QScrollArea {

                border: none;

                background: transparent;

            }

            QScrollBar:vertical {

                background: #f1f5f9;

                width: 12px;

                border-radius: 6px;

            }

            QScrollBar::handle:vertical {

                background: #cbd5e1;

                border-radius: 6px;

                min-height: 20px;

            }

            QScrollBar::handle:vertical:hover {

                background: #94a3b8;

            }

        """)



        # Create content widget

        content_widget = QWidget()

        content_layout = QVBoxLayout(content_widget)

        content_layout.setContentsMargins(16, 16, 16, 16)

        content_layout.setSpacing(16)



        # === HEADER SECTION ===

        self.create_modern_header(content_layout)



        # === MAIN CONTENT AREA ===

        main_content = QVBoxLayout()

        main_content.setSpacing(12)

        main_content.setContentsMargins(0, 0, 0, 0)



        # Top - Shopping Cart & Product Search (full width)

        self.create_cart_section(main_content)



        # Bottom - Checkout & Summary (full width)

        self.create_checkout_section(main_content)



        content_layout.addLayout(main_content)



        # Attach content to scroll area and main layout

        scroll_area.setWidget(content_widget)

        main_layout.addWidget(scroll_area)



    def create_modern_header(self, parent_layout):

        """Minimal placeholder header for Sales page (no visible hero block)."""

        header_frame = QFrame()

        header_frame.setStyleSheet("""

            QFrame {

                background: transparent;

                border: none;

                margin: 0px;

                padding: 0px;

            }

        """)



        header_layout = QVBoxLayout(header_frame)

        header_layout.setContentsMargins(0, 0, 0, 0)

        header_layout.setSpacing(0)



        spacer = QWidget()

        spacer.setFixedHeight(0)

        header_layout.addWidget(spacer)



        parent_layout.addWidget(header_frame)



    def create_cart_section(self, parent_layout):

        """Create the main shopping cart section with product search"""

        # Cart container

        cart_container = QWidget()

        cart_container.setMinimumWidth(0)

        try:

            from PySide6.QtWidgets import QSizePolicy

        except Exception:

            try:

                from PyQt6.QtWidgets import QSizePolicy

            except Exception:

                QSizePolicy = None

        try:

            if QSizePolicy is not None:

                cart_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        except Exception:

            pass



        cart_layout = QVBoxLayout(cart_container)

        cart_layout.setContentsMargins(0, 0, 0, 0)

        cart_layout.setSpacing(12)



        # Product Search Section

        search_frame = QFrame()

        search_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                padding: 6px 12px 8px 12px;

                border: 1px solid #e2e8f0;

            }

        """)

        search_frame.setMaximumHeight(200)  # Reduced height



        search_layout = QVBoxLayout(search_frame)

        search_layout.setContentsMargins(0, 0, 0, 0)

        search_layout.setSpacing(8)



        # Search header (empty for now, refund field moved below)

        header_layout = QHBoxLayout()

        header_layout.setContentsMargins(0, 0, 0, 0)

        header_layout.setSpacing(12)

        header_layout.addStretch()



        # Ctrl+R shortcuts are now bound in _bind_shortcuts() to avoid conflicts



        search_layout.addLayout(header_layout)



        self.refund_sale_info_label = QLabel("")

        self.refund_sale_info_label.setStyleSheet("font-size: 12px; color: #475569; font-weight: 600;")

        try:

            self.refund_sale_info_label.setWordWrap(True)

        except Exception:

            pass



        search_body_layout = QHBoxLayout()

        search_body_layout.setContentsMargins(0, 0, 0, 0)

        search_body_layout.setSpacing(12)



        search_left = QWidget()

        search_left_layout = QVBoxLayout(search_left)

        search_left_layout.setContentsMargins(0, 0, 0, 0)

        search_left_layout.setSpacing(4)  # Reduced from 6 to 4



        # Create a horizontal layout for title and refund field

        title_refund_layout = QHBoxLayout()

        title_refund_layout.setContentsMargins(0, 0, 0, 0)

        title_refund_layout.setSpacing(10)  # Reduced from 12 to 10

        

        # Refund invoice ID input (left side of title)

        refund_label = QLabel("Refund Invoice ID:")

        refund_label.setStyleSheet("font-size: 12px; color: #64748b; font-weight: 600;")

        title_refund_layout.addWidget(refund_label)



        self.refund_invoice_input = QLineEdit()

        self.refund_invoice_input.setPlaceholderText("Enter invoice ID to refund...")

        self.refund_invoice_input.setMinimumWidth(380)

        self.refund_invoice_input.setMaximumWidth(480)

        self.refund_invoice_input.setMinimumHeight(36)  # Increased from 32 to 36

        self.refund_invoice_input.setReadOnly(False)

        self.refund_invoice_input.setEnabled(True)

        try:

            from PySide6.QtWidgets import QSizePolicy

        except Exception:

            try:

                from PyQt6.QtWidgets import QSizePolicy

            except Exception:

                QSizePolicy = None

        try:

            if QSizePolicy is not None:

                self.refund_invoice_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        except Exception:

            pass

        self.refund_invoice_input.setStyleSheet("""

            QLineEdit {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 8px 12px;

                font-size: 13px;

                background: white;

                color: #1e293b;

                selection-background-color: #3b82f6;

                min-width: 200px;

            }

            QLineEdit:focus {

                border: 2px solid #3b82f6;

                background: white;

            }

            QLineEdit:hover {

                border: 2px solid #cbd5e1;

            }

            QLineEdit::placeholder {

                color: #94a3b8;

                font-size: 12px;

            }

        """)

        # Install event filter to capture Ctrl+R shortcut when refund input has focus

        try:

            self.refund_invoice_input.installEventFilter(self)

        except Exception:

            pass

        # Prevent auto-focus on refund field - only focus on click

        self.refund_invoice_input.setFocusPolicy(Qt.ClickFocus)

        self.refund_invoice_input.returnPressed.connect(self.load_refund_invoice)

        self.refund_invoice_input.setCursorPosition(0)

        self.refund_invoice_input.setAlignment(Qt.AlignVCenter)

        title_refund_layout.addWidget(self.refund_invoice_input)

        

        # Exit Refund Mode button (visible only in refund mode)

        self.exit_refund_btn = QPushButton("Exit Refund Mode")

        self.exit_refund_btn.setStyleSheet("""

            QPushButton {

                background-color: #ef4444;

                color: white;

                border: none;

                border-radius: 6px;

                padding: 8px 16px;

                font-size: 12px;

                font-weight: 600;

            }

            QPushButton:hover {

                background-color: #dc2626;

            }

            QPushButton:pressed {

                background-color: #b91c1c;

            }

        """)

        self.exit_refund_btn.clicked.connect(self.exit_refund_mode)

        self.exit_refund_btn.setVisible(False)  # Hidden by default

        title_refund_layout.addWidget(self.exit_refund_btn)

        

        # No "Add to Cart" heading - removed for cleaner layout

        

        search_left_layout.addLayout(title_refund_layout)



        search_left_layout.addWidget(self.refund_sale_info_label)



        # Product search input with barcode support

        search_input_layout = QHBoxLayout()

        search_input_layout.setContentsMargins(0, 0, 0, 0)

        search_input_layout.setSpacing(10)



        self.product_search = QLineEdit()

        self.product_search.setPlaceholderText("Search product name or scan barcode...")

        self.product_search.setStyleSheet("""

            QLineEdit {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 12px 16px;

                font-size: 16px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QLineEdit:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        # Debounce search to avoid lag with fast barcode scanners

        self._search_timer = QTimer(self)

        self._search_timer.setSingleShot(True)

        self._search_timer.setInterval(300)  # 300ms debounce delay for better performance

        self._search_timer.timeout.connect(self.search_products)

        self.product_search.textChanged.connect(self._on_search_text_changed)

        self.product_search.returnPressed.connect(self.add_first_search_result)

        try:

            self.product_search.installEventFilter(self)

        except Exception:

            pass



        self.barcode_input = self.product_search



        add_product_btn = QPushButton("➕ Add Product")

        add_product_btn.setStyleSheet("""

            QPushButton {

                background: #10b981;

                color: Qt.white;

                border: none;

                border-radius: 8px;

                padding: 12px 24px;

                font-size: 16px;

                font-weight: 600;

                min-width: 140px;

            }

            QPushButton:hover {

                background: #059669;

            }

        """)

        add_product_btn.clicked.connect(self.show_product_selector)



        search_input_layout.addWidget(self.product_search, 1)

        search_input_layout.addWidget(add_product_btn)

        search_left_layout.addLayout(search_input_layout, 0)

        search_left_layout.addSpacing(6)

        

        # Unified suggestions list (shows both product and barcode matches)

        self.search_suggestions_list = QListWidget()

        self.search_suggestions_list.setMaximumHeight(400)  # Increased to show more items

        self.search_suggestions_list.setMinimumHeight(0)

        self.search_suggestions_list.setStyleSheet("""

            QListWidget {

                border: 1px solid #e2e8f0;

                border-radius: 6px;

                background: Qt.white;

                font-size: 13px;

                margin: 0;

                padding: 0;

            }

            QListWidget::item:hover {

                background: #f0f9ff;

            }

            QListWidget::item:selected {

                background: #3b82f6;

                color: Qt.white;

            }

        """)

        try:

            # Ensure list can take focus for keyboard selection

            self.search_suggestions_list.setFocusPolicy(Qt.StrongFocus)

            self.search_suggestions_list.setSelectionMode(self.search_suggestions_list.SingleSelection)

            self.search_suggestions_list.installEventFilter(self)

        except Exception:

            pass

        self.search_suggestions_list.itemDoubleClicked.connect(self._on_suggestion_selected)

        self.search_suggestions_list.itemActivated.connect(self._on_suggestion_selected)

        # Connect Enter key on suggestions list to add product

        try:

            self.search_suggestions_list.installEventFilter(self)

        except Exception:

            pass

        search_left_layout.addWidget(self.search_suggestions_list, 0)



        self.barcode_suggestions_list = self.search_suggestions_list



        # Cart summary (moved back near search area)

        summary_frame = QFrame()

        summary_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

                padding: 10px;

            }

        """)

        summary_layout = QVBoxLayout(summary_frame)

        summary_layout.setContentsMargins(0, 0, 0, 0)

        summary_layout.setSpacing(4)



        summary_title = QLabel("📊 Cart Summary")

        summary_title.setStyleSheet("font-size: 14px; font-weight: 900; color: #1e293b; margin: 0; padding: 0;")

        summary_layout.addWidget(summary_title)



        self.cart_items_label = QLabel("Items: 0")

        self.cart_subtotal_label = QLabel("Subtotal: Rs 0.00")

        self.cart_tax_label = QLabel("Tax (0%): Rs 0.00")

        self.cart_total_label = QLabel("Final Total: Rs 0.00")



        for label in [self.cart_items_label, self.cart_subtotal_label, self.cart_tax_label]:

            label.setStyleSheet("font-size: 12px; color: #6b7280; margin: 0; padding: 0;")



        self.cart_total_label.setStyleSheet("""

            font-size: 13px;

            font-weight: 900;

            color: #1e293b;

            border-top: 1px solid #e2e8f0;

            padding-top: 6px;

            margin-top: 6px;

        """)



        summary_layout.addWidget(self.cart_items_label)

        summary_layout.addWidget(self.cart_subtotal_label)

        summary_layout.addWidget(self.cart_tax_label)

        summary_layout.addWidget(self.cart_total_label)

        summary_layout.addStretch(1)



        search_body_layout.addWidget(search_left, 2)

        search_body_layout.addWidget(summary_frame, 1)

        search_layout.addLayout(search_body_layout)



        cart_layout.addWidget(search_frame)



        # Shopping Cart Section

        cart_frame = QFrame()

        cart_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

                padding: 8px;

            }

        """)



        cart_section_layout = QVBoxLayout(cart_frame)

        cart_section_layout.setSpacing(1)  # Reduced from 2 to 1

        cart_section_layout.setContentsMargins(0, 0, 0, 0)



        # Cart header

        cart_header_layout = QHBoxLayout()

        cart_header_layout.setContentsMargins(0, 2, 0, 2)  # Minimal 2px margins



        cart_title = QLabel("🛒 Shopping Cart")

        cart_title.setStyleSheet("""

            font-size: 13px;

            margin: 0px;

            padding: 0px;

            QPushButton {

                background: #fef2f2;

                color: #dc2626;

                border: none;

                border-radius: 8px;

                padding: 8px 12px;

                font-weight: 600;

            }

            QPushButton:hover {

                background: #fee2e2;

            }

        """)

        # Clear Cart button (define before use)

        self.clear_cart_btn = QPushButton("🗑️ Clear All")

        self.clear_cart_btn.setStyleSheet("""

            QPushButton {

                background: #fef2f2;

                color: #dc2626;

                border: none;

                border-radius: 8px;

                padding: 8px 12px;

                font-weight: 600;

            }

            QPushButton:hover {

                background: #fee2e2;

            }

        """)

        self.clear_cart_btn.clicked.connect(self.clear_cart)



        cart_header_layout.addWidget(cart_title)

        cart_header_layout.addStretch()

        cart_header_layout.addWidget(self.clear_cart_btn)

        cart_section_layout.addLayout(cart_header_layout)



        # Enhanced Cart table with purchase/sale prices

        # Cart table will be created as custom CartTableWidget below



        # Cart table styling and configuration will be applied after creating the custom widget

        

        # Install delegate to auto-select text when editing starts

        try:

            from PySide6.QtWidgets import QStyledItemDelegate

            from PySide6.QtCore import QEvent

        except ImportError:

            from PyQt6.QtWidgets import QStyledItemDelegate

            from PyQt6.QtCore import QEvent

        

        # Create a custom cart table class for better keyboard handling

        class CartTableWidget(QTableWidget):

            def __init__(self, parent=None):

                super().__init__(parent)

            

            def keyPressEvent(self, event):

                """Handle arrow key navigation to stay within editable columns"""

                # Get current position

                current_row = self.currentRow()

                current_col = self.currentColumn()

                

                # Handle Delete key to remove selected row

                if event.key() == Qt.Key_Delete:

                    _dprint(f"[DEBUG] Delete key pressed in CartTableWidget at row {current_row}")

                    # Get parent SalesWidget to call remove_cart_item

                    parent_widget = self.parent()

                    while parent_widget and not hasattr(parent_widget, 'remove_cart_item'):

                        parent_widget = parent_widget.parent()

                    if parent_widget and current_row >= 0:

                        parent_widget.remove_cart_item(current_row)

                    return

                

                # Handle arrow keys

                if event.key() in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):

                    # Check if we're in an editable column

                    if current_col in (1, 3):  # QTY or Sale Price columns

                        new_row, new_col = current_row, current_col

                        

                        if event.key() == Qt.Key_Left:

                            # From Sale Price (3) go to QTY (1)

                            if current_col == 3:

                                new_col = 1

                            else:

                                return  # Don't allow left from QTY

                        elif event.key() == Qt.Key_Right:

                            # From QTY (1) go to Sale Price (3)

                            if current_col == 1:

                                new_col = 3

                            else:

                                return  # Don't allow right from Sale Price

                        elif event.key() == Qt.Key_Up:

                            # Move up but stay in same column

                            new_row = max(0, current_row - 1)

                        elif event.key() == Qt.Key_Down:

                            # Move down but stay in same column

                            new_row = min(self.rowCount() - 1, current_row + 1)

                        

                        # Navigate to the new cell

                        if new_row != current_row or new_col != current_col:

                            self.setCurrentCell(new_row, new_col)

                            # Start editing the new cell immediately

                            if new_col in (1, 3):

                                item = self.item(new_row, new_col)

                                if item:

                                    # Use QTimer to ensure editing starts after navigation

                                    QTimer.singleShot(0, lambda: self.editItem(item))

                            return

                    else:

                        # If not in editable column, find nearest editable column

                        if event.key() == Qt.Key_Left:

                            target_col = 1

                        elif event.key() == Qt.Key_Right:

                            target_col = 3

                        else:

                            # For up/down, stay in current column but move to nearest editable

                            target_col = 1 if current_col < 1 else 3

                        

                        # Move to target column and start editing

                        if target_col < self.columnCount():

                            self.setCurrentCell(current_row, target_col)

                            item = self.item(current_row, target_col)

                            if item:

                                QTimer.singleShot(0, lambda: self.editItem(item))

                            return

                

                # Let parent handle other keys

                super().keyPressEvent(event)

        

        # Replace the cart table with our custom one

        self.cart_table = CartTableWidget(self)

        self.cart_table.setColumnCount(10)

        

        # Set headers based on user role

        if self._is_worker_user():

            # Worker user - hide purchase price and profit columns

            self.cart_table.setHorizontalHeaderLabels([

                "Product Name", "Qty", "", "Sale Price", "Total", "", "Remove", "Bought Qty", "Stock", "Item Disc"

            ])

            # Hide purchase price (column 2) and profit (column 5) columns

            self.cart_table.setColumnHidden(2, True)  # Purchase Price

            self.cart_table.setColumnHidden(5, True)  # Profit

        else:

            # Admin user - show all columns

            self.cart_table.setHorizontalHeaderLabels([

                "Product Name", "Qty", "Purchase Price", "Sale Price", "Total", "Profit", "Remove", "Bought Qty", "Stock", "Item Disc"

            ])

        

        class SelectAllDelegate(QStyledItemDelegate):

            def __init__(self, parent=None):

                super().__init__(parent)

                _dprint("[DEBUG] SelectAllDelegate created")

                self._table = None

            

            def createEditor(self, parent, option, index):

                _dprint(f"[DEBUG] createEditor called for column {index.column()}")

                # Create a QLineEdit editor explicitly for better control

                from PySide6.QtWidgets import QLineEdit

                try:

                    from PySide6.QtCore import Qt, QEvent

                except ImportError:

                    from PyQt6.QtCore import Qt, QEvent

                

                editor = QLineEdit(parent)

                _dprint(f"[DEBUG] QLineEdit editor created: {editor}")

                

                # Make sure editor allows typing

                editor.setReadOnly(False)

                _dprint(f"[DEBUG] Editor readOnly set to False")

                

                # Set alignment for numbers

                if index.column() in (1, 3):  # QTY (column 1) or SALE PRICE (column 3)

                    editor.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

                

                # Store table reference and index for event filter

                self._table = parent.parent() if hasattr(parent, 'parent') else None

                self._current_row = index.row()

                self._current_col = index.column()

                

                # Install event filter to intercept arrow keys

                editor.installEventFilter(self)

                

                _dprint(f"[DEBUG] Editor alignment set, returning editor")

                return editor

            

            def eventFilter(self, obj, event):

                """Intercept arrow keys and other shortcuts to navigate and control cart"""

                try:

                    from PySide6.QtCore import Qt, QEvent

                    from PySide6.QtWidgets import QApplication

                except ImportError:

                    from PyQt6.QtCore import Qt, QEvent

                    from PyQt6.QtWidgets import QApplication

                

                # Only handle KeyPress events

                try:

                    key_press_type = QEvent.KeyPress

                except AttributeError:

                    key_press_type = QEvent.Type.KeyPress

                

                if event.type() == key_press_type:

                    key = event.key()

                    modifiers = QApplication.keyboardModifiers()

                    

                    # Handle Delete key to remove current row

                    if key == Qt.Key_Delete:

                        if self._table and hasattr(self, '_current_row'):

                            row = self._current_row

                            # Get the parent SalesWidget to call remove_cart_item

                            parent_widget = self._table.parent()

                            while parent_widget and not hasattr(parent_widget, 'remove_cart_item'):

                                parent_widget = parent_widget.parent()

                            if parent_widget:

                                parent_widget.remove_cart_item(row)

                            return True  # Event handled

                    

                    # Allow global shortcuts to propagate even when editing QTY/Price fields

                    # Fix 8 & 11: Let all Ctrl shortcuts pass through to application level

                    if modifiers & Qt.ControlModifier:

                        # Only handle basic text editing shortcuts locally

                        if key in (Qt.Key_C, Qt.Key_V, Qt.Key_X, Qt.Key_A):

                            if key == Qt.Key_C and hasattr(obj, 'copy'):

                                obj.copy()

                            elif key == Qt.Key_V and hasattr(obj, 'paste'):

                                obj.paste()

                            elif key == Qt.Key_X and hasattr(obj, 'cut'):

                                obj.cut()

                            elif key == Qt.Key_A and hasattr(obj, 'selectAll'):

                                obj.selectAll()

                        # Always propagate Ctrl shortcuts to allow global handlers

                        return False



                    # Handle Escape to cancel editing (but don't auto-focus search bar)

                    if key == Qt.Key_Escape:

                        if self._table:

                            self._table.closePersistentEditor(self._table.item(self._current_row, self._current_col))

                            print("[DEBUG] Escape: Closed editor")

                        return True



                    # Handle Enter to accept and move down

                    if key == Qt.Key_Return or key == Qt.Key_Enter:

                        if self._table and hasattr(self, '_current_row'):

                            # Commit the data before closing editor

                            self._table.commitData(obj)

                            # Close current editor and move to next row

                            self._table.closePersistentEditor(self._table.item(self._current_row, self._current_col))

                            new_row = min(self._table.rowCount() - 1, self._current_row + 1)

                            self._table.setCurrentCell(new_row, self._current_col)

                            if self._current_col in (1, 3):

                                QTimer.singleShot(0, lambda: self._table.editItem(self._table.item(new_row, self._current_col)))

                        return True

                    

                    # Handle Tab to move to next column or checkout

                    if key == Qt.Key_Tab:

                        if self._table and hasattr(self, '_current_row') and hasattr(self, '_current_col'):

                            # Commit the data before closing editor

                            self._table.commitData(obj)

                            self._table.closePersistentEditor(self._table.item(self._current_row, self._current_col))

                            

                            # If in Sale Price column, move to checkout section

                            if self._current_col == 3:

                                # Find parent SalesWidget and focus checkout

                                parent_widget = self._table.parent()

                                while parent_widget and not hasattr(parent_widget, 'amount_paid_input'):

                                    parent_widget = parent_widget.parent()

                                if parent_widget and hasattr(parent_widget, 'amount_paid_input'):

                                    parent_widget.amount_paid_input.setFocus()

                                    parent_widget.amount_paid_input.selectAll()

                            else:

                                # Toggle between QTY and Sale Price

                                new_col = 3 if self._current_col == 1 else 1

                                self._table.setCurrentCell(self._current_row, new_col)

                                QTimer.singleShot(0, lambda: self._table.editItem(self._table.item(self._current_row, new_col)))

                        return True

                    

                    # Handle arrow keys to navigate between cells

                    if key in (Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down):

                        if self._table and hasattr(self, '_current_row') and hasattr(self, '_current_col'):

                            # Commit the data before closing editor

                            self._table.commitData(obj)

                            self._table.closePersistentEditor(self._table.item(self._current_row, self._current_col))

                            

                            new_row = self._current_row

                            new_col = self._current_col

                            

                            if key == Qt.Key_Left:

                                new_col = 1  # Go to QTY

                            elif key == Qt.Key_Right:

                                new_col = 3  # Go to Sale Price

                            elif key == Qt.Key_Up:

                                new_row = max(0, self._current_row - 1)

                            elif key == Qt.Key_Down:

                                new_row = min(self._table.rowCount() - 1, self._current_row + 1)

                            

                            # Navigate to new cell

                            self._table.setCurrentCell(new_row, new_col)

                            if new_col in (1, 3):

                                QTimer.singleShot(0, lambda: self._table.editItem(self._table.item(new_row, new_col)))

                            

                            return True  # Event handled

                

                return super().eventFilter(obj, event)

            

            def setEditorData(self, editor, index):

                # Get the current text from the model

                text = index.model().data(index, Qt.DisplayRole) or ""

                # Set the text in the editor

                editor.setText(str(text))

                # Select all text immediately after setting data

                editor.selectAll()

            

            def setModelData(self, editor, model, index):

                _dprint(f"[DEBUG] setModelData called for row {index.row()}, col {index.column()}")

                # Get the text from the editor

                text = editor.text()

                _dprint(f"[DEBUG] Editor text: {text}")

                # Set the data in the model

                model.setData(index, text, Qt.EditRole)

                _dprint(f"[DEBUG] Data set to model")

                

                # Let the existing _on_cart_item_changed handle the updates

                # This avoids conflicts and ensures proper handling

        

        # Apply delegate to QTY and SALE PRICE columns

        self.cart_table.setItemDelegateForColumn(1, SelectAllDelegate(self.cart_table))  # QTY (column 1)

        self.cart_table.setItemDelegateForColumn(3, SelectAllDelegate(self.cart_table))  # SALE PRICE (column 3)

        _dprint("[DEBUG] Delegates applied to columns 1 and 3")

        

        # Enhanced cart table styling

        self.cart_table.setStyleSheet("""

            QTableWidget {

                background: Qt.white;

                border: 1px solid #e2e8f0;

                border-radius: 8px;

                gridline-color: #e2e8f0;

                font-size: 14px;

                color: #1e293b;

                selection-background-color: #fef3c7;

                alternate-background-color: #f8fafc;

            }

            QTableWidget::item {

                padding: 8px 10px;

                border-bottom: 1px solid #e2e8f0;

                color: #1e293b;

                background: Qt.white;

            }

            QTableWidget::item:alternate {

                background: #f8fafc;

                color: #1e293b;

            }

            QTableWidget::item:selected {

                background: #fef3c7;

                color: #92400e;

            }

            QTableWidget::item:selected:alternate {

                background: #fef3c7;

                color: #92400e;

            }

            QHeaderView::section {

                background: #f8fafc;

                color: #374151;

                font-weight: 600;

                font-size: 13px;

                padding: 10px;

                border: none;

                border-bottom: 2px solid #e2e8f0;

            }

        """)

        

        # Configure cart table

        self.cart_table.verticalHeader().setVisible(False)

        try:

            # PyQt6

            self.cart_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)

            self.cart_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        except AttributeError:

            # PySide6

            self.cart_table.setSelectionBehavior(QAbstractItemView.SelectItems)

            self.cart_table.setSelectionMode(QAbstractItemView.SingleSelection)

        

        # Add double-click event handler for quantity editing

        self.cart_table.cellDoubleClicked.connect(self.on_cart_cell_double_clicked)

        

        # Enable edit triggers for inline editing of quantity and price columns

        try:

            # PyQt6

            self.cart_table.setEditTriggers(

                QAbstractItemView.EditTrigger.DoubleClicked | 

                QAbstractItemView.EditTrigger.SelectedClicked |

                QAbstractItemView.EditTrigger.AnyKeyPressed

            )

        except AttributeError:

            # PySide6

            self.cart_table.setEditTriggers(

                QAbstractItemView.DoubleClicked | 

                QAbstractItemView.SelectedClicked |

                QAbstractItemView.AnyKeyPressed

            )

        

        # Connect to item changed signal to handle inline edits

        self.cart_table.itemChanged.connect(self._on_cart_item_changed)

        

        # Connect cell click handler for remove button

        self.cart_table.cellClicked.connect(self._on_cart_item_clicked)

        

        try:

            self.cart_table.setFocusPolicy(Qt.StrongFocus)

            # Install event filter to handle cart navigation and shortcuts

            self.cart_table.installEventFilter(self)

        except Exception:

            pass

        self.cart_table.setAlternatingRowColors(False)

        try:

            # Ensure we can scroll horizontally if needed and do not ellipsize text

            try:

                # PyQt6

                self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

            except AttributeError:

                # PySide6

                self.cart_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            try:

                self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            except AttributeError:

                self.cart_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

            self.cart_table.setTextElideMode(Qt.ElideNone)

            self.cart_table.setWordWrap(False)

        except Exception:

            pass

        # Add double-click handler to edit price

        self.cart_table.doubleClicked.connect(self._on_cart_item_double_clicked)



        cart_header = self.cart_table.horizontalHeader()

        try:

            cart_header.setStretchLastSection(True)

        except Exception:

            pass

        # Product Name should have priority space; make other columns tighter

        try:

            # PyQt6

            cart_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Product Name

        except AttributeError:

            # PySide6

            cart_header.setSectionResizeMode(0, QHeaderView.Stretch)  # Product Name

        try:

            # PyQt6

            cart_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)     # Qty

            cart_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)    # Purchase Price

            cart_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)    # Sale Price

        except AttributeError:

            # PySide6

            cart_header.setSectionResizeMode(1, QHeaderView.Fixed)     # Qty

            cart_header.setSectionResizeMode(2, QHeaderView.Fixed)    # Purchase Price

            cart_header.setSectionResizeMode(3, QHeaderView.Fixed)    # Sale Price

        cart_header.resizeSection(1, 110)   # Qty

        cart_header.resizeSection(2, 110)   # Purchase Price

        cart_header.resizeSection(3, 120)   # Sale Price

        try:

            # PyQt6

            cart_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)    # Total

            cart_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)    # Profit

            cart_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)    # Remove

        except AttributeError:

            # PySide6

            cart_header.setSectionResizeMode(4, QHeaderView.Fixed)    # Total

            cart_header.setSectionResizeMode(5, QHeaderView.Fixed)    # Profit

            cart_header.setSectionResizeMode(6, QHeaderView.Fixed)    # Remove

        cart_header.resizeSection(4, 80)   # Total - fixed width

        cart_header.resizeSection(5, 80)   # Profit - fixed width

        cart_header.resizeSection(6, 60)   # Remove

        try:

            cart_header.resizeSection(7, 70)   # Bought Qty

            cart_header.resizeSection(8, 70)   # Stock

            cart_header.resizeSection(9, 90)   # Item Disc

        except Exception:

            pass

        try:

            self.cart_table.setColumnHidden(7, True)

            self.cart_table.setColumnHidden(9, True)

        except Exception:

            pass



        try:

            self.cart_table.setColumnHidden(8, False)

        except Exception:

            pass



        try:

            self.cart_table.setMaximumHeight(420)

        except Exception:

            pass

        

        # Keep header/columns stretched; do not auto-shrink columns to contents

        

        # Set minimum widths to ensure readability

        cart_header.setMinimumSectionSize(60)  # Minimum width for any column

        # Override global header styling (blue rounded) with a flat, clean header just for the cart

        try:

            cart_header.setStyleSheet(

                "QHeaderView::section {"

                "  background: #f8fafc;"

                "  color: #374151;"

                "  font-weight: 600;"

                "  font-size: 13px;"

                "  padding: 10px;"

                "  border: 1px solid #e2e8f0;"

                "  border-bottom: 2px solid #e2e8f0;"

                "  border-radius: 0px;"

                "}"

                "QHeaderView { background: #f8fafc; }"

            )

            # Corner button (top-left) to match header

            self.cart_table.setStyleSheet(

                self.cart_table.styleSheet() +

                "\nQTableCornerButton::section {"

                "  background: #f8fafc;"

                "  border: 1px solid #e2e8f0;"

                "}"

            )

        except Exception:

            pass



        cart_section_layout.addWidget(self.cart_table)



        cart_layout.addWidget(cart_frame)



        parent_layout.addWidget(cart_container)



    def create_checkout_section(self, parent_layout):

        """Create the checkout and summary section"""

        # Checkout container

        checkout_container = QWidget()

        checkout_container.setMinimumWidth(0)

        try:

            from PySide6.QtWidgets import QSizePolicy

        except Exception:

            try:

                from PyQt6.QtWidgets import QSizePolicy

            except Exception:

                QSizePolicy = None

        try:

            if QSizePolicy is not None:

                checkout_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        except Exception:

            pass



        checkout_layout = QVBoxLayout(checkout_container)

        checkout_layout.setContentsMargins(0, 0, 0, 0)

        checkout_layout.setSpacing(1)  # COMPRESSED: 1px spacing



        # Checkout Form Section

        checkout_frame = QFrame()

        checkout_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

                padding: 4px;

            }

        """)



        checkout_form_layout = QVBoxLayout(checkout_frame)

        checkout_form_layout.setSpacing(1)  # COMPRESSED: 1px spacing

        checkout_form_layout.setContentsMargins(0, 0, 0, 0)



        # Checkout header

        checkout_title = QLabel("💳 Checkout")

        checkout_title.setStyleSheet("""

            font-size: 14px;

            font-weight: 700;

            color: #1e293b;

            margin: 0;

            padding: 0;

        """)

        checkout_form_layout.addWidget(checkout_title)



        # 3-column checkout layout

        columns_layout = QHBoxLayout()

        columns_layout.setContentsMargins(0, 0, 0, 0)

        columns_layout.setSpacing(6)  # COMPRESSED: 6px spacing



        col1 = QVBoxLayout()

        col1.setContentsMargins(0, 0, 0, 0)

        col1.setSpacing(2)  # COMPRESSED: 2px spacing



        col2 = QVBoxLayout()

        col2.setContentsMargins(0, 0, 0, 0)

        col2.setSpacing(2)  # COMPRESSED: 2px spacing



        col3 = QVBoxLayout()

        col3.setContentsMargins(0, 0, 0, 0)

        col3.setSpacing(2)  # COMPRESSED: 2px spacing



        # Customer selection

        customer_layout = QVBoxLayout()

        customer_layout.setSpacing(4)

        customer_layout.setContentsMargins(0, 0, 0, 0)



        customer_label = QLabel("👤 Customer (Ctrl+Z)")

        customer_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);

            border: 2px solid #92400e;

            border-radius: 6px;

        """)



        self.customer_combo = QComboBox()

        self.customer_combo.setEditable(True)

        try:

            le = self.customer_combo.lineEdit()

            if le is not None:

                le.setPlaceholderText("Type customer name...")

                le.setReadOnly(False)

        except Exception:

            pass

        self.customer_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 6px 10px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        customer_layout.addWidget(customer_label)

        customer_layout.addWidget(self.customer_combo)

        col1.addLayout(customer_layout)



        # Sales type selector (Retail vs Wholesale)

        sale_type_layout = QVBoxLayout()

        sale_type_layout.setSpacing(4)

        sale_type_layout.setContentsMargins(0, 0, 0, 0)



        payment_label = QLabel("💳 Payment Method (Ctrl+C)")

        payment_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22c55e, stop:1 #16a34a);

            border: 2px solid #15803d;

            border-radius: 6px;

        """)



        sale_type_label = QLabel("🏷️ Sales Type (Ctrl+T)")

        sale_type_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ec4899, stop:1 #db2777);

            border: 2px solid #be185d;

            border-radius: 6px;

        """)



        self.sale_type_combo = QComboBox()

        self.sale_type_combo.addItems([

            "Walk-in / Retail",

            "Wholesale",

        ])

        self.sale_type_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 6px 10px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        sale_type_layout.addWidget(sale_type_label)

        sale_type_layout.addWidget(self.sale_type_combo)

        col1.addLayout(sale_type_layout)



        # Payment method

        payment_layout = QVBoxLayout()

        payment_layout.setSpacing(4)

        payment_layout.setContentsMargins(0, 0, 0, 0)

        # Update cart prices when sale type changes

        try:

            self.sale_type_combo.currentTextChanged.connect(self.on_sale_type_changed)

        except Exception:

            pass



        self.pay_method_combo = QComboBox()

        self.pay_method_combo.addItems([

            "Cash", "Bank Transfer", "Credit Card",

            "EasyPaisa", "JazzCash", "Credit"

        ])

        self.pay_method_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 6px 10px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        payment_layout.addWidget(payment_label)

        payment_layout.addWidget(self.pay_method_combo)

        col2.addLayout(payment_layout)



        # Amount paid

        amount_layout = QVBoxLayout()

        amount_layout.setSpacing(4)

        amount_layout.setContentsMargins(0, 0, 0, 0)



        amount_label = QLabel("💰 Amount Paid (Ctrl+D)")

        amount_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #0891b2);

            border: 2px solid #0e7490;

            border-radius: 6px;

        """)



        self.amount_paid_input = QDoubleSpinBox()

        self.amount_paid_input.setDecimals(2)

        self.amount_paid_input.setMaximum(1_000_000_000.0)

        self.amount_paid_input.setStyleSheet("""

            QDoubleSpinBox {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 6px 10px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QDoubleSpinBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)

        # Wrap with crash prevention

        try:

            self.amount_paid_input.valueChanged.connect(lambda: self._safe_calculate_change())

        except Exception:

            self.amount_paid_input.valueChanged.connect(self.calculate_change)



        amount_layout.addWidget(amount_label)

        amount_layout.addWidget(self.amount_paid_input)

        col2.addLayout(amount_layout)



        # Discount amount (fixed Rs)

        discount_layout = QVBoxLayout()

        discount_layout.setSpacing(4)

        discount_layout.setContentsMargins(0, 0, 0, 0)



        discount_label = QLabel("🏷️ Discount (Ctrl+X):")

        discount_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 13px; 

            padding: 4px 8px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #9333ea);

            border: 2px solid #7e22ce;

            border-radius: 4px;

        """)



        self.discount_amount = QDoubleSpinBox()

        self.discount_amount.setDecimals(2)

        self.discount_amount.setMaximum(10000.0)  # Maximum Rs 10,000 discount

        self.discount_amount.setSingleStep(10.0)  # Step by Rs 10

        self.discount_amount.setValue(0.0)

        self.discount_amount.setStyleSheet("""

            QDoubleSpinBox {

                border: 2px solid #e2e8f0;

                border-radius: 6px;

                padding: 6px 10px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 20px;

            }

            QDoubleSpinBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)

        try:

            self.discount_amount.valueChanged.connect(self.update_totals)

            self.discount_amount.valueChanged.connect(self.calculate_change)

        except Exception:

            pass



        discount_layout.addWidget(discount_label)

        discount_layout.addWidget(self.discount_amount)

        col3.addLayout(discount_layout)



        # Change display

        change_layout = QVBoxLayout()

        change_layout.setSpacing(4)

        change_layout.setContentsMargins(0, 0, 0, 0)



        change_label = QLabel("Change to Give")

        change_label.setStyleSheet("font-weight: 600; color: #374151; font-size: 14px;")



        self.change_display = QLabel("Rs 0.00")

        self.change_display.setStyleSheet("""

            QLabel {

                border: 2px solid #10b981;

                border-radius: 6px;

                padding: 8px 12px;

                font-size: 16px;

                font-weight: 700;

                background: #f0fdf4;

                color: #059669;

                min-height: 20px;

            }

        """)



        change_layout.addWidget(change_label)

        change_layout.addWidget(self.change_display)

        col3.addLayout(change_layout)



        columns_layout.addLayout(col1, 1)

        columns_layout.addLayout(col2, 1)

        columns_layout.addLayout(col3, 1)

        checkout_form_layout.addLayout(columns_layout)



        # Complete Sale button - Primary action, large and prominent

        self.complete_sale_btn = QPushButton("✓ COMPLETE SALE")

        self.complete_sale_btn.setStyleSheet("""

            QPushButton {

                background: #22c55e;

                color: #ffffff;

                border: none;

                border-radius: 8px;

                padding: 4px 16px;

                font-size: 14px;

                font-weight: 700;

            }

            QPushButton:hover {

                background: #16a34a;

            }

            QPushButton:pressed {

                background: #15803d;

            }

        """)

        self.complete_sale_btn.setMinimumHeight(28)  # Reduced from 32 to 28

        self.complete_sale_btn.clicked.connect(self.process_sale)



        checkout_form_layout.addWidget(self.complete_sale_btn)

        checkout_layout.addWidget(checkout_frame)



        parent_layout.addWidget(checkout_container)

        """Create the modern products catalog section"""

        # Products container

        products_container = QWidget()

        products_container.setMinimumWidth(600)



        products_layout = QVBoxLayout(products_container)

        products_layout.setContentsMargins(0, 0, 0, 0)

        products_layout.setSpacing(16)



        # Products header

        products_header = QFrame()

        products_header.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                padding: 20px;

                border: 1px solid #e2e8f0;

            }

        """)



        header_layout = QVBoxLayout(products_header)

        header_layout.setSpacing(12)



        # Title and search

        title_search_layout = QHBoxLayout()



        title_label = QLabel("🛍️ Product Catalog")

        title_label.setStyleSheet("""

            font-size: 20px;

            font-weight: 700;

            color: #1e293b;

            margin: 0;

        """)



        # Search box

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText("🔍 Search products by name or SKU...")

        self.search_input.setStyleSheet("""

            QLineEdit {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 8px 12px;

                font-size: 14px;

                background: Qt.white;

                min-height: 20px;

            }

            QLineEdit:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)

        self.search_input.textChanged.connect(self.filter_products)



        title_search_layout.addWidget(title_label)

        title_search_layout.addStretch()

        title_search_layout.addWidget(self.search_input)



        header_layout.addLayout(title_search_layout)



        # Filter buttons

        filters_layout = QHBoxLayout()

        filters_layout.setSpacing(8)



        all_btn = QPushButton("📦 All Products")

        all_btn.setCheckable(True)

        all_btn.setChecked(True)

        all_btn.setProperty("filter", "all")



        instock_btn = QPushButton("✅ In Stock")

        instock_btn.setCheckable(True)

        instock_btn.setProperty("filter", "instock")



        lowstock_btn = QPushButton("⚠️ Low Stock")

        lowstock_btn.setCheckable(True)

        lowstock_btn.setProperty("filter", "lowstock")



        outstock_btn = QPushButton("❌ Out of Stock")

        outstock_btn.setCheckable(True)

        outstock_btn.setProperty("filter", "outstock")



        filter_buttons = [all_btn, instock_btn, lowstock_btn, outstock_btn]



        for btn in filter_buttons:

            btn.setStyleSheet("""

                QPushButton {

                    background: #f8fafc;

                    color: #64748b;

                    border: 1px solid #e2e8f0;

                    border-radius: 6px;

                    padding: 6px 12px;

                    font-size: 12px;

                    font-weight: 500;

                }

                QPushButton:checked {

                    background: #3b82f6;

                    color: Qt.white;

                    border-color: #3b82f6;

                }

                QPushButton:hover {

                    background: #e2e8f0;

                }

                QPushButton:checked:hover {

                    background: #2563eb;

                }

            """)

            btn.clicked.connect(self.on_filter_changed)

            filters_layout.addWidget(btn)



        header_layout.addLayout(filters_layout)



        products_layout.addWidget(products_header)



        # Products table container

        table_container = QFrame()

        table_container.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

            }

        """)



        table_layout = QVBoxLayout(table_container)

        table_layout.setContentsMargins(0, 0, 0, 0)



        # Modern products table

        self.products_table = QTableWidget()

        self.products_table.setColumnCount(6)

        self.products_table.setHorizontalHeaderLabels([

            "Product Name", "Barcode", "Stock", "Retail Price", "Wholesale Price", "Action"

        ])



        # Modern table styling with improved contrast

        self.products_table.setStyleSheet("""

            QTableWidget {

                background: Qt.white;

                border: none;

                border-radius: 8px;

                gridline-color: #e2e8f0;

                font-size: 14px;

                color: #1e293b;

                selection-background-color: #eff6ff;

                alternate-background-color: #fafbfc;

            }

            QTableWidget::item {

                padding: 12px 16px;

                border-bottom: 1px solid #e2e8f0;

                color: #1e293b;

                background: Qt.white;

            }

            QTableWidget::item:alternate {

                background: #fafbfc;

                color: #1e293b;

            }

            QTableWidget::item:selected {

                background: #eff6ff;

                color: #1e40af;

            }

            QHeaderView::section {

                background: #f8fafc;

                color: #374151;

                font-weight: 600;

                font-size: 13px;

                padding: 16px;

                border: none;

                border-bottom: 2px solid #e2e8f0;

            }

            QHeaderView::section:first {

                border-top-left-radius: 8px;

            }

            QHeaderView::section:last {

                border-top-right-radius: 8px;

            }

        """)



        # Configure table behavior

        self.products_table.setAlternatingRowColors(True)

        try:

            # PyQt6

            self.products_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        except AttributeError:

            # PySide6

            self.products_table.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Disable edit triggers so keyboard shortcuts work

        try:

            # PyQt6

            self.products_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        except AttributeError:

            # PySide6

            self.products_table.setEditTriggers(QAbstractItemView.NoEditTriggers)

        self.products_table.verticalHeader().setVisible(False)

        self.products_table.installEventFilter(self)

        

        # Connect double-click to edit price

        self.products_table.itemDoubleClicked.connect(self._on_product_item_double_clicked)



        # Set column resize modes

        header = self.products_table.horizontalHeader()

        try:

            # PyQt6

            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # Product Name

            header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # Barcode

            header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # Stock

            header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # Retail Price

            header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # Wholesale Price

            header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)  # Action

        except AttributeError:

            # PySide6

            header.setSectionResizeMode(0, QHeaderView.Stretch)  # Product Name

            header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Barcode

            header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Stock

            header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Retail Price

            header.setSectionResizeMode(4, QHeaderView.ResizeToContents)  # Wholesale Price

            header.setSectionResizeMode(5, QHeaderView.Fixed)  # Action

        header.resizeSection(5, 100)



        table_layout.addWidget(self.products_table)



        products_layout.addWidget(table_container)



        products_container.setVisible(False)

        parent_layout.addWidget(products_container, 2)  # 2/3 width



    def create_cart_checkout_section(self, parent_layout):

        """Create the modern cart and checkout section"""

        # Cart container

        cart_container = QWidget()

        cart_container.setMinimumWidth(400)



        cart_layout = QVBoxLayout(cart_container)

        cart_layout.setContentsMargins(0, 0, 0, 0)

        cart_layout.setSpacing(16)



        # Shopping Cart Section

        cart_frame = QFrame()

        cart_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

                padding: 20px;

            }

        """)



        cart_section_layout = QVBoxLayout(cart_frame)

        cart_section_layout.setSpacing(12)



        # Cart header

        cart_header_layout = QHBoxLayout()



        cart_title = QLabel("🛒 Shopping Cart")

        cart_title.setStyleSheet("""

            font-size: 18px;

            font-weight: 700;

            color: #1e293b;

            margin: 0;

        """)



        cart_clear_btn = QPushButton("🗑️ Clear All")

        cart_clear_btn.setStyleSheet("""

            QPushButton {

                background: #fef2f2;

                color: #dc2626;

                border: 1px solid #fecaca;

                border-radius: 6px;

                padding: 6px 12px;

                font-size: 12px;

                font-weight: 500;

            }

            QPushButton:hover {

                background: #fee2e2;

            }

        """)

        cart_clear_btn.clicked.connect(self.clear_cart)



        cart_header_layout.addWidget(cart_title)

        cart_header_layout.addStretch()

        cart_header_layout.addWidget(cart_clear_btn)



        cart_section_layout.addLayout(cart_header_layout)



        # Cart table already created as custom CartTableWidget earlier; just ensure it exists

        # (Do not recreate to avoid losing delegates and edit triggers)

        cart_header = self.cart_table.horizontalHeader()

        try:

            cart_header.setStretchLastSection(True)

        except Exception:

            pass

        # Column 0: Qty (fixed, narrow)

        try:

            # PyQt6

            cart_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)

            cart_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)

            cart_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)     # Purchase Price

        except AttributeError:

            # PySide6

            cart_header.setSectionResizeMode(0, QHeaderView.Fixed)

            cart_header.setSectionResizeMode(1, QHeaderView.Stretch)

            cart_header.setSectionResizeMode(2, QHeaderView.Fixed)     # Purchase Price

        cart_header.resizeSection(0, 60)

        # Column 1: Product (stretch – always visible)

        # Remaining columns: fixed widths

        cart_header.resizeSection(2, 90)

        try:

            # PyQt6

            cart_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)     # Unit Price

            cart_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Fixed)     # Total

            cart_header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)     # Profit

            cart_header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)     # Remove

        except AttributeError:

            # PySide6

            cart_header.setSectionResizeMode(3, QHeaderView.Fixed)     # Unit Price

            cart_header.setSectionResizeMode(4, QHeaderView.Fixed)     # Total

            cart_header.setSectionResizeMode(5, QHeaderView.Fixed)     # Profit

            cart_header.setSectionResizeMode(6, QHeaderView.Fixed)     # Remove

        cart_header.resizeSection(3, 90)

        cart_header.resizeSection(4, 90)

        cart_header.resizeSection(5, 90)

        cart_header.resizeSection(6, 70)



        cart_section_layout.addWidget(self.cart_table)



        # Cart summary

        cart_summary = QFrame()

        cart_summary.setStyleSheet("""

            QFrame {

                background: #f8fafc;

                border-radius: 8px;

                padding: 12px;

                border: 1px solid #e2e8f0;

            }

        """)



        summary_layout = QVBoxLayout(cart_summary)

        summary_layout.setSpacing(4)



        self.cart_subtotal_label = QLabel("Subtotal: Rs 0.00")

        self.cart_tax_label = QLabel("Tax: Rs 0.00")

        

        # Create discount input field instead of label

        discount_layout = QHBoxLayout()

        discount_layout.setSpacing(8)

        discount_label = QLabel("🏷️ Discount (Ctrl+X):")

        discount_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 13px; 

            padding: 4px 8px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #a855f7, stop:1 #9333ea);

            border: 2px solid #7e22ce;

            border-radius: 4px;

        """)

        

        # Simple QLineEdit for discount

        self.discount_amount_input = QLineEdit()

        self.discount_amount_input.setText("0")

        self.discount_amount_input.setFixedWidth(120)

        # Wrap signal connection with crash prevention

        self.discount_amount_input.textChanged.connect(lambda text: self._safe_update_totals())

        self.discount_amount_input.setStyleSheet("""

            QLineEdit {

                border: 1px solid #d1d5db;

                border-radius: 4px;

                padding: 4px 8px;

                font-size: 13px;

                background: Qt.white;

                color: #1e293b;

                min-height: 16px;

            }

            QLineEdit:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.1);

            }

        """)

        

        discount_layout.addWidget(discount_label)

        discount_layout.addWidget(self.discount_amount_input)

        discount_layout.addStretch()

        

        self.cart_total_label = QLabel("Total: Rs 0.00")



        # Style summary labels

        for label in [self.cart_subtotal_label, self.cart_tax_label]:

            label.setStyleSheet("font-size: 13px; color: #6b7280;")



        self.cart_total_label.setStyleSheet("""

            font-size: 16px;

            font-weight: 700;

            color: #1e293b;

            border-top: 1px solid #e2e8f0;

            padding-top: 4px;

            margin-top: 4px;

        """)



        summary_layout.addWidget(self.cart_subtotal_label)

        summary_layout.addWidget(self.cart_tax_label)

        summary_layout.addLayout(discount_layout)

        summary_layout.addWidget(self.cart_total_label)



        cart_section_layout.addWidget(cart_summary)



        cart_layout.addWidget(cart_frame)



        # Checkout Section

        checkout_frame = QFrame()

        checkout_frame.setStyleSheet("""

            QFrame {

                background: Qt.white;

                border-radius: 12px;

                border: 1px solid #e2e8f0;

                padding: 20px;

            }

        """)



        checkout_layout = QVBoxLayout(checkout_frame)

        checkout_layout.setSpacing(16)



        # Checkout header

        checkout_title = QLabel("💳 Checkout")

        checkout_title.setStyleSheet("""

            font-size: 18px;

            font-weight: 700;

            color: #1e293b;

            margin: 0;

        """)

        checkout_layout.addWidget(checkout_title)



        # Customer selection

        customer_layout = QVBoxLayout()

        customer_layout.setSpacing(6)



        customer_label = QLabel("👤 Customer (Ctrl+Z)")

        customer_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #d97706);

            border: 2px solid #92400e;

            border-radius: 6px;

        """)



        self.customer_combo = QComboBox()

        self.customer_combo.setEditable(True)

        try:

            le = self.customer_combo.lineEdit()

            if le is not None:

                le.setPlaceholderText("Type customer name...")

                le.setReadOnly(False)

        except Exception:

            pass

        self.customer_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 8px 12px;

                font-size: 14px;

                background: Qt.white;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        customer_layout.addWidget(customer_label)

        customer_layout.addWidget(self.customer_combo)



        checkout_layout.addLayout(customer_layout)



        # Payment method

        payment_layout = QVBoxLayout()

        payment_layout.setSpacing(6)



        payment_label = QLabel("💳 Payment Method (Ctrl+C)")

        payment_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #22c55e, stop:1 #16a34a);

            border: 2px solid #15803d;

            border-radius: 6px;

        """)



        self.pay_method_combo = QComboBox()

        self.pay_method_combo.addItems([

            "Cash", "Bank Transfer", "Credit Card",

            "EasyPaisa", "JazzCash", "Credit"

        ])

        self.pay_method_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 8px 12px;

                font-size: 14px;

                background: Qt.white;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        payment_layout.addWidget(payment_label)

        payment_layout.addWidget(self.pay_method_combo)



        checkout_layout.addLayout(payment_layout)



        # Sales type

        sales_type_layout = QVBoxLayout()

        sales_type_layout.setSpacing(6)



        sales_type_label = QLabel("🏷️ Sales Type (Ctrl+T)")

        sales_type_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ec4899, stop:1 #db2777);

            border: 2px solid #be185d;

            border-radius: 6px;

        """)



        self.sale_type_combo = QComboBox()

        self.sale_type_combo.addItems(["Retail", "Wholesale"])

        self.sale_type_combo.setStyleSheet("""

            QComboBox {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 8px 12px;

                font-size: 14px;

                background: Qt.white;

                min-height: 20px;

            }

            QComboBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        sales_type_layout.addWidget(sales_type_label)

        sales_type_layout.addWidget(self.sale_type_combo)



        checkout_layout.addLayout(sales_type_layout)



        # Amount paid

        amount_layout = QVBoxLayout()

        amount_layout.setSpacing(6)



        amount_label = QLabel("💰 Amount Paid (Ctrl+D)")

        amount_label.setStyleSheet("""

            font-weight: 800; 

            color: #ffffff; 

            font-size: 15px; 

            margin-bottom: 6px;

            padding: 6px 10px;

            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #06b6d4, stop:1 #0891b2);

            border: 2px solid #0e7490;

            border-radius: 6px;

        """)



        self.amount_paid_input = QDoubleSpinBox()

        self.amount_paid_input.setDecimals(2)

        self.amount_paid_input.setMaximum(1_000_000_000.0)

        # Wrap with crash prevention

        try:

            self.amount_paid_input.valueChanged.connect(lambda: self._safe_calculate_change())

        except Exception:

            self.amount_paid_input.valueChanged.connect(self.calculate_change)

        self.amount_paid_input.setStyleSheet("""

            QDoubleSpinBox {

                border: 2px solid #e2e8f0;

                border-radius: 8px;

                padding: 12px;

                font-size: 14px;

                background: Qt.white;

                min-height: 20px;

            }

            QDoubleSpinBox:focus {

                border-color: #3b82f6;

                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);

            }

        """)



        amount_layout.addWidget(amount_label)

        amount_layout.addWidget(self.amount_paid_input)

        

        # Change to give label

        self.change_label = QLabel("Change to Give: Rs 0.00")

        self.change_label.setStyleSheet("""

            font-size: 14px;

            font-weight: 700;

            color: #10b981;

            padding: 8px 12px;

            background: #f0fdf4;

            border: 1px solid #bbf7d0;

            border-radius: 6px;

            margin-top: 4px;

        """)

        # Also create change_display for compatibility with calculate_change method

        self.change_display = self.change_label

        amount_layout.addWidget(self.change_label)



        checkout_layout.addLayout(amount_layout)



        # Complete Sale button

        self.complete_sale_btn = QPushButton("💳 Complete Sale (Ctrl+Enter)")

        self.complete_sale_btn.setStyleSheet("""

            QPushButton {

                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,

                    stop:0 #10b981, stop:1 #059669);

                color: white;

                border: none;

                border-radius: 10px;

                padding: 6px;

                font-size: 15px;

                font-weight: bold;

            }

            QPushButton:hover {

                background: #059669;

            }

            QPushButton:pressed {

                background: #047857;

            }

        """)

        try:

            self.complete_sale_btn.setMinimumHeight(32)

        except Exception:

            pass

        self.complete_sale_btn.clicked.connect(self.process_sale)



        checkout_layout.addWidget(self.complete_sale_btn)



        cart_layout.addWidget(checkout_frame)



        parent_layout.addWidget(cart_container, 1)  # 1/3 width



    # Additional methods for the modern interface

    def filter_products(self):

        """Filter products based on search input"""

        search_text = self.search_input.text().lower()

        for row in range(self.products_table.rowCount()):

            product_name = self.products_table.item(row, 0).text().lower()

            sku = self.products_table.item(row, 1).text().lower()

            visible = search_text in product_name or search_text in sku

            self.products_table.setRowHidden(row, not visible)



    def on_filter_changed(self):

        """Handle filter button changes"""

        sender = self.sender()

        filter_type = sender.property("filter")



        # Uncheck all other buttons

        for btn in self.findChildren(QPushButton):

            if btn.property("filter") and btn != sender:

                btn.setChecked(False)



        sender.setChecked(True)



        # Apply filter logic

        if filter_type == "all":

            for row in range(self.products_table.rowCount()):

                self.products_table.setRowHidden(row, False)

        elif filter_type == "instock":

            for row in range(self.products_table.rowCount()):

                stock_text = self.products_table.item(row, 2).text()

                try:

                    stock = int(stock_text)

                    self.products_table.setRowHidden(row, stock <= 0)

                except:

                    self.products_table.setRowHidden(row, True)

        # Add more filter logic as needed



    def clear_cart(self):

        """Clear all items from cart"""

        try:

            buttons = getattr(QMessageBox, 'StandardButton', QMessageBox)

            reply = QMessageBox.question(

                self, "Clear Cart",

                "Are you sure you want to clear all items from the cart?",

                buttons.Yes | buttons.No

            )

        except Exception:

            reply = QMessageBox.question(

                self, "Clear Cart",

                "Are you sure you want to clear all items from the cart?",

                QMessageBox.Yes | QMessageBox.No

            )

        if reply in (getattr(QMessageBox, 'StandardButton', QMessageBox).Yes, QMessageBox.Yes):

            self.current_cart.clear()

            self.update_cart_table()

            self.update_totals()



    def refresh_data(self):

        """Refresh all data"""

        self.load_products()

        self.load_customers()

        self.update_totals()



    def show_keyboard_help(self):

        """Show keyboard shortcuts help"""

        shortcuts_text = """

        <h3>Keyboard Shortcuts</h3>

        <table>

        <tr><td><b>F1</b></td><td>Focus product search</td></tr>

        <tr><td><b>F2</b></td><td>Focus barcode input</td></tr>

        <tr><td><b>F3</b></td><td>Focus customer selection</td></tr>

        <tr><td><b>Enter</b></td><td>Add product to cart</td></tr>

        <tr><td><b>Delete</b></td><td>Remove selected cart item</td></tr>

        <tr><td><b>Ctrl+Q</b></td><td>Increase quantity of selected item</td></tr>

        <tr><td><b>Ctrl+Shift+Q</b></td><td>Decrease quantity of selected item</td></tr>

        <tr><td><b>Ctrl+S</b></td><td>Focus product search / Complete sale</td></tr>

        <tr><td><b>Ctrl+E</b></td><td>Edit price of selected item</td></tr>

        <tr><td><b>Ctrl+Up/Down</b></td><td>Increase/Decrease price by 10</td></tr>

        <tr><td><b>Ctrl+Shift+Up/Down</b></td><td>Increase/Decrease price by 1</td></tr>

        </table>

        """

        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)



    def _safe_update_totals(self):

        """Safe wrapper for update_totals to prevent crashes"""

        try:

            self.update_totals()

        except Exception as e:

            _dprint(f"[DEBUG] Error in _safe_update_totals: {e}")

            # Don't crash - just log and continue

    

    def _safe_calculate_change(self):

        """Safe wrapper for calculate_change to prevent crashes"""

        try:

            self.calculate_change()

        except Exception as e:

            _dprint(f"[DEBUG] Error in _safe_calculate_change: {e}")

            # Don't crash - just log and continue



    def on_discount_changed(self, text):

        """Handle discount text changes with debugging and crash prevention"""

        try:

            _dprint(f"[DEBUG] Discount field changed: '{text}'")

            # Validate input before updating totals

            if text and text.strip():

                try:

                    float(text)

                except ValueError:

                    # Invalid number, ignore silently

                    return

            self.update_totals()

        except Exception as e:

            _dprint(f"[DEBUG] Error in discount change: {e}")

            # Don't crash, just log the error



    def update_totals(self):

        """Update all total labels in the interface"""

        if not self.current_cart:

            subtotal = discount = final_total = purchase_total = profit = amount_paid = change = 0.0

        else:

            # Calculate subtotal = sum(qty × sale_price)

            subtotal = sum(item['quantity'] * item['price'] for item in self.current_cart)



            # Get discount from the active discount widget (QDoubleSpinBox/QLineEdit)

            try:

                discount = float(self._get_discount_amount_value() or 0.0)

            except Exception:

                discount = 0.0

            

            # discount = min(discount, subtotal)  # cannot exceed subtotal

            discount = min(discount, subtotal)

            

            # Calculate purchase_total = sum(qty × purchase_price)

            purchase_total = sum(item['quantity'] * item.get('purchase_price', 0) for item in self.current_cart)

            

            # final_total = subtotal - discount

            final_total = subtotal - discount

            

            # profit = final_total - purchase_total

            profit = final_total - purchase_total

            

            # Get current amount_paid for change calculation

            amount_paid = 0.0

            if hasattr(self, 'amount_paid_input'):

                try:

                    amount_paid = float(self.amount_paid_input.value())

                except:

                    amount_paid = 0.0

            

            # Calculate change

            change = max(0, amount_paid - final_total)



        # Update UI labels

        if hasattr(self, 'cart_subtotal_label'):

            self.cart_subtotal_label.setText(f"Subtotal: Rs {subtotal:,.2f}")

        if hasattr(self, 'cart_total_label'):

            self.cart_total_label.setText(f"Final Total: Rs {final_total:,.2f}")

        if hasattr(self, 'change_display'):

            self.change_display.setText(f"Rs {change:,.2f}")

        if hasattr(self, 'change_label'):

            self.change_label.setText(f"Change to Give: Rs {change:,.2f}")

        if hasattr(self, 'sales_card'):

            self.sales_card.setText(f"Rs {final_total:,.2f}")



    def update_cart_profit_display(self):

        """Update profit display in cart table after discount changes"""

        try:

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                # Recalculate profit for each cart item

                for i in range(self.cart_table.rowCount()):

                    if i < len(self.current_cart):

                        item = self.current_cart[i]

                        sale_price = item['price']

                        purchase_price = item.get('purchase_price', 0)

                        quantity = item['quantity']

                        

                        # Profit per item = sale_price - purchase_price

                        profit_per_item = (sale_price - purchase_price) * quantity

                        profit_item = QTableWidgetItem(f"Rs {profit_per_item:,.2f}")

                        profit_item.setTextAlignment(Qt.AlignRight)

                        

                        font = QFont()

                        font.setBold(True)

                        profit_item.setFont(font)

                        

                        # Color based on profit

                        if profit_per_item > 0:

                            profit_item.setForeground(QColor("#10b981"))  # Green

                        elif profit_per_item < 0:

                            profit_item.setForeground(QColor("#ef4444"))  # Red

                        else:

                            profit_item.setForeground(QColor("#6b7280"))  # Gray

                        

                        self.cart_table.setItem(i, 5, profit_item)

        except Exception as e:

            print(f"Error updating profit display: {e}")



    # Placeholder methods that need to be implemented

    def load_tax_rate(self):

        """Load tax rate from settings"""

        settings = QSettings("POSApp", "Settings")

        try:

            v = settings.value('tax_rate', 8.0)

            if v is None or str(v).strip() == "":

                v = 8.0

            self.tax_rate = float(v)

        except Exception:

            self.tax_rate = 8.0

        try:

            self.update_totals()

        except Exception:

            pass



    def _bind_shortcuts(self):

        """Bind keyboard shortcuts for cycling checkout options"""

        try:

            # ----------------------------------------------------------------------------------

            # Qt enum alias

            try:

                from PySide6.QtCore import Qt as _Qt

            except ImportError:

                from PyQt6.QtCore import Qt as _Qt

            # ----------------------------------------------------------------------------------

            # Ctrl+R - Refund mode handler (Fix 7)

            try:

                ctrl_r_short = QShortcut(QKeySequence("Ctrl+R"), self)

                ctrl_r_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                ctrl_r_short.activated.connect(self._handle_ctrl_r)

                print("[DEBUG] Ctrl+R shortcut bound with ApplicationShortcut context")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+R: {e}")



            # Ctrl+Shift+R - Restore all items in refund mode

            try:

                ctrl_shift_r_short = QShortcut(QKeySequence("Ctrl+Shift+R"), self)

                ctrl_shift_r_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                ctrl_shift_r_short.activated.connect(lambda: self._handle_ctrl_r(restore_all=True))

                print("[DEBUG] Ctrl+Shift+R shortcut bound with ApplicationShortcut context")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+Shift+R: {e}")



            # Ctrl+Enter - Complete sale globally (Fix for user request)

            try:

                ctrl_enter_short = QShortcut(QKeySequence("Ctrl+Return"), self)

                ctrl_enter_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                ctrl_enter_short.activated.connect(self._handle_ctrl_enter_complete_sale)

                print("[DEBUG] Ctrl+Enter shortcut bound with ApplicationShortcut context")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+Enter: {e}")

            

            # Ctrl+Shift+Enter - Complete sale and print receipt

            try:

                ctrl_shift_enter_short = QShortcut(QKeySequence("Ctrl+Shift+Return"), self)

                ctrl_shift_enter_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                ctrl_shift_enter_short.activated.connect(self._handle_ctrl_shift_enter_complete_sale_with_receipt)

                print("[DEBUG] Ctrl+Shift+Enter shortcut bound with ApplicationShortcut context")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+Shift+Enter: {e}")

            

            # Delete / Backspace - remove selected cart item

            try:

                del_short = QShortcut(QKeySequence(_Qt.Key_Delete), self)

                del_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                del_short.activated.connect(self._delete_selected_cart_item)

                back_short = QShortcut(QKeySequence(_Qt.Key_Backspace), self)

                back_short.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                back_short.activated.connect(self._delete_selected_cart_item)

            except Exception:

                pass

            

            # Ctrl+Z - Focus customer selector (typing)

            try:

                sc_customer = QShortcut(QKeySequence("Ctrl+Z"), self)

                sc_customer.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_customer.activated.connect(self._focus_customer_select)

            except Exception:

                pass

            

            # F1 - Help/Show shortcuts (Fix 8)

            try:

                sc_help = QShortcut(QKeySequence("F1"), self)

                sc_help.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_help.activated.connect(self.show_keyboard_help)

                print("[DEBUG] F1 shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding F1: {e}")

            

            # F2 - Clear cart (Fix 8)

            try:

                sc_clear = QShortcut(QKeySequence("F2"), self)

                sc_clear.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_clear.activated.connect(self.clear_cart)

                print("[DEBUG] F2 shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding F2: {e}")

            

            # F3 - Toggle refund mode (Fix 8)

            try:

                sc_refund = QShortcut(QKeySequence("F3"), self)

                sc_refund.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_refund.activated.connect(self.toggle_refund_mode)

                print("[DEBUG] F3 shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding F3: {e}")



            # Ctrl+Shift+Z - Cycle customer options

            try:

                sc_customer_cycle = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)

                sc_customer_cycle.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_customer_cycle.activated.connect(self.cycle_customer)

                self._sc_customer_cycle = sc_customer_cycle

            except Exception:

                pass

            

            # Ctrl+C - Cycle Payment Method options (Fix 8)

            try:

                sc_payment = QShortcut(QKeySequence("Ctrl+C"), self)

                sc_payment.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_payment.activated.connect(self.cycle_payment_method)

                print("[DEBUG] Ctrl+C shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+C: {e}")

            

            # Ctrl+T - Cycle Sales Type options (Fix 8)

            try:

                sc_sales_type = QShortcut(QKeySequence("Ctrl+T"), self)

                sc_sales_type.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_sales_type.activated.connect(self.cycle_sales_type)

                print("[DEBUG] Ctrl+T shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+T: {e}")

            

            # Ctrl+X - Focus discount field (Fix 8)

            try:

                sc_discount = QShortcut(QKeySequence("Ctrl+X"), self)

                sc_discount.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_discount.activated.connect(self.focus_discount_field)

                self._sc_discount = sc_discount

                print("[DEBUG] Ctrl+X shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+X: {e}")

            

            # Ctrl+D - Focus amount paid field (Fix 8)

            try:

                sc_amount = QShortcut(QKeySequence("Ctrl+D"), self)

                sc_amount.setContext(_Qt.ShortcutContext.ApplicationShortcut)

                sc_amount.activated.connect(lambda: self._focus_amount_paid())

                self._sc_amount = sc_amount

                print("[DEBUG] Ctrl+D shortcut bound with ApplicationShortcut")

            except Exception as e:

                print(f"[DEBUG] Error binding Ctrl+D: {e}")

                

        except Exception:

            pass



    def cycle_customer(self):

        """Cycle through customer options"""

        try:

            if hasattr(self, 'customer_combo'):

                current_index = self.customer_combo.currentIndex()

                next_index = (current_index + 1) % self.customer_combo.count()

                self.customer_combo.setCurrentIndex(next_index)

                print(f"[SHORTCUT] Ctrl+Z: Customer changed to {self.customer_combo.currentText()}")

                

                # Return focus to cart table after changing customer (like other fields)

                if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                    self.cart_table.setFocus()

                    self.cart_table.selectRow(0)

        except Exception as e:

            print(f"[DEBUG] Error cycling customer: {e}")



    def cycle_payment_method(self):

        """Cycle through payment method options"""

        try:

            # Don't change payment method if cart table is being edited

            if hasattr(self, 'cart_table') and self.cart_table.state() == QTableWidget.EditingState:

                print("[DEBUG] Cart table is being edited, not changing payment method")

                return

                

            if hasattr(self, 'pay_method_combo'):

                current_index = self.pay_method_combo.currentIndex()

                next_index = (current_index + 1) % self.pay_method_combo.count()

                self.pay_method_combo.setCurrentIndex(next_index)

                print(f"[SHORTCUT] Ctrl+C: Payment method changed to {self.pay_method_combo.currentText()}")

                

                # Return focus to cart table after changing payment method

                if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                    self.cart_table.setFocus()

                    self.cart_table.selectRow(0)

        except Exception as e:

            print(f"[DEBUG] Error cycling payment method: {e}")



    def cycle_sales_type(self):

        """Cycle through sales type options"""

        try:

            if hasattr(self, 'sale_type_combo'):

                current_index = self.sale_type_combo.currentIndex()

                next_index = (current_index + 1) % self.sale_type_combo.count()

                self.sale_type_combo.setCurrentIndex(next_index)

                print(f"[SHORTCUT] Ctrl+T: Sales type changed to {self.sale_type_combo.currentText()}")

                

                # Return focus to cart table after changing sales type

                if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                    self.cart_table.setFocus()

                    self.cart_table.selectRow(0)

        except Exception as e:

            print(f"[DEBUG] Error cycling sales type: {e}")



    def focus_discount_field(self):

        """Focus on discount field - Ctrl+X shortcut"""

        try:

            _dprint("[DEBUG] focus_discount_field called")

            if hasattr(self, 'discount_amount_input'):

                _dprint(f"[DEBUG] Found discount field: {self.discount_amount_input}")

                self.discount_amount_input.setFocus()

                self.discount_amount_input.selectAll()

                print("[SHORTCUT] Ctrl+X pressed: Focused on discount")

            else:

                _dprint("[DEBUG] Discount field not found")

        except Exception as e:

            _dprint(f"[DEBUG] Error focusing discount field: {e}")



    def _focus_amount_paid(self):

        """Focus on amount paid field - Ctrl+D shortcut"""

        try:

            print("[SHORTCUT] Ctrl+D: Focusing amount paid field")

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setFocus()

                self.amount_paid_input.selectAll()

                print("[SHORTCUT] Ctrl+D: Amount paid field focused")

            else:

                print("[DEBUG] Amount paid field not found")

        except Exception as e:

            print(f"[DEBUG] Error focusing amount paid field: {e}")



    def eventFilter(self, obj, event):

        """Global event filter for keyboard shortcuts and navigation"""

        try:

            from PySide6.QtCore import QEvent, Qt

        except ImportError:

            from PyQt6.QtCore import QEvent, Qt



        try:

            # Handle Qt5/Qt6 compatibility for QEvent.KeyPress

            try:

                key_press_type = QEvent.KeyPress

            except AttributeError:

                key_press_type = QEvent.Type.KeyPress



            if event.type() != key_press_type:

                return super().eventFilter(obj, event)



            key = event.key()

            modifiers = event.modifiers()

            cart_tbl = getattr(self, 'cart_table', None)

            search_input = getattr(self, 'product_search', None)

            sugg_list = getattr(self, 'search_suggestions_list', None)



            # Debug: Log ALL key events with Ctrl

            if modifiers & Qt.ControlModifier:

                print(f"[DEBUG] eventFilter: Ctrl key - key={key} (R={key == Qt.Key_R}), obj={obj.__class__.__name__}")



            # 1. Global Ctrl Shortcuts - PRIORITY 0

            if modifiers & Qt.ControlModifier:

                print(f"[DEBUG] Ctrl key detected - key={key}, modifiers={modifiers}")

                if key == Qt.Key_C:

                    self.cycle_payment_method()

                    return True

                if key == Qt.Key_R:

                    print(f"[DEBUG] Ctrl+R detected in eventFilter (Shift={modifiers & Qt.ShiftModifier})")

                    if modifiers & Qt.ShiftModifier:

                        self._handle_ctrl_r(restore_all=True)

                    else:

                        self._handle_ctrl_r()

                    return True

                if key == Qt.Key_Z:

                    if modifiers & Qt.ShiftModifier:

                        self.cycle_customer()

                    else:

                        self._focus_customer_select()

                    return True

                if key == Qt.Key_T:

                    self.cycle_sales_type()

                    return True

                if key == Qt.Key_S:

                    if search_input:

                        if search_input.hasFocus():

                            search_input.clearFocus()

                            if cart_tbl:

                                cart_tbl.setFocus()

                        else:

                            search_input.setFocus()

                            search_input.selectAll()

                    return True

                if key == Qt.Key_X:

                    self.focus_discount_field()

                    return True

                if key == Qt.Key_D:

                    self._focus_amount_paid()

                    return True

                if key == Qt.Key_E:

                    if cart_tbl and len(self.current_cart) > 0:

                        row = cart_tbl.currentRow()

                        if row >= 0:

                            self.edit_cart_item_price(row)

                    return True

                if key == Qt.Key_Q:

                    if cart_tbl and len(self.current_cart) > 0:

                        row = cart_tbl.currentRow()

                        if row >= 0:

                            qty = int(self.current_cart[row]['quantity'])

                            if modifiers & Qt.ShiftModifier:

                                if qty > 1:

                                    self.current_cart[row]['quantity'] = qty - 1

                                else:

                                    self.remove_cart_item(row)

                            else:

                                self.current_cart[row]['quantity'] = qty + 1

                            self.update_cart_table()

                            self.update_totals()

                    return True



            # 2. Search Suggestions Navigation

            if search_input and sugg_list and sugg_list.count() > 0:

                if obj is search_input and key == Qt.Key_Down:

                    sugg_list.setFocus()

                    sugg_list.setCurrentRow(0)

                    item = sugg_list.item(0)

                    if item:

                        item.setSelected(True)

                        sugg_list.setCurrentItem(item)

                    return True

                

                # Down arrow from search suggestions - if at bottom, go to cart

                if (obj is sugg_list or (hasattr(sugg_list, 'viewport') and obj is sugg_list.viewport())):

                    if key == Qt.Key_Down:

                        current_row = sugg_list.currentRow()

                        if current_row < sugg_list.count() - 1:

                            sugg_list.setCurrentRow(current_row + 1)

                            item = sugg_list.item(current_row + 1)

                            if item:

                                item.setSelected(True)

                                sugg_list.setCurrentItem(item)

                        else:

                            # At bottom of suggestions, move to cart if it has items

                            if cart_tbl and cart_tbl.rowCount() > 0:

                                cart_tbl.setFocus()

                                cart_tbl.selectRow(0)

                                print("[DEBUG] Navigation: Suggestions -> Cart")

                        return True

                    if key == Qt.Key_Up:

                        current_row = sugg_list.currentRow()

                        if current_row > 0:

                            sugg_list.setCurrentRow(current_row - 1)

                            item = sugg_list.item(current_row - 1)

                            if item:

                                item.setSelected(True)

                                sugg_list.setCurrentItem(item)

                        else:

                            search_input.setFocus()

                            search_input.selectAll()

                        return True

                    if key in (Qt.Key_Return, Qt.Key_Enter):

                        curr = sugg_list.currentItem()

                        if curr:

                            try:

                                self._on_suggestion_selected(curr)

                            except Exception as e:

                                print(f"[DEBUG] Error selecting suggestion: {e}")

                        return True

                    # Escape closes suggestions but doesn't auto-focus search

                    if key == Qt.Key_Escape:

                        sugg_list.hide()

                        return True



            # 2a. Down arrow from search input - navigate to suggestions or cart

            if search_input and obj is search_input and key == Qt.Key_Down:

                # If Ctrl+Down, skip suggestions and go directly to cart

                if modifiers & Qt.ControlModifier:

                    if cart_tbl and cart_tbl.rowCount() > 0:

                        cart_tbl.setFocus()

                        cart_tbl.selectRow(0)

                        print("[DEBUG] Navigation: Search -> Cart (Ctrl+Down)")

                        return True

                # If no suggestions, go directly to cart if it has items

                elif not sugg_list or sugg_list.count() == 0:

                    if cart_tbl and cart_tbl.rowCount() > 0:

                        cart_tbl.setFocus()

                        cart_tbl.selectRow(0)

                        print("[DEBUG] Navigation: Search -> Cart (no suggestions)")

                        return True

                # If suggestions exist, let the code above handle it (go to suggestions first)

                return False



            # 3. Cart Table Navigation

            if cart_tbl and (obj is cart_tbl or (hasattr(cart_tbl, 'viewport') and obj is cart_tbl.viewport())):

                if key == Qt.Key_Up:

                    current_row = cart_tbl.currentRow()

                    if current_row <= 0 and search_input:

                        search_input.setFocus()

                        search_input.selectAll()

                        return True

                    # Let default behavior handle other rows

                    return False

                if key in (Qt.Key_Backspace, Qt.Key_Delete):

                    row = cart_tbl.currentRow()

                    if row >= 0 and row < len(self.current_cart):

                        print(f"[DEBUG] Delete/Backspace: Removing cart item at row {row}")

                        self.remove_cart_item(row)

                        # Select the next row or the last row if this was the last one

                        if cart_tbl.rowCount() > 0:

                            if row >= cart_tbl.rowCount():

                                cart_tbl.selectRow(cart_tbl.rowCount() - 1)

                            else:

                                cart_tbl.selectRow(row)

                        return True

                return False



            # 4. Cell Editors

            if cart_tbl and cart_tbl.state() == QTableWidget.EditingState:

                return False



            # 5. Fallback Barcode/Text

            text_inputs = (

                search_input,

                getattr(self, 'barcode_input', None),

                getattr(self, 'amount_paid_input', None),

                getattr(self, 'discount_amount_input', None),

                getattr(self, 'refund_invoice_input', None),

            )



            try:

                customer_line_edit = getattr(self, 'customer_combo', None)

                if customer_line_edit:

                    customer_line_edit = customer_line_edit.lineEdit()

                if customer_line_edit:

                    text_inputs = text_inputs + (customer_line_edit,)



                customer_combo = getattr(self, 'customer_combo', None)

                if customer_combo:

                    text_inputs = text_inputs + (customer_combo,)



                if cart_tbl:

                    text_inputs = text_inputs + (cart_tbl,)

            except Exception:

                pass



            # Always let search input and suggestions handle Enter to add products

            fw = self.focusWidget()

            if (fw is search_input or fw is sugg_list or 

                (hasattr(sugg_list, 'viewport') and fw is sugg_list.viewport())) and key in (Qt.Key_Return, Qt.Key_Enter):

                # Let search field/suggestions handle Enter to add product

                return False

            

            # Handle Delete/Backspace for cart table globally

            if key in (Qt.Key_Backspace, Qt.Key_Delete):

                fw = self.focusWidget()

                if fw is cart_tbl or (hasattr(cart_tbl, 'viewport') and fw is cart_tbl.viewport()):

                    row = cart_tbl.currentRow()

                    if row >= 0 and row < len(self.current_cart):

                        print(f"[DEBUG] Global Delete/Backspace: Removing cart item at row {row}")

                        self.remove_cart_item(row)

                        # Select the next row or the last row if this was the last one

                        if cart_tbl.rowCount() > 0:

                            if row >= cart_tbl.rowCount():

                                cart_tbl.selectRow(cart_tbl.rowCount() - 1)

                            else:

                                cart_tbl.selectRow(row)

                        return True



            # NEVER process sale completion from eventFilter - let keyPressEvent handle it

            # This prevents crashes and ensures proper event handling

            return False

        except Exception as e:

            print(f"[DEBUG] eventFilter Error: {e}")

            return False



    def keyPressEvent(self, event):

        """Handle keyboard navigation and shortcuts"""

        try:

            from PySide6.QtCore import Qt

        except ImportError:

            from PyQt6.QtCore import Qt



        try:

            # Let refund invoice input handle keys normally, but allow Ctrl+R to pass through

            if self.focusWidget() is getattr(self, 'refund_invoice_input', None):

                key = event.key()

                modifiers = event.modifiers()

                # Allow Ctrl+R to be processed even when refund input has focus

                if key == Qt.Key_R and (modifiers & Qt.ControlModifier):

                    # Don't return - let Ctrl+R be processed below

                    pass

                else:

                    # Let refund input handle all other keys normally

                    return

        except Exception:

            pass

        

        # Handle keyboard shortcuts here as well (in case eventFilter doesn't catch them)

        if not event.isAutoRepeat():

            key_text = event.text().lower()

            key = event.key()

            modifiers = event.modifiers()

            

            # Ctrl+Enter - Complete sale (ONLY way to complete sales now)

            if key == Qt.Key_Return or key == Qt.Key_Enter:

                if modifiers & Qt.ControlModifier:

                    if getattr(self, 'current_cart', []) and len(self.current_cart) > 0:

                        print("[SHORTCUT] Ctrl+Enter: Completing sale")

                        try:

                            # Use QTimer to prevent blocking and crashes

                            from PySide6.QtCore import QTimer

                            QTimer.singleShot(100, self._safe_process_sale)

                            return

                        except Exception as e:

                            print(f"[DEBUG] Error setting up sale processing: {e}")

                            return

                    else:

                        event.ignore()

                        return

            # Regular Enter key without Ctrl - complete sale if cart has items

            elif key in (Qt.Key_Return, Qt.Key_Enter) and not modifiers:

                if getattr(self, 'current_cart', []) and len(self.current_cart) > 0:

                    print("[SHORTCUT] Enter: Completing sale")

                    try:

                        # Use QTimer to prevent blocking and crashes

                        from PySide6.QtCore import QTimer

                        QTimer.singleShot(100, self._safe_process_sale)

                        return

                    except Exception as e:

                        print(f"[DEBUG] Error setting up sale processing: {e}")

                        return

                else:

                    event.ignore()

                    return

            

            # Ctrl+X - Focus on discount field - REMOVED (handled in eventFilter)

            if key == Qt.Key_X and (modifiers & Qt.ControlModifier):

                print("[SHORTCUT] Ctrl+X: Focusing discount field")

                if hasattr(self, 'discount_amount_input'):

                    self.discount_amount_input.setFocus()

                    self.discount_amount_input.selectAll()

                    print("[SHORTCUT] Ctrl+X: Discount field focused")

                else:

                    print("[DEBUG] Discount field not found")

                return

            

            # Ctrl+D - Focus on amount paid field

            if key == Qt.Key_D and (modifiers & Qt.ControlModifier):

                print("[SHORTCUT] Ctrl+D: Focusing amount paid field")

                if hasattr(self, 'amount_paid_input'):

                    self.amount_paid_input.setFocus()

                    self.amount_paid_input.selectAll()

                    print("[SHORTCUT] Ctrl+D: Amount paid field focused")

                else:

                    print("[DEBUG] Amount paid field not found")

                return

            

            # Ctrl+E - Edit price of selected cart item

            if key == Qt.Key_E and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        self.edit_cart_item_price(current_row)

                        return

            

            # Ctrl+S - Toggle focus on product search

            if key == Qt.Key_S and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'product_search'):

                    # Check if search field is already focused

                    if self.product_search.hasFocus():

                        # Unfocus search field to allow other shortcuts

                        self.product_search.clearFocus()

                        # Focus on cart table as alternative

                        if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                            self.cart_table.setFocus()

                        print("[SHORTCUT] Ctrl+S: Unfocused search field")

                    else:

                        # Focus search field

                        self.product_search.setFocus()

                        self.product_search.selectAll()

                        print("[SHORTCUT] Ctrl+S: Focused on search field")

                    return

            

            # Ctrl+X - Focus on discount field - REMOVED (handled in eventFilter)

            # if key == Qt.Key_X and (modifiers & Qt.ControlModifier):

            #     print("[DEBUG] Ctrl+X detected in keyPressEvent")

            #     if hasattr(self, 'discount_amount_input'):

            #         print(f"[DEBUG] Found discount field: {self.discount_amount_input}")

            #         self.discount_amount_input.setFocus()

            #         self.discount_amount_input.selectAll()

            #         print("[SHORTCUT] Ctrl+X: Focused on discount field")

            #         event.accept()

            #         return

            #     else:

            #         print("[DEBUG] Discount field NOT found!")

            #         event.ignore()

            #         return

            

            # Ctrl+Up - Increase price of selected cart item

            if key == Qt.Key_Up and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        current_price = float(self.current_cart[current_row]['price'])

                        new_price = current_price + 10

                        self.current_cart[current_row]['price'] = new_price

                        self.update_cart_table()

                        self.update_totals()

                        return

            

            # Ctrl+Down - Decrease price of selected cart item

            if key == Qt.Key_Down and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        current_price = float(self.current_cart[current_row]['price'])

                        new_price = max(0, current_price - 10)

                        self.current_cart[current_row]['price'] = new_price

                        self.update_cart_table()

                        self.update_totals()

                        return



            # Ctrl+R - Handle refund mode (mark/unmark items)

            if key == Qt.Key_R and (modifiers & Qt.ControlModifier):

                print(f"[SHORTCUT] Ctrl+R detected in keyPressEvent (Shift={modifiers & Qt.ShiftModifier})")

                if modifiers & Qt.ShiftModifier:

                    self._handle_ctrl_r(restore_all=True)

                else:

                    self._handle_ctrl_r()

                return



            # Ctrl+A - Increase quantity of selected cart item

            if key == Qt.Key_A and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        self.current_cart[current_row]['quantity'] = int(self.current_cart[current_row]['quantity']) + 1

                        self.update_cart_table()

                        self.update_totals()

                        return



            # Ctrl+C - Change payment method

            if key == Qt.Key_C and (modifiers & Qt.ControlModifier):

                # Don't change payment method if cart table is being edited

                if hasattr(self, 'cart_table') and self.cart_table.state() == QTableWidget.EditingState:

                    print("[DEBUG] Cart table is being edited, not changing payment method")

                    # Allow default copy behavior in the editor

                    event.ignore()

                    return



                combo = getattr(self, 'pay_method_combo', None) or getattr(self, 'payment_method_combo', None)

                if combo and combo.count() > 0:

                    current_index = combo.currentIndex()

                    next_index = (current_index + 1) % combo.count()

                    combo.setCurrentIndex(next_index)

                    combo.setFocus()

                    return



            # Ctrl+T - Change sales type (cycle through Retail/Wholesale)

            if key == Qt.Key_T and (modifiers & Qt.ControlModifier):

                combo = getattr(self, 'sale_type_combo', None) or getattr(self, 'sales_type_combo', None)

                if combo and combo.count() > 0:

                    current_index = combo.currentIndex()

                    next_index = (current_index + 1) % combo.count()

                    combo.setCurrentIndex(next_index)

                    combo.setFocus()

                    return



            # Ctrl+Z - Focus customer (editable + suggestions)

            if key == Qt.Key_Z and (modifiers & Qt.ControlModifier):

                try:

                    self._focus_customer_select()

                    return

                except Exception:

                    return



        # Enter key handling

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:

            fw = self.focusWidget()

            

            # Let refund invoice input handle Enter normally

            if fw is getattr(self, 'refund_invoice_input', None):

                return

            

            # Let search input and suggestions handle Enter to add products

            if fw in (getattr(self, 'product_search', None), getattr(self, 'search_suggestions_list', None), getattr(self, 'barcode_input', None)):

                # Let the native handlers add products - don't interfere

                return

            

            # For ALL other cases, ignore Enter to prevent accidental sales

            # Only Ctrl+Enter should complete sales (handled above)

            event.ignore()

            return

        

        # Delete key - remove cart item

        if event.key() == Qt.Key_Delete:

            if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

                current_row = self.cart_table.currentRow()

                if current_row >= 0 and current_row < len(self.current_cart):

                    self.remove_cart_item(current_row)

                    return

        

        # Backspace key - remove cart item

        if event.key() == Qt.Key_Backspace:

            if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

                current_row = self.cart_table.currentRow()

                if current_row >= 0 and current_row < len(self.current_cart):

                    self.remove_cart_item(current_row)

                    return

        

        # Arrow keys for navigation

        if event.key() == Qt.Key_Right:

            self.navigate_right()

            return

        elif event.key() == Qt.Key_Left:

            self.navigate_left()

            return

        elif event.key() == Qt.Key_Down:

            self.navigate_down()

            return

        elif event.key() == Qt.Key_Up:

            self.navigate_up()

            return

        

        # Tab key: move to next field

        if event.key() == Qt.Key_Tab:

            self.navigate_right()

            return

        

        # Shift+Tab: move to previous field

        if event.key() == Qt.Key_Backtab:

            self.navigate_left()

            return

        

        # Default behavior

        super().keyPressEvent(event)



    def _safe_process_sale(self):

        """Safe wrapper for process_sale to prevent crashes"""

        try:

            if getattr(self, 'is_refund_mode', False):

                # In refund mode, only allow processing if an invoice was loaded

                if getattr(self, 'refund_of_sale_id', None) is None:

                    return

            self.process_sale()

        except Exception as e:

            print(f"[DEBUG] Error in safe_process_sale: {e}")



    def _handle_enter_key(self):

        """Smart Enter key handling.



        - If focus is on search/barcode inputs, let their own handlers run.

        - Otherwise, when there are items in the cart, treat Enter as

          "complete sale" from anywhere on the Sales page.

        """

        try:

            w = self.focusWidget()



            # If focus is on refund invoice input, Enter should load invoice only

            if w is getattr(self, 'refund_invoice_input', None):

                try:

                    self.load_refund_invoice()

                except Exception:

                    pass

                return



            # If focus is on search inputs, let their own returnPressed handlers work

            if w in (getattr(self, 'product_search', None), getattr(self, 'barcode_input', None)):

                return



            # From anywhere else on the Sales page, Enter should complete the

            # sale as long as there is something in the cart.

            # NOTE: Sale completion is intentionally restricted to Ctrl+Enter

            # to avoid accidental sales while scanning/typing.

            return

        except Exception:

            pass



    def on_settings_updated(self, settings):

        """Handle settings updates"""

        if 'tax_rate' in settings:

            self.tax_rate = float(settings.get('tax_rate', 8.0))

            self.update_totals()



    def load_products(self):

        """Load products into the products table"""

        try:

            if not hasattr(self, 'products_table') or self.products_table is None:

                return



            from pos_app.models.database import Product

            # Sort by product creation date (descending - newest first)

            # Try to sort by created_at if available, otherwise fall back to ID

            try:

                products = self.controller.session.query(Product).order_by(Product.created_at.desc()).all()

            except:

                # Fallback if created_at doesn't exist

                products = self.controller.session.query(Product).order_by(Product.id.desc()).all()



            self.products_table.setRowCount(len(products))



            for row, product in enumerate(products):

                # Product name (column 0)

                name_item = QTableWidgetItem(getattr(product, 'name', ''))

                self.products_table.setItem(row, 0, name_item)



                # Barcode (column 1)

                barcode_item = QTableWidgetItem(getattr(product, 'barcode', ''))

                self.products_table.setItem(row, 1, barcode_item)



                # Stock level with color coding

                stock = getattr(product, 'stock_level', 0)

                stock_item = QTableWidgetItem(str(stock))



                # Set colors using proper methods

                from PySide6.QtGui import QFont, QColor

                font = QFont()

                font.setBold(True)

                stock_item.setFont(font)



                if stock <= 0:

                    stock_item.setForeground(QColor("#ef4444"))  # Red for out of stock

                elif stock <= getattr(product, 'reorder_level', 5):

                    stock_item.setForeground(QColor("#f59e0b"))  # Orange for low stock

                else:

                    stock_item.setForeground(QColor("#10b981"))  # Green for good stock



                self.products_table.setItem(row, 2, stock_item)



                # Retail price

                retail_price = getattr(product, 'retail_price', 0)

                try:

                    retail_item = QTableWidgetItem(f"Rs {float(retail_price):,.2f}")

                except:

                    retail_item = QTableWidgetItem("Rs 0.00")

                self.products_table.setItem(row, 3, retail_item)



                # Wholesale price

                wholesale_price = getattr(product, 'wholesale_price', 0)

                try:

                    wholesale_item = QTableWidgetItem(f"Rs {float(wholesale_price):,.2f}")

                except:

                    wholesale_item = QTableWidgetItem("Rs 0.00")

                self.products_table.setItem(row, 4, wholesale_item)



                # Add to cart button

                add_btn = QPushButton("➕ Add")

                add_btn.setStyleSheet("""

                    QPushButton {

                        background: #3b82f6;

                        color: Qt.white;

                        border: none;

                        border-radius: 6px;

                        padding: 6px 12px;

                        font-size: 12px;

                        font-weight: 500;

                        min-width: 60px;

                    }

                    QPushButton:hover {

                        background: #2563eb;

                        color: Qt.white;

                    }

                    QPushButton:pressed {

                        background: #1d4ed8;

                        color: Qt.white;

                    }

                """)

                add_btn.clicked.connect(lambda checked, p=product: self.add_product_to_cart(p))

                self.products_table.setCellWidget(row, 5, add_btn)



        except Exception as e:

            print(f"Error loading products: {e}")



    def _on_product_item_double_clicked(self, item):

        """Handle double-click on product table to edit price"""

        try:

            from PySide6.QtWidgets import QInputDialog

        except ImportError:

            from PyQt6.QtWidgets import QInputDialog

        

        row = item.row()

        col = item.column()

        

        # Only allow editing retail price (col 3) or wholesale price (col 4)

        if col not in (3, 4):

            return

        

        # Get current price value

        current_text = self.products_table.item(row, col).text()

        # Remove "Rs " prefix if present

        current_price = current_text.replace("Rs ", "").replace(",", "").strip()

        

        # Get product from database

        try:

            from pos_app.models.database import Product

            products = self.controller.session.query(Product).all()

            if row < len(products):

                product = products[row]

                

                # Show input dialog

                new_price_str, ok = QInputDialog.getText(

                    self, 

                    f"Edit {'Retail' if col == 3 else 'Wholesale'} Price",

                    f"Enter new price for {product.name}:",

                    text=current_price

                )

                

                if ok and new_price_str:

                    try:

                        new_price = float(new_price_str)

                        if col == 3:

                            product.retail_price = new_price

                        else:

                            product.wholesale_price = new_price

                        

                        self.controller.session.commit()

                        self.load_products()  # Reload to show updated prices

                    except ValueError:

                        from PySide6.QtWidgets import QMessageBox

                        try:

                            from PySide6.QtWidgets import QMessageBox

                        except ImportError:

                            from PyQt6.QtWidgets import QMessageBox

                        msg = QMessageBox(self)

                        msg.setIcon(QMessageBox.Warning)

                        msg.setWindowTitle("Invalid Input")

                        msg.setText("Please enter a valid number")

                        msg.setStandardButtons(QMessageBox.Ok)

                        msg.exec()

        except Exception as e:

            print(f"Error editing product price: {e}")



    def _on_cart_item_changed(self, item):

        """Handle when user edits a cart table cell inline"""

        try:

            if not item:

                return

            

            row = item.row()

            col = item.column()

            

            # Only handle QTY (col 1) and SALE PRICE (col 3) edits

            if col not in (1, 3):

                return

            

            if row >= len(self.current_cart):

                return

            

            cart_item = self.current_cart[row]

            new_text = item.text().strip()

            

            # Remove "Rs " prefix if present

            if new_text.startswith("Rs "):

                new_text = new_text[3:].strip()

            

            # Remove commas from number

            new_text = new_text.replace(',', '')

            

            try:

                new_value = float(new_text)

            except ValueError:

                # Invalid input, revert to original

                self.update_cart_table()

                return

            

            if col == 1:  # QTY column

                if new_value <= 0:

                    self.update_cart_table()

                    return

                cart_item['quantity'] = new_value

                cart_item['total'] = new_value * float(cart_item.get('price', 0))

            

            elif col == 3:  # SALE PRICE column

                if new_value < 0:

                    self.update_cart_table()

                    return

                cart_item['price'] = new_value

                cart_item['total'] = float(cart_item.get('quantity', 0)) * new_value

            

            # Temporarily disconnect to avoid recursion

            self.cart_table.itemChanged.disconnect(self._on_cart_item_changed)

            

            # Update the cart item data

            if col == 1:  # QTY column

                if new_value <= 0:

                    self.update_cart_table()

                    return

                cart_item['quantity'] = new_value

                cart_item['total'] = new_value * float(cart_item.get('price', 0))

            elif col == 3:  # SALE PRICE column

                if new_value < 0:

                    self.update_cart_table()

                    return

                cart_item['price'] = new_value

                cart_item['total'] = float(cart_item.get('quantity', 0)) * new_value

            

            # Update only the changed cell and related cells without rebuilding the table

            if col == 1:  # QTY changed

                # Update Total column (4)

                total_item = self.cart_table.item(row, 4)

                if total_item:

                    total_item.setText(f"Rs {cart_item['total']:,.2f}")

                # Update Profit column (5)

                profit = cart_item['total'] - (float(cart_item.get('quantity', 0)) * float(cart_item.get('purchase_price', 0)))

                profit_item = self.cart_table.item(row, 5)

                if profit_item:

                    profit_item.setText(f"Rs {profit:,.2f}")

            elif col == 3:  # Sale Price changed

                # Update Total column (4)

                total_item = self.cart_table.item(row, 4)

                if total_item:

                    total_item.setText(f"Rs {cart_item['total']:,.2f}")

                # Update Profit column (5)

                profit = cart_item['total'] - (float(cart_item.get('quantity', 0)) * float(cart_item.get('purchase_price', 0)))

                profit_item = self.cart_table.item(row, 5)

                if profit_item:

                    profit_item.setText(f"Rs {profit:,.2f}")

            

            self.update_totals()

            self.cart_table.itemChanged.connect(self._on_cart_item_changed)

            

        except Exception as e:

            print(f"ERROR in _on_cart_item_changed: {e}")

            import traceback

            traceback.print_exc()

    

    def on_cart_cell_double_clicked(self, row, column):

        """Handle double-click on cart table cells - start inline editing"""

        try:

            print(f"[DEBUG] on_cart_cell_double_clicked: row={row}, column={column}")

            # Allow editing on QTY (col 1) or SALE PRICE (col 3)

            if column not in (1, 3):

                print(f"[DEBUG] Column {column} is not editable")

                return

            

            if row >= len(self.current_cart):

                print(f"[DEBUG] Row {row} >= cart length {len(self.current_cart)}")

                return

            

            print(f"[DEBUG] Starting edit for row {row}, column {column}")

            # Start editing the cell

            self.cart_table.editItem(self.cart_table.item(row, column))

                

        except Exception as e:

            print(f"ERROR in on_cart_cell_double_clicked: {e}")

            import traceback

            traceback.print_exc()



    def update_cart_row(self, row_index):

        """Update only a specific row in the cart table"""

        if not self.current_cart or row_index >= len(self.current_cart):

            return

            

        item = self.current_cart[row_index]

        

        # Update QTY column

        qty_item = self.cart_table.item(row_index, 1)

        if qty_item:

            qty_item.setText(str(item['quantity']))

        

        # Update Sale Price column

        price_item = self.cart_table.item(row_index, 3)

        if price_item:

            price_item.setText(f"{item['price']:.2f}")

        

        # Update Total column

        total = item['quantity'] * item['price']

        total_item = self.cart_table.item(row_index, 4)

        if total_item:

            total_item.setText(f"{total:.2f}")

        

        # Update Profit column

        profit = total - (item['quantity'] * item.get('purchase_price', 0))

        profit_item = self.cart_table.item(row_index, 5)

        if profit_item:

            profit_item.setText(f"{profit:.2f}")



    def update_cart_table(self):

        """Update the cart table with current items"""

        print(f"[DEBUG] update_cart_table called with {len(self.current_cart)} items")

        import traceback

        print("[DEBUG] Call stack:")

        for line in traceback.format_stack()[-3:-1]:  # Show last 2 frames

            print(f"  {line.strip()}")

        

        # Prevent re-entry

        if getattr(self, '_updating_cart', False):

            print("[DEBUG] Already updating cart, skipping")

            return

        self._updating_cart = True

        

        # Don't update if table is being edited to avoid destroying the editor

        if hasattr(self, 'cart_table') and self.cart_table.state() == QTableWidget.EditingState:

            print("[DEBUG] Table is in editing state, skipping update_cart_table")

            self._updating_cart = False  # Reset flag before returning

            return

        

        try:

            # Block signals to prevent feedback loop

            if hasattr(self, 'cart_table'):

                self.cart_table.blockSignals(True)

            

            show_extra = bool(getattr(self, 'is_refund_mode', False))

            self.cart_table.setColumnHidden(7, not show_extra)

            self.cart_table.setColumnHidden(9, not show_extra)

            self.cart_table.setColumnHidden(8, False)

        except Exception:

            pass

        self.cart_table.setRowCount(len(self.current_cart))



        for i, item in enumerate(self.current_cart):

            print(f"[DEBUG] Processing cart item {i}: {item.get('name', 'Unknown')}")



            # Check if this item is marked for refund

            marked_items = getattr(self, '_refund_marked_items', set())

            is_marked_for_refund = item.get('id') in marked_items



            # Determine background color for this row

            if is_marked_for_refund:

                bg_color = QColor("#fee2e2")  # Light red for marked refund items

                print(f"[DEBUG] Row {i}: Setting RED background (marked for refund)")

            elif i % 2 == 0:

                bg_color = QColor("#ffffff")  # White for even rows

                print(f"[DEBUG] Row {i}: Setting WHITE background")

            else:

                bg_color = QColor("#f8fafc")  # Light gray for odd rows

                print(f"[DEBUG] Row {i}: Setting LIGHT GRAY background")

            

            # Product name (column 0 - main column)

            name = (

                item.get('name')

                or item.get('product_name')

                or str(item.get('id', ''))

            )

            # Add REFUND prefix if marked for refund

            if is_marked_for_refund:

                name = f"🔴 REFUND: {name}"

            name_item = QTableWidgetItem(name)

            name_item.setForeground(QColor("#1e293b"))  # Explicit text color

            name_item.setBackground(bg_color)  # Explicit background color

            try:

                name_item.setToolTip(name)

            except Exception:

                pass

            self.cart_table.setItem(i, 0, name_item)



            # Quantity (column 1 - narrow, centered)

            try:

                is_inline_refund = bool(self.is_refund_mode) or ('max_refund_qty' in item) or ('bought_qty' in item)

            except Exception:

                is_inline_refund = False



            if is_inline_refund:

                try:

                    max_q = float(item.get('max_refund_qty', item.get('bought_qty', 0)) or 0)

                except Exception:

                    max_q = 0.0



                try:

                    cur_q = float(item.get('quantity', 0) or 0)

                except Exception:

                    cur_q = 0.0



                # Set a background item so row coloring stays consistent

                qty_item = QTableWidgetItem("")

                qty_item.setBackground(bg_color)

                self.cart_table.setItem(i, 1, qty_item)



                try:

                    qty_spin = QDoubleSpinBox()

                    qty_spin.setMinimum(0.0)

                    qty_spin.setMaximum(max_q)

                    qty_spin.setSingleStep(1.0)

                    qty_spin.setDecimals(2)

                    qty_spin.setValue(cur_q)

                    try:

                        qty_spin.setButtonSymbols(QAbstractSpinBox.NoButtons)

                    except Exception:

                        pass

                    try:

                        qty_spin.setAlignment(Qt.AlignCenter)

                    except Exception:

                        pass

                    try:

                        qty_spin.setMinimumWidth(90)

                        qty_spin.setMaximumWidth(130)

                        qty_spin.setMinimumHeight(28)

                    except Exception:

                        pass

                    try:

                        # Use red background if marked for refund, otherwise white

                        spin_bg = "#fee2e2" if is_marked_for_refund else "#ffffff"

                        qty_spin.setStyleSheet(f"""

                            QDoubleSpinBox {{

                                border: 2px solid #334155;

                                border-radius: 6px;

                                padding: 4px 8px;

                                font-size: 14px;

                                font-weight: 700;

                                background: {spin_bg};

                                color: #0f172a;

                                selection-background-color: #3b82f6;

                                selection-color: #0f172a;

                                margin: 0px;

                            }}

                            QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{

                                width: 0px;

                                height: 0px;

                                border: none;

                                background: transparent;

                            }}

                            QDoubleSpinBox::up-arrow, QDoubleSpinBox::down-arrow {{

                                width: 0px;

                                height: 0px;

                            }}

                            QDoubleSpinBox::drop-down {{

                                width: 0px;

                                border: none;

                            }}

                            QDoubleSpinBox:focus {{

                                border: 2px solid #2563eb;

                                background: {spin_bg};

                                color: #0f172a;

                            }}

                        """)

                    except Exception:

                        pass

                    try:

                        qty_spin.setToolTip(f"Max refund: {max_q}")

                    except Exception:

                        pass

                    try:

                        qty_spin.valueChanged.connect(lambda v, row=i: self._on_inline_refund_qty_changed(row, v))

                    except Exception:

                        pass



                    # Don't use setCellWidget as it prevents double-clicks

                    # self.cart_table.setCellWidget(i, 1, qty_spin)

                except Exception:

                    # Fallback to plain text

                    qty_item = QTableWidgetItem(str(cur_q))

                    qty_item.setTextAlignment(Qt.AlignCenter)

                    qty_item.setForeground(QColor("#1e293b"))

                    qty_item.setBackground(bg_color)

                    self.cart_table.setItem(i, 1, qty_item)



                try:

                    if max_q > 0:

                        name_item.setToolTip(f"{name}\nBought Qty: {max_q}")

                except Exception:

                    pass

            else:

                # Editable quantity field (plain text, no widget)

                try:

                    qty_val = float(item.get('quantity', 0) or 0)

                except Exception:

                    qty_val = 0

                

                qty_item = QTableWidgetItem(str(qty_val))

                qty_item.setTextAlignment(Qt.AlignCenter)

                qty_item.setForeground(QColor("#1e293b"))

                qty_item.setBackground(bg_color)

                # Make it editable

                qty_item.setFlags(qty_item.flags() | Qt.ItemIsEditable)

                print(f"[DEBUG] QTY item flags: {qty_item.flags()}, editable: {bool(qty_item.flags() & Qt.ItemIsEditable)}")

                self.cart_table.setItem(i, 1, qty_item)



            if show_extra:

                try:

                    bought_qty_val = item.get('bought_qty', '')

                    bought_item = QTableWidgetItem(str(bought_qty_val))

                    bought_item.setTextAlignment(Qt.AlignCenter)

                    bought_item.setForeground(QColor("#1e293b"))

                    bought_item.setBackground(bg_color)

                    self.cart_table.setItem(i, 7, bought_item)

                except Exception:

                    pass



                try:

                    dval = float(item.get('item_discount', 0.0) or 0.0)

                except Exception:

                    dval = 0.0

                dtype = str(item.get('item_discount_type', '') or '').strip().upper()

                disc_txt = ""

                if dval:

                    if dtype in ("PERCENT", "PERCENTAGE"):

                        disc_txt = f"{dval:g}%"

                    else:

                        disc_txt = f"Rs {dval:,.2f}"

                else:

                    disc_txt = "Rs 0.00"

                try:

                    disc_item = QTableWidgetItem(disc_txt)

                    disc_item.setTextAlignment(Qt.AlignCenter)

                    disc_item.setForeground(QColor("#1e293b"))

                    disc_item.setBackground(bg_color)

                    self.cart_table.setItem(i, 9, disc_item)

                except Exception:

                    pass



            # Purchase price (column 2) - hide for worker users

            if not self._is_worker_user():

                purchase_price = item.get('purchase_price', 0)

                purchase_item = QTableWidgetItem(f"Rs {purchase_price:,.2f}")

                purchase_item.setTextAlignment(Qt.AlignRight)

                purchase_item.setForeground(QColor("#1e293b"))  # Explicit text color

                purchase_item.setBackground(bg_color)  # Explicit background color

                self.cart_table.setItem(i, 2, purchase_item)

            else:

                # Worker user - set empty item for column 2

                empty_item = QTableWidgetItem("")

                empty_item.setBackground(bg_color)

                self.cart_table.setItem(i, 2, empty_item)



            # Unit / sale price (column 3) - editable

            try:

                sale_price = float(item.get('price', 0.0) or 0.0)

            except Exception:

                sale_price = 0.0

            sale_item = QTableWidgetItem(f"{sale_price:.2f}")  # Just the number, no "Rs" prefix

            sale_item.setTextAlignment(Qt.AlignRight)

            font = QFont()

            font.setBold(True)

            font.setPointSize(11)

            sale_item.setFont(font)

            sale_item.setForeground(QColor("#0f766e"))  # Teal/dark cyan for visibility

            sale_item.setBackground(bg_color)  # Explicit background color

            # Make it editable

            sale_item.setFlags(sale_item.flags() | Qt.ItemIsEditable)

            print(f"[DEBUG] Sale Price item flags: {sale_item.flags()}, editable: {bool(sale_item.flags() & Qt.ItemIsEditable)}")

            self.cart_table.setItem(i, 3, sale_item)



            # Total sale amount (column 4)

            eff_price = sale_price

            try:

                if show_extra and getattr(self, 'is_refund_mode', False):

                    eff_price = float(item.get('refund_unit_subtotal', sale_price) or sale_price)

            except Exception:

                eff_price = sale_price

            total_sale = item['quantity'] * eff_price

            total_item = QTableWidgetItem(f"Rs {total_sale:,.2f}")

            total_item.setTextAlignment(Qt.AlignRight)

            font = QFont()

            font.setBold(True)

            total_item.setFont(font)

            total_item.setForeground(QColor("#10b981"))

            total_item.setBackground(bg_color)  # Explicit background color

            self.cart_table.setItem(i, 4, total_item)



            # Profit per item (column 5) - hide for worker users

            if not self._is_worker_user():

                profit_per_item = (eff_price - purchase_price) * item['quantity']

                profit_item = QTableWidgetItem(f"Rs {profit_per_item:,.2f}")

                profit_item.setTextAlignment(Qt.AlignRight)

                font = QFont()

                font.setBold(True)

                profit_item.setFont(font)

                if profit_per_item > 0:

                    profit_item.setForeground(QColor("#10b981"))  # Green for profit

                elif profit_per_item < 0:

                    profit_item.setForeground(QColor("#ef4444"))  # Red for loss

                else:

                    profit_item.setForeground(QColor("#6b7280"))  # Gray for break-even

                profit_item.setBackground(bg_color)  # Explicit background color

                self.cart_table.setItem(i, 5, profit_item)

            else:

                # Worker user - set empty item for column 5

                empty_item = QTableWidgetItem("")

                empty_item.setBackground(bg_color)

                self.cart_table.setItem(i, 5, empty_item)



            # Remove button (column 6) - use table item instead of widget to respect background

            remove_item = QTableWidgetItem("🗑️ Remove")

            remove_item.setTextAlignment(Qt.AlignCenter)

            remove_item.setForeground(QColor("#dc2626"))  # Red text

            remove_item.setBackground(bg_color)  # Explicit background color

            remove_item.setFont(QFont())  # Use default font

            self.cart_table.setItem(i, 6, remove_item)

            

            # Store index in item data for click handling

            remove_item.setData(Qt.UserRole, i)



            # Stock (column 8) - always visible

            try:

                stock_val = item.get('stock_level', '')

                if stock_val in (None, ""):

                    # Fallback: try to fetch live stock from DB

                    try:

                        from pos_app.models.database import Product

                        pid = item.get('id', None)

                        if pid is not None:

                            prod = self.controller.session.get(Product, pid)

                            if prod is not None:

                                stock_val = int(getattr(prod, 'stock_level', 0) or 0)

                    except Exception:

                        pass



                stock_item = QTableWidgetItem(str(stock_val if stock_val is not None else ""))

                stock_item.setTextAlignment(Qt.AlignCenter)

                stock_item.setForeground(QColor("#1e293b"))

                stock_item.setBackground(bg_color)

                self.cart_table.setItem(i, 8, stock_item)

            except Exception:

                pass

            

            # Reduce row height for compact display

            try:

                self.cart_table.setRowHeight(i, 36)  # Compact but safe for embedded widgets

            except Exception:

                pass



        # Always ensure the view is scrolled to the first column so the

        # product name remains visible, even if the user scrolled to the right.

        try:

            hbar = self.cart_table.horizontalScrollBar()

            if hbar is not None:

                hbar.setValue(0)

        except Exception:

            pass

        

        # Auto-resize columns based on content

        self._auto_resize_cart_columns()

        

        # Always unblock signals and reset flag

        if hasattr(self, 'cart_table'):

            self.cart_table.blockSignals(False)

        self._updating_cart = False



    def _cart_qty_inc(self, row: int):

        try:

            if row < 0 or row >= len(getattr(self, 'current_cart', []) or []):

                return

            try:

                cur = int(float(self.current_cart[row].get('quantity', 0) or 0))

            except Exception:

                cur = 0

            self.current_cart[row]['quantity'] = cur + 1

            self.update_cart_table()

            self.update_totals()

        except Exception:

            pass



    def _cart_qty_dec(self, row: int):

        try:

            if row < 0 or row >= len(getattr(self, 'current_cart', []) or []):

                return

            try:

                cur = int(float(self.current_cart[row].get('quantity', 0) or 0))

            except Exception:

                cur = 0

            if cur <= 1:

                try:

                    self.current_cart.pop(row)

                except Exception:

                    return

            else:

                self.current_cart[row]['quantity'] = cur - 1

            self.update_cart_table()

            self.update_totals()

        except Exception:

            pass



    def _auto_resize_cart_columns(self):

        """Auto-resize cart table columns based on content with smart sizing"""

        try:

            # Get the horizontal header

            header = self.cart_table.horizontalHeader()

            

            # Resize columns based on content

            self.cart_table.resizeColumnsToContents()

            

            # Define minimum widths for readability

            min_widths = {

                0: 150,  # Product Name - minimum width

                1: 90,   # Qty / Refund Qty - minimum width

                2: 80,   # Purchase Price - minimum width  

                3: 80,   # Sale Price - minimum width

                4: 80,   # Total - minimum width

                5: 80,   # Profit - minimum width

                6: 50,   # Remove - minimum width

                7: 95,   # Bought Qty

                8: 95,   # Stock

                9: 80    # Item Disc

            }

            

            # Define maximum widths to prevent overly wide columns

            max_widths = {

                0: 300,  # Product Name - maximum width

                1: 140,   # Qty / Refund Qty - maximum width

                2: 120,  # Purchase Price - maximum width

                3: 120,  # Sale Price - maximum width

                4: 120,  # Total - maximum width

                5: 120,  # Profit - maximum width

                6: 80,   # Remove - maximum width

                7: 120,   # Bought Qty

                8: 120,   # Stock

                9: 120   # Item Disc

            }

            

            # Apply min/max width constraints

            for col in range(self.cart_table.columnCount()):

                current_width = header.sectionSize(col)

                

                # Apply minimum width

                if current_width < min_widths.get(col, 60):

                    header.resizeSection(col, min_widths.get(col, 60))

                

                # Apply maximum width

                elif current_width > max_widths.get(col, 200):

                    header.resizeSection(col, max_widths.get(col, 200))

                

                # Add small padding for better readability

                elif col in [2, 3, 4, 5]:  # Price columns

                    header.resizeSection(col, current_width + 10)

            

        except Exception as e:

            # Fallback to default sizing if auto-resize fails

            try:

                header = self.cart_table.horizontalHeader()

                header.resizeSection(0, 200)  # Product Name

                header.resizeSection(1, 110)   # Qty

                header.resizeSection(2, 100)  # Purchase Price

                header.resizeSection(3, 100)  # Sale Price

                header.resizeSection(4, 100)  # Total

                header.resizeSection(5, 80)   # Profit

                header.resizeSection(6, 70)   # Remove

                try:

                    header.resizeSection(7, 110)   # Bought Qty

                    header.resizeSection(8, 110)   # Stock

                    header.resizeSection(9, 90)   # Item Disc

                except Exception:

                    pass

            except Exception:

                pass



    def _update_refund_discount_from_current_cart(self):

        try:

            if not getattr(self, 'is_refund_mode', False):

                return

            try:

                original_subtotal = float(getattr(self, '_refund_original_items_subtotal', getattr(self, '_refund_original_subtotal', 0.0)) or 0.0)

            except Exception:

                original_subtotal = 0.0

            try:

                original_discount = float(getattr(self, '_refund_original_discount', 0.0) or 0.0)

            except Exception:

                original_discount = 0.0



            selected_subtotal = 0.0

            for ci in (self.current_cart or []):

                try:

                    q = float(ci.get('quantity', 0) or 0)

                except Exception:

                    q = 0.0

                try:

                    unit_sub = float(ci.get('refund_unit_subtotal', ci.get('price', 0.0)) or 0.0)

                except Exception:

                    unit_sub = 0.0

                selected_subtotal += q * unit_sub



            refund_discount = 0.0

            if original_subtotal > 0 and original_discount > 0 and selected_subtotal > 0:

                refund_discount = (original_discount * selected_subtotal) / original_subtotal

                refund_discount = min(refund_discount, selected_subtotal)



            self._set_discount_amount_value(refund_discount)

        except Exception:

            return



    def _refund_selected_cart_row_full(self):

        try:

            if not getattr(self, 'is_refund_mode', False):

                return False

            if not hasattr(self, 'cart_table'):

                return False

            row = self.cart_table.currentRow()

            if row < 0 or row >= len(self.current_cart or []):

                return False



            try:

                max_q = float(self.current_cart[row].get('max_refund_qty', self.current_cart[row].get('bought_qty', 0)) or 0)

            except Exception:

                max_q = 0.0



            if max_q <= 0:

                return False



            w = None

            try:

                w = self.cart_table.cellWidget(row, 1)

            except Exception:

                w = None

            try:

                if w is not None and hasattr(w, 'setValue'):

                    w.setValue(max_q)

                else:

                    self.current_cart[row]['quantity'] = max_q

                    self._update_refund_discount_from_current_cart()

                    self.update_cart_table()

                    self.update_totals()

            except Exception:

                self.current_cart[row]['quantity'] = max_q

                self._update_refund_discount_from_current_cart()

                self.update_cart_table()

                self.update_totals()



            try:

                self.cart_table.setFocus()

                self.cart_table.selectRow(row)

            except Exception:

                pass

            return True

        except Exception:

            return False



    def _refund_selected_cart_row_only(self):

        """Refund only the selected item (set its refund qty to max and set all others to 0)."""

        try:

            if not getattr(self, 'is_refund_mode', False):

                return False

            if not hasattr(self, 'cart_table'):

                return False



            row = self.cart_table.currentRow()

            if row < 0 and self.cart_table.rowCount() > 0:

                try:

                    self.cart_table.setFocus()

                    self.cart_table.selectRow(0)

                except Exception:

                    pass

                row = self.cart_table.currentRow()



            if row < 0 or row >= len(self.current_cart or []):

                return False



            # First set all other rows refund qty to 0

            try:

                for r in range(len(self.current_cart or [])):

                    if r == row:

                        continue

                    try:

                        self.current_cart[r]['quantity'] = 0.0

                    except Exception:

                        pass

                    try:

                        w_other = self.cart_table.cellWidget(r, 1)

                        if w_other is not None and hasattr(w_other, 'setValue'):

                            w_other.setValue(0.0)

                    except Exception:

                        pass

            except Exception:

                pass



            # Now set selected row to full/bought qty

            return bool(self._refund_selected_cart_row_full())

        except Exception:

            return False



    def _on_inline_refund_qty_changed(self, row: int, value):

        try:

            if row < 0 or row >= len(self.current_cart or []):

                return

            try:

                v = float(value)

            except Exception:

                v = 0.0

            self.current_cart[row]['quantity'] = v



            self._update_refund_discount_from_current_cart()



            try:

                if getattr(self, 'is_refund_mode', False):

                    sale_price = float(self.current_cart[row].get('refund_unit_subtotal', self.current_cart[row].get('price', 0.0)) or 0.0)

                else:

                    sale_price = float(self.current_cart[row].get('price', 0.0) or 0.0)

                purchase_price = float(self.current_cart[row].get('purchase_price', 0.0) or 0.0)

                total_sale = v * sale_price

                profit_per_item = (sale_price - purchase_price) * v



                it_total = self.cart_table.item(row, 4)

                if it_total is not None:

                    it_total.setText(f"Rs {total_sale:,.2f}")



                it_profit = self.cart_table.item(row, 5)

                if it_profit is not None:

                    it_profit.setText(f"Rs {profit_per_item:,.2f}")

            except Exception:

                pass



            self.update_totals()

        except Exception:

            return



    def _on_cart_item_clicked(self, row, col):

        """Handle cart table cell clicks - specifically for Remove column"""

        print(f"[DEBUG] Cart cell clicked: row={row}, col={col}")

        # Check if Remove column (column 6) was clicked

        if col == 6:

            print(f"[DEBUG] Remove column clicked! Removing row {row}")

            # Use row directly since cellClicked gives us the correct row

            self.remove_cart_item(row)



    def update_totals(self):

        """Update all total labels with enhanced calculations"""

        if not self.current_cart:

            items_count = 0

            subtotal = total_cost = total_profit = tax = total = 0.0

        else:

            # Calculate enhanced totals

            items_count = sum(item['quantity'] for item in self.current_cart)

            subtotal = sum(item['quantity'] * item['price'] for item in self.current_cart)

            total_cost = sum(item['quantity'] * item.get('purchase_price', 0) for item in self.current_cart)

            total_profit = subtotal - total_cost

            

            # Apply discount if exists (fixed amount instead of percentage)

            discount = getattr(self, 'discount_amount', QDoubleSpinBox()).value()

            taxable_amount = subtotal - discount

            tax = taxable_amount * (self.tax_rate / 100)

            total = taxable_amount + tax



        # Auto-update amount_paid to match total (both when adding and removing items)

        if hasattr(self, 'amount_paid_input'):

            print(f"[DEBUG] Auto-updating amount_paid: total={total}, current_value={self.amount_paid_input.value()}")

            # Block signals to avoid interference with calculate_change

            self.amount_paid_input.blockSignals(True)

            try:

                # Always set amount_paid to match the current total

                self.amount_paid_input.setValue(total)

                print(f"[DEBUG] Set amount_paid to {total}")

            finally:

                self.amount_paid_input.blockSignals(False)

        else:

            print(f"[DEBUG] amount_paid_input not found!")



        # Update enhanced summary labels

        if hasattr(self, 'cart_items_label'):

            self.cart_items_label.setText(f"Items: {items_count}")

        if hasattr(self, 'cart_subtotal_label'):

            self.cart_subtotal_label.setText(f"Subtotal: Rs {subtotal:,.2f}")

        if hasattr(self, 'cart_total_cost_label'):

            self.cart_total_cost_label.setText(f"Total Cost: Rs {total_cost:,.2f}")

        if hasattr(self, 'cart_profit_label'):

            profit_text = f"Total Profit: Rs {total_profit:,.2f}"

            if hasattr(self, 'cart_profit_label'):

                self.cart_profit_label.setText(profit_text)

                # Color code profit label

                if total_profit > 0:

                    self.cart_profit_label.setStyleSheet("font-size: 14px; color: #10b981; margin: 2px 0; font-weight: 600;")

                elif total_profit < 0:

                    self.cart_profit_label.setStyleSheet("font-size: 14px; color: #ef4444; margin: 2px 0; font-weight: 600;")

                else:

                    self.cart_profit_label.setStyleSheet("font-size: 14px; color: #6b7280; margin: 2px 0;")

        if hasattr(self, 'cart_tax_label'):

            self.cart_tax_label.setText(f"Tax ({self.tax_rate}%): Rs {tax:,.2f}")

        if hasattr(self, 'cart_total_label'):

            self.cart_total_label.setText(f"Final Total: Rs {total:,.2f}")



        # Amount Paid is user input; do not overwrite it here.



    def add_product_to_cart(self, product):

        """Add a product to enhanced cart with purchase/sale prices"""

        # Block adding new products while refunding; refund mode must only use invoice items.

        if getattr(self, 'is_refund_mode', False):

            try:

                QMessageBox.warning(self, "Refund", "You are in refund mode. You can only refund items from loaded invoice.")

            except Exception:

                pass

            return

        

        # Prevent re-entry during product addition

        if getattr(self, '_adding_product', False):

            print("[DEBUG] Already adding product, skipping")

            return

        self._adding_product = True



        # ------------------------------------------------------------------

        # Stock calculation - use stock_level field as primary source

        # ------------------------------------------------------------------

        try:

            stock_level = 0

            if product:

                # Fetch freshest values from DB

                product_id = getattr(product, "id", None)

                if product_id:

                    current_product = (

                        self.controller.session.query(type(product))

                        .filter_by(id=product_id)

                        .first()

                    )

                    if current_product:

                        # Use stock_level field as primary source of truth

                        stock_level = int(getattr(current_product, "stock_level", 0) or 0)

                    else:

                        stock_level = int(getattr(product, "stock_level", 0) or 0)

                else:

                    stock_level = int(getattr(product, "stock_level", 0) or 0)

            else:

                stock_level = 0

        except Exception:

            stock_level = int(getattr(product, "stock_level", 0) or 0)



        # Check if product already in cart

        for item in self.current_cart:

            if item['id'] == getattr(product, 'id', None):

                # Stock check - only for retail, skip for wholesale to allow large orders

                if not self.is_wholesale_selected() and item['quantity'] + 1 > stock_level:

                    msg = QMessageBox(self)

                    msg.setIcon(QMessageBox.Warning)

                    msg.setWindowTitle("Stock")

                    msg.setText(f"Insufficient stock for this product. Available: {stock_level}, Requested: {item['quantity'] + 1}")

                    msg.setStandardButtons(QMessageBox.Ok)

                    msg.exec()

                    self._adding_product = False

                    return

                # Increment quantity if stock is sufficient

                item['quantity'] += 1

                self.update_cart_table()

                self.update_totals()

                self._adding_product = False

                return



        # Add new item to cart with enhanced data

        sale_price = self._get_sale_price_for_product(product)

        cart_item = {

            'id': getattr(product, 'id', None),

            'name': getattr(product, 'name', ''),

            'price': float(sale_price),

            'purchase_price': float(getattr(product, 'purchase_price', 0) or 0.0),

            'quantity': 1,

            'stock_level': stock_level

        }

        

        # Stock check for new item - only for retail

        if not self.is_wholesale_selected() and cart_item['quantity'] > stock_level:

            msg = QMessageBox(self)

            msg.setIcon(QMessageBox.Warning)

            msg.setWindowTitle("Stock")

            msg.setText(f"Insufficient stock for this product. Available: {stock_level}, Requested: {cart_item['quantity']}")

            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec()

            self._adding_product = False

            return

        

        self.current_cart.append(cart_item)

        self.update_cart_table()

        self.update_totals()

        self._adding_product = False



    def _get_sale_price_for_product(self, product):

        """Return sale price based on current sale type selection (retail/wholesale)."""

        try:

            is_wholesale = self.is_wholesale_selected()

            if is_wholesale:

                return float(getattr(product, 'wholesale_price', 0.0) or 0.0)

            return float(getattr(product, 'retail_price', 0.0) or 0.0)

        except Exception:

            return float(getattr(product, 'retail_price', 0.0) or 0.0)



    def is_wholesale_selected(self) -> bool:

        try:

            if hasattr(self, 'sale_type_combo'):

                txt = (self.sale_type_combo.currentText() or '').lower()

                return 'wholesale' in txt

        except Exception:

            pass

        return False



    def on_sale_type_changed(self, _txt: str):

        """Reprice cart items when sale type changes between retail/wholesale."""

        try:

            from pos_app.models.database import Product

            is_wholesale = self.is_wholesale_selected()

            for item in self.current_cart:

                pid = item.get('id')

                if not pid:

                    continue

                try:

                    p = self.controller.session.query(Product).filter(Product.id == pid).first()

                    if not p:

                        continue

                    # Only update sale price; keep purchase_price as stored cost

                    item['price'] = self._get_sale_price_for_product(p)

                except Exception:

                    continue

            self.update_cart_table()

            self.update_totals()

            self.calculate_change()

        except Exception:

            pass



    def _on_search_text_changed(self, text):

        """Handle search text changes with debounce to avoid lag with fast barcode scanners"""

        # Restart the debounce timer

        if hasattr(self, '_search_timer'):

            self._search_timer.stop()

            self._search_timer.start()

    

    def search_products(self):

        """Search products by name, SKU, or barcode and show suggestions (don't auto-add)"""

        search_text = self.product_search.text().lower().strip()

        if len(search_text) < 1:

            # Clear suggestions if search is empty

            if hasattr(self, 'search_suggestions_list'):

                self.search_suggestions_list.clear()

            return

        

        try:

            from pos_app.models.database import Product

            # Search by name, SKU, AND barcode

            products = self.controller.session.query(Product).filter(

                (Product.name.ilike(f'%{search_text}%')) | 

                (Product.sku.ilike(f'%{search_text}%')) |

                (Product.barcode.ilike(f'%{search_text}%'))

            ).limit(1000).all()

            

            # Show suggestions in a list (don't auto-add)

            if hasattr(self, 'search_suggestions_list'):

                self.search_suggestions_list.clear()

                for product in products:

                    # Show name, SKU, and barcode in suggestions

                    barcode_str = f"BAR: {product.barcode}" if product.barcode else "BAR: -"

                    sku_str = f"SKU: {product.sku}" if product.sku else "SKU: -"

                    display_text = f"{product.name} ({barcode_str} | {sku_str}) - Rs {product.retail_price:.2f}"

                    item = QListWidgetItem(display_text)

                    item.setData(Qt.UserRole, product.id)

                    self.search_suggestions_list.addItem(item)

                

        except Exception as e:

            print(f"Error searching products: {e}")

    

    def _on_suggestion_selected(self, item):

        """Handle when user double-clicks a suggestion"""

        try:

            product_id = item.data(Qt.UserRole)

            if product_id:

                from pos_app.models.database import Product

                product = self.controller.session.query(Product).filter(Product.id == product_id).first()

                if product:

                    self.add_product_to_cart(product)

                    self.product_search.clear()

                    self.search_suggestions_list.clear()

                    # Set flag to prevent Enter from triggering sale immediately

                    self._product_added_from_search = True

                    # Reset flag after 1.5 seconds

                    QTimer.singleShot(1500, lambda: setattr(self, '_product_added_from_search', False))

                    # Fix 6: Keep focus on search field after adding product

                    QTimer.singleShot(50, lambda: self.product_search.setFocus())

        except Exception as e:

            print(f"Error selecting suggestion: {e}")



    def search_barcode_suggestions(self):

        """Show suggestions while typing in the barcode field (fallback when scanner not used)."""

        if not hasattr(self, 'barcode_input') or not hasattr(self, 'barcode_suggestions_list'):

            return

        text = (self.barcode_input.text() or '').strip()

        if len(text) < 1:

            self.barcode_suggestions_list.clear()

            return

        try:

            from pos_app.models.database import Product

            q = self.controller.session.query(Product)

            products = q.filter(

                (Product.barcode.ilike(f'%{text}%')) | (Product.sku.ilike(f'%{text}%'))

            ).limit(1000).all()

            self.barcode_suggestions_list.clear()

            for product in products:

                display_text = f"{product.name} (BAR: {product.barcode or '-'} | SKU: {product.sku or '-'}) - Rs {float(getattr(product,'retail_price',0)):,.2f}"

                item = QListWidgetItem(display_text)

                item.setData(Qt.UserRole, product.id)

                self.barcode_suggestions_list.addItem(item)

        except Exception as e:

            print(f"Error searching barcode: {e}")



    def show_product_selector(self):

        """Show a dialog to select products"""

        # Simple implementation - you can enhance this later

        try:

            from pos_app.models.database import Product

            products = self.controller.session.query(Product).all()

            

            if products:

                # Add first product for demonstration

                self.add_product_to_cart(products[0])

                msg = QMessageBox(self)

                msg.setIcon(QMessageBox.Information)

                msg.setWindowTitle("Product Added")

                msg.setText(f"Added {products[0].name} to cart!")

                msg.setStandardButtons(QMessageBox.Ok)

                msg.exec()

            else:

                msg = QMessageBox(self)

                msg.setIcon(QMessageBox.Warning)

                msg.setWindowTitle("No Products")

                msg.setText("No products found in database!")

                msg.setStandardButtons(QMessageBox.Ok)

                msg.exec()

                

        except Exception as e:

            msg = QMessageBox(self)

            msg.setIcon(QMessageBox.Critical)

            msg.setWindowTitle("Error")

            msg.setText(f"Failed to load products: {str(e)}")

            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec()



    def remove_cart_item(self, index):

        """Remove an item from the cart"""

        try:

            idx = int(index)

        except Exception:

            return

        if 0 <= idx < len(self.current_cart):

            print(f"[DEBUG] Removing cart item at index {idx}")

            del self.current_cart[idx]

            self.update_cart_table()

            self.update_totals()

            # Auto-exit refund mode if cart becomes empty

            if getattr(self, 'is_refund_mode', False) and len(self.current_cart) == 0:

                print("[DEBUG] Cart is now empty, auto-exiting refund mode")

                self.exit_refund_mode()



    def clear_cart(self):

        """Clear all items from the cart"""

        reply = QMessageBox.question(

            self, "Clear Cart",

            "Are you sure you want to clear all items from the cart?",

            QMessageBox.Yes | QMessageBox.No

        )

        if reply == QMessageBox.Yes:

            print("[DEBUG] Clearing all cart items")

            self.current_cart.clear()

            self.update_cart_table()

            self.update_totals()

            # Auto-exit refund mode if cart becomes empty

            if getattr(self, 'is_refund_mode', False) and len(self.current_cart) == 0:

                print("[DEBUG] Cart cleared, auto-exiting refund mode")

                self.exit_refund_mode()



    def refresh_data(self):

        """Refresh all data"""

        self.load_customers()

        self.update_totals()



    def show_keyboard_help(self):

        """Show keyboard shortcuts help"""

        shortcuts_text = """

        <h3>Keyboard Shortcuts</h3>

        <table>

        <tr><td><b>F1</b></td><td>Focus product search</td></tr>

        <tr><td><b>Enter</b></td><td>Add product to cart</td></tr>

        <tr><td><b>Delete</b></td><td>Remove selected cart item</td></tr>

        <tr><td><b>Ctrl+S</b></td><td>Complete sale</td></tr>

        </table>

        """

        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts_text)



    # Placeholder methods that need to be implemented

    def load_tax_rate(self):

        """Load tax rate from settings"""

        settings = QSettings("POSApp", "Settings")

        try:

            try:

                user_set = str(settings.value('tax_rate_user_set', 'false') or 'false').strip().lower() == 'true'

            except Exception:

                user_set = False



            if not user_set:

                self.tax_rate = 0.0

                try:

                    self.update_totals()

                except Exception:

                    pass

                return



            has_key = False

            try:

                has_key = bool(settings.contains('tax_rate'))

            except Exception:

                has_key = False



            v = settings.value('tax_rate', None)

            if v is None or str(v).strip() == "":

                v = None



            if v is None and not has_key:

                # Fresh/new PCs should default to 0% tax unless explicitly set in Settings.

                self.tax_rate = 0.0

            else:

                try:

                    self.tax_rate = float(v if v is not None else 0.0)

                except Exception:

                    self.tax_rate = 0.0

        except Exception:

            self.tax_rate = 0.0



        try:

            self.update_totals()

        except Exception:

            pass



            if hasattr(self, 'barcode_input'):

                self.barcode_input.setFocus()

                self.barcode_input.selectAll()

        except Exception:

            pass



    def _focus_suggestions(self):

        try:

            if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

                self.search_suggestions_list.setFocus()

                if self.search_suggestions_list.currentRow() < 0:

                    self.search_suggestions_list.setCurrentRow(0)

        except Exception:

            pass



    def _focus_cart(self):

        try:

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

        except Exception:

            pass



    def _focus_pay_method(self):

        try:

            if hasattr(self, 'pay_method_combo'):

                self.pay_method_combo.setFocus()

                # open popup for quick selection via arrows/enter

                try:

                    self.pay_method_combo.showPopup()

                except Exception:

                    pass

        except Exception:

            pass



    def _focus_amount_paid(self):

        try:

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setFocus()

                try:

                    self.amount_paid_input.selectAll()

                except Exception:

                    pass

        except Exception:

            pass



    def _focus_sale_type(self):

        try:

            if hasattr(self, 'sale_type_combo'):

                self.sale_type_combo.setFocus()

                try:

                    self.sale_type_combo.showPopup()

                except Exception:

                    pass

        except Exception:

            pass



    def _focus_customer(self):

        try:

            if hasattr(self, 'customer_combo'):

                self.customer_combo.setFocus()

                try:

                    self.customer_combo.showPopup()

                except Exception:

                    pass

        except Exception:

            pass



    def _focus_customer_select(self):

        try:

            if not hasattr(self, 'customer_combo'):

                return

            self.customer_combo.setFocus()

            try:

                le = self.customer_combo.lineEdit()

                if le is not None:

                    try:

                        le.setReadOnly(False)

                    except Exception:

                        pass

                    le.selectAll()

                    try:

                        le.setFocus()

                    except Exception:

                        pass

            except Exception:

                pass

            try:

                self.customer_combo.showPopup()

            except Exception:

                pass

        except Exception:

            pass



    def _edit_selected_price(self):

        try:

            if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

                row = self.cart_table.currentRow()

                if row >= 0:

                    self.edit_cart_item_price(row)

        except Exception:

            pass



    def on_settings_updated(self, settings):

        """Handle settings updates"""

        if 'tax_rate' in settings:

            self.tax_rate = float(settings.get('tax_rate', 8.0))

            self.update_totals()



    def load_customers(self):

        """Load customers into the combo box"""

        try:

            if hasattr(self, 'customer_combo'):

                # Store current selection to restore it after refresh

                current_customer_id = self.customer_combo.currentData()

                

                self.customer_combo.clear()

                self.customer_combo.addItem("Walk-in Customer", None)



                from pos_app.models.database import Customer

                try:

                    # Try to get customers from the controller's session

                    customers = self.controller.session.query(Customer).filter(

                        Customer.is_active == True

                    ).all()



                    if customers:

                        for customer in customers:

                            customer_name = getattr(customer, 'name', 'Unknown')

                            customer_id = getattr(customer, 'id', None)

                            self.customer_combo.addItem(customer_name, customer_id)

                        print(f"[SalesWidget] Loaded {len(customers)} customers")

                        

                        # Restore previous selection if it still exists

                        if current_customer_id:

                            for i in range(self.customer_combo.count()):

                                if self.customer_combo.itemData(i) == current_customer_id:

                                    self.customer_combo.setCurrentIndex(i)

                                    break

                    else:

                        # Try without the is_active filter

                        customers = self.controller.session.query(Customer).all()

                        if customers:

                            for customer in customers:

                                customer_name = getattr(customer, 'name', 'Unknown')

                                customer_id = getattr(customer, 'id', None)

                                self.customer_combo.addItem(customer_name, customer_id)

                            print(f"[SalesWidget] Loaded {len(customers)} customers (including inactive)")

                        else:

                            print("[SalesWidget] No customers found in database")

                except Exception as e:

                    print(f"[SalesWidget] Error querying customers: {e}")



                try:

                    self.customer_combo.setEditable(True)

                except Exception:

                    pass

                try:

                    le = self.customer_combo.lineEdit()

                    if le is not None:

                        le.setPlaceholderText("Type customer name...")

                        try:

                            le.setReadOnly(False)

                        except Exception:

                            pass

                except Exception:

                    pass

        except Exception as e:

            print(f"[SalesWidget] Error loading customers: {e}")

    

    def enter_refund_mode(self):

        """Enter refund mode"""

        try:

            self.is_refund_mode = True

            # Only clear marked items if this is a fresh entry (not after loading refund invoice)

            if not hasattr(self, '_refund_marked_items') or len(self._refund_marked_items) == 0:

                self._refund_marked_items = set()

                print("[DEBUG] Initialized empty marked items set")

            else:

                print(f"[DEBUG] Preserving existing marked items: {self._refund_marked_items}")

            self._refund_all_items = []

            # Show exit refund mode button

            if hasattr(self, 'exit_refund_btn'):

                self.exit_refund_btn.setVisible(True)

            print("[DEBUG] Entered refund mode")

        except Exception as e:

            print(f"[DEBUG] Error entering refund mode: {e}")

    

    def exit_refund_mode(self):

        """Exit refund mode and clear refund state"""

        try:

            print("[DEBUG] Exiting refund mode")

            self.is_refund_mode = False

            self.refund_of_sale_id = None

            self._refund_source_sale = None

            

            # Clear marked items for refund

            if hasattr(self, '_refund_marked_items'):

                self._refund_marked_items.clear()

            if hasattr(self, '_refund_all_items'):

                self._refund_all_items.clear()

            

            # Clear cart

            self.current_cart.clear()

            self.update_cart_table()

            self.update_totals()

            

            # Clear refund invoice input

            if hasattr(self, 'refund_invoice_input'):

                self.refund_invoice_input.clear()

            

            # Hide exit refund mode button

            if hasattr(self, 'exit_refund_btn'):

                self.exit_refund_btn.setVisible(False)

            

            # Reset discount

            if hasattr(self, 'discount_amount'):

                try:

                    self.discount_amount.setValue(0.0)

                except Exception:

                    pass

            

            # Reset amount paid

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setValue(0.0)

            

            print("[DEBUG] Exited refund mode successfully")

        except Exception as e:

            print(f"[DEBUG] Error exiting refund mode: {e}")

    

    def toggle_refund_mode(self):

        """Toggle refund mode on/off"""

        try:

            if getattr(self, 'is_refund_mode', False):

                self.exit_refund_mode()

            else:

                self.enter_refund_mode()

        except Exception as e:

            print(f"[DEBUG] Error toggling refund mode: {e}")

    

    def _delete_selected_cart_item(self):

        """Delete selected cart row via shortcut - WORKS GLOBALLY"""

        try:

            print("[DEBUG] Delete key pressed - attempting to remove cart item")

            # Always try to delete if cart has items, regardless of focus

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                # If cart has focus, delete selected row

                if self.cart_table.hasFocus():

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0:

                        print(f"[DEBUG] Deleting selected row {current_row}")

                        self.remove_cart_item(current_row)

                        # Check if cart is now empty and exit refund mode

                        if self.cart_table.rowCount() == 0 and getattr(self, 'is_refund_mode', False):

                            print("[DEBUG] Cart empty after delete, exiting refund mode")

                            self.exit_refund_mode()

                        return

                # Otherwise delete the last row (global delete)

                else:

                    last_row = self.cart_table.rowCount() - 1

                    if last_row >= 0:

                        print(f"[DEBUG] Deleting last row {last_row} (global delete)")

                        self.remove_cart_item(last_row)

                        # Check if cart is now empty and exit refund mode

                        if self.cart_table.rowCount() == 0 and getattr(self, 'is_refund_mode', False):

                            print("[DEBUG] Cart empty after delete, exiting refund mode")

                            self.exit_refund_mode()

                        return

            else:

                print("[DEBUG] Cart is empty, nothing to delete")

        except Exception as e:

            print(f"[DEBUG] Error deleting cart item via shortcut: {e}")



    def refresh_customers(self):

        """Refresh customer list to sync new customers without restart"""

        print("[SalesWidget] Refreshing customer list...")

        try:

            # rollback so we can see new committed customers from another session

            self.controller.session.rollback()

        except Exception:

            pass

        self.load_customers()

        print(f"[SalesWidget] Customer list refreshed. Total customers: {self.customer_combo.count() if hasattr(self, 'customer_combo') else 0}")

        

        # Auto-select "Walk-in Customer" as default

        try:

            if hasattr(self, 'customer_combo') and self.customer_combo:

                walk_in_index = self.customer_combo.findText("Walk-in Customer")

                if walk_in_index >= 0:

                    self.customer_combo.setCurrentIndex(walk_in_index)

        except Exception:

            pass



    def keyPressEvent(self, event):

        """Handle keyboard navigation and shortcuts"""

        try:

            from PySide6.QtCore import Qt

        except ImportError:

            from PyQt6.QtCore import Qt

        

        # Handle keyboard shortcuts here as well (in case eventFilter doesn't catch them)

        if not event.isAutoRepeat():

            key_text = event.text().lower()

            key = event.key()

            modifiers = event.modifiers()

            

            # Ctrl+R - Handle refund logic from any field

            if key == Qt.Key_R and (modifiers & Qt.ControlModifier):

                if modifiers & Qt.ShiftModifier:

                    print("[DEBUG] Ctrl+Shift+R key detected in keyPressEvent")

                    self._handle_ctrl_r(restore_all=True)

                else:

                    print("[DEBUG] Ctrl+R key detected in keyPressEvent")

                    self._handle_ctrl_r()

                return

            

            # Ctrl+Enter - Complete sale from anywhere

            if key in (Qt.Key_Return, Qt.Key_Enter) and (modifiers & Qt.ControlModifier):

                print("[DEBUG] Ctrl+Enter key detected in keyPressEvent")

                self._handle_ctrl_enter_complete_sale()

                return

            

            # Ctrl+E - Edit price of selected cart item - DISABLED

            # Use shortcut keys (Ctrl+Up/Down) instead of dialog

            if key == Qt.Key_E and (modifiers & Qt.ControlModifier):

                return

            

            # Ctrl+S - Focus on product search

            if key == Qt.Key_S and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'product_search'):

                    self.product_search.setFocus()

                    self.product_search.selectAll()

                    return

            

            # Ctrl+Up - Increase price of selected cart item

            if key == Qt.Key_Up and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        current_price = float(self.current_cart[current_row]['price'])

                        new_price = current_price + 10

                        self.current_cart[current_row]['price'] = new_price

                        self.update_cart_table()

                        self.update_totals()

                        return

            

            # Ctrl+Down - Decrease price of selected cart item

            if key == Qt.Key_Down and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        current_price = float(self.current_cart[current_row]['price'])

                        new_price = max(0, current_price - 10)

                        self.current_cart[current_row]['price'] = new_price

                        self.update_cart_table()

                        self.update_totals()

                        return

            

            # Ctrl+A - Increase quantity of selected cart item

            if key == Qt.Key_A and (modifiers & Qt.ControlModifier):

                if hasattr(self, 'cart_table') and len(self.current_cart) > 0:

                    current_row = self.cart_table.currentRow()

                    if current_row >= 0 and current_row < len(self.current_cart):

                        self.current_cart[current_row]['quantity'] = int(self.current_cart[current_row]['quantity']) + 1

                        self.update_cart_table()

                        self.update_totals()

                        return

            

            # Ctrl+C - Change payment method

            if key == Qt.Key_C and (modifiers & Qt.ControlModifier):

                # Don't change payment method if cart table is being edited

                if hasattr(self, 'cart_table') and self.cart_table.state() == QTableWidget.EditingState:

                    print("[DEBUG] Cart table is being edited, not changing payment method")

                    # Allow default copy behavior in the editor

                    event.ignore()

                    return

                    

                combo = getattr(self, 'pay_method_combo', None) or getattr(self, 'payment_method_combo', None)

                if combo and combo.count() > 0:

                    current_index = combo.currentIndex()

                    next_index = (current_index + 1) % combo.count()

                    combo.setCurrentIndex(next_index)

                    combo.setFocus()

                    return

            

            # Ctrl+T - Change sales type (cycle through Retail/Wholesale)

            if key == Qt.Key_T and (modifiers & Qt.ControlModifier):

                combo = getattr(self, 'sale_type_combo', None) or getattr(self, 'sales_type_combo', None)

                if combo and combo.count() > 0:

                    current_index = combo.currentIndex()

                    next_index = (current_index + 1) % combo.count()

                    combo.setCurrentIndex(next_index)

                    combo.setFocus()

                    return

            

            # Ctrl+Z - Focus customer (editable + suggestions)

            if key == Qt.Key_Z and (modifiers & Qt.ControlModifier):

                try:

                    self._focus_customer_select()

                except Exception:

                    try:

                        self._focus_customer()

                    except Exception:

                        pass

                return

        

        # Note: Keyboard shortcuts (Ctrl+A, Ctrl+C, Ctrl+S, Ctrl+T, Ctrl+Z, Ctrl+E, Ctrl+Up, Ctrl+Down)

        # are also handled in eventFilter() to ensure they work globally regardless of widget focus

        

        # No Delete key handling: Backspace is used for removals in keyboard-only mode

        

        # Products table interactions: Right/Left arrow to edit price, Up/Down to navigate rows

        if hasattr(self, 'products_table') and self.products_table.hasFocus():

            current_row = self.products_table.currentRow()

            if current_row >= 0:

                if event.key() == Qt.Key_Right:

                    # Edit retail price (column 3)

                    item = self.products_table.item(current_row, 3)

                    if item:

                        self._on_product_item_double_clicked(item)

                    return

                if event.key() == Qt.Key_Left:

                    # Edit wholesale price (column 4)

                    item = self.products_table.item(current_row, 4)

                    if item:

                        self._on_product_item_double_clicked(item)

                    return

                if event.key() == Qt.Key_Down:

                    # Move down in products table

                    if current_row < self.products_table.rowCount() - 1:

                        self.products_table.selectRow(current_row + 1)

                    return

                if event.key() == Qt.Key_Up:

                    # Move up in products table

                    if current_row > 0:

                        self.products_table.selectRow(current_row - 1)

                    return

        

        # Cart interactions: Right adjust quantity, Left edit price, Up/Down navigate, Backspace removes

        if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

            current_row = self.cart_table.currentRow()

            if current_row >= 0 and current_row < len(self.current_cart):

                if event.key() == Qt.Key_Right:

                    # Right arrow: increase quantity

                    self.current_cart[current_row]['quantity'] = int(self.current_cart[current_row]['quantity']) + 1

                    self.update_cart_table()

                    self.update_totals()

                    return

                if event.key() == Qt.Key_Left:

                    # Left arrow: DISABLED price editing - use shortcut keys instead

                    # Move to previous item or back to search

                    if current_row > 0:

                        self.cart_table.selectRow(current_row - 1)

                    else:

                        # From top cart row, move back to product search section

                        if hasattr(self, 'product_search'):

                            self.product_search.setFocus()

                    return

                if event.key() == Qt.Key_Down:

                    # Down arrow: move to next item in cart

                    if current_row < self.cart_table.rowCount() - 1:

                        self.cart_table.selectRow(current_row + 1)

                    return

                if event.key() == Qt.Key_Up:

                    # Up arrow: move to previous item in cart

                    if current_row > 0:

                        self.cart_table.selectRow(current_row - 1)

                    return

                if event.key() == Qt.Key_Backspace:

                    self.remove_cart_item(current_row)

                    return

                if event.key() in (Qt.Key_Return, Qt.Key_Enter):

                    # Suppress Enter immediately after barcode add to prevent unwanted actions

                    try:

                        if (time.monotonic() - getattr(self, '_last_barcode_add_ts', 0.0)) < 1.0:

                            print(f"[DEBUG] Suppressing Enter key after barcode scan")

                            event.ignore()

                            return

                    except Exception:

                        pass

                    # Move to payment widgets

                    self.navigate_right()

                    return

        

        # Enter key handling

        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:

            fw = self.focusWidget()

            if fw is getattr(self, 'refund_invoice_input', None):

                try:

                    self.load_refund_invoice()

                except Exception:

                    pass

                try:

                    event.accept()

                except Exception:

                    pass

                return

            if fw in (getattr(self, 'product_search', None), getattr(self, 'barcode_input', None)) or (hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.hasFocus()):

                # Let field-specific handlers run (add_first_search_result / add_product_by_barcode)

                event.ignore()

                return

            # On combos/spinboxes, treat Enter as confirm and move right

            try:

                from PySide6.QtWidgets import QComboBox as _QComboBox, QDoubleSpinBox as _QDoubleSpinBox

            except ImportError:

                from PyQt6.QtWidgets import QComboBox as _QComboBox, QDoubleSpinBox as _QDoubleSpinBox

            try:

                if isinstance(fw, (_QComboBox, _QDoubleSpinBox)):

                    self.navigate_right()

                    return

            except Exception:

                pass

            # If a QPushButton has focus, allow Enter to activate it (keyboard-only operation)

            try:

                from PySide6.QtWidgets import QPushButton as _QPushButton

            except ImportError:

                from PyQt6.QtWidgets import QPushButton as _QPushButton

            try:

                if isinstance(fw, _QPushButton) and fw.isEnabled() and fw.isVisible():

                    # Do not click buttons if cart is empty (prevents Empty Cart popup)

                    if not getattr(self, 'current_cart', []):

                        event.ignore()

                        return

                    # Suppress Enter immediately after a barcode add

                    try:

                        if (time.monotonic() - getattr(self, '_last_barcode_add_ts', 0.0)) < 0.5:

                            event.ignore()

                            return

                    except Exception:

                        pass

                    fw.click()

                    return

            except Exception:

                pass

            # Complete sale ONLY on Ctrl+Enter (global shortcut - works anywhere on sales page)

            if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ControlModifier):

                print("[DEBUG] Ctrl+Enter detected globally - clicking complete sale button")

                try:

                    if (time.monotonic() - getattr(self, '_last_barcode_add_ts', 0.0)) < 0.5:

                        print("[DEBUG] Suppressing Ctrl+Enter after barcode scan")

                        event.ignore()

                        return

                except Exception:

                    pass

                

                # Directly call process_sale instead of clicking button to avoid UI issues

                if getattr(self, 'current_cart', []) and len(self.current_cart) > 0:

                    print("[DEBUG] Calling process_sale directly")

                    try:

                        self.process_sale()

                        event.accept()

                        return

                    except Exception as e:

                        print(f"[DEBUG] Error in process_sale: {e}")

                        event.accept()

                        return

                else:

                    print("[DEBUG] Cart is empty - cannot process sale")

                    event.accept()

                    return



            event.ignore()

            return

        

        # Arrow keys for navigation

        if event.key() == Qt.Key_Right:

            self.navigate_right()

            return

        elif event.key() == Qt.Key_Left:

            self.navigate_left()

            return

        elif event.key() == Qt.Key_Down:

            self.navigate_down()

            return

        elif event.key() == Qt.Key_Up:

            self.navigate_up()

            return

        

        # Tab key: move to next field

        if event.key() == Qt.Key_Tab:

            self.navigate_right()

            return

        

        # Shift+Tab: move to previous field

        if event.key() == Qt.Key_Backtab:

            self.navigate_left()

            return

        

        super().keyPressEvent(event)



    def navigate_right(self):

        """Navigate to the right (search -> cart if items exist, else suggestions)"""

        focused_widget = self.focusWidget()

        

        # PRIORITY: If cart has items and we're in search/barcode, go directly to cart

        if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

            if focused_widget in (getattr(self, 'product_search', None), getattr(self, 'barcode_input', None)):

                self.cart_table.setFocus()

                self.cart_table.selectRow(0)

                print("[DEBUG] Navigate: Search/Barcode -> Cart (has items)")

                return

        

        # From product search field (only if cart is empty)

        if focused_widget == getattr(self, 'product_search', None):

            # Try suggestions if they have items

            if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

                self.search_suggestions_list.setFocus()

                self.search_suggestions_list.setCurrentRow(0)

                print("[DEBUG] Navigate: Search -> Suggestions")

                return

            # If no suggestions, go to barcode input

            if hasattr(self, 'barcode_input'):

                self.barcode_input.setFocus()

                print("[DEBUG] Navigate: Search -> Barcode")

                return

                

        # From barcode input (only if cart is empty)

        if focused_widget == getattr(self, 'barcode_input', None):

            # Try barcode suggestions if available

            if hasattr(self, 'barcode_suggestions_list') and self.barcode_suggestions_list.count() > 0:

                self.barcode_suggestions_list.setFocus()

                self.barcode_suggestions_list.setCurrentRow(0)

                print("[DEBUG] Navigate: Barcode -> Suggestions")

                return

                

        # From suggestions lists

        if focused_widget in (getattr(self, 'search_suggestions_list', None), getattr(self, 'barcode_suggestions_list', None)):

            # Move to cart if it has items

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                self.cart_table.selectRow(0)

                print("[DEBUG] Navigate: Suggestions -> Cart")

                return

            # Otherwise cycle back to search

            if hasattr(self, 'product_search'):

                self.product_search.setFocus()

                print("[DEBUG] Navigate: Suggestions -> Search (cycle)")

                return

        

        # From cart -> checkout section (pay method -> amount -> sale type -> customer -> complete -> clear)

        if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

            if hasattr(self, 'pay_method_combo'):

                self.pay_method_combo.setFocus()

            return



        # Checkout section sequential navigation

        if hasattr(self, 'pay_method_combo') and self.pay_method_combo.hasFocus():

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setFocus()

                try:

                    self.amount_paid_input.selectAll()

                except Exception:

                    pass

            return



        if hasattr(self, 'amount_paid_input') and self.amount_paid_input.hasFocus():

            if hasattr(self, 'sale_type_combo'):

                self.sale_type_combo.setFocus()

            return



        if hasattr(self, 'sale_type_combo') and self.sale_type_combo.hasFocus():

            if hasattr(self, 'customer_combo'):

                self.customer_combo.setFocus()

            return



        if hasattr(self, 'customer_combo') and self.customer_combo.hasFocus():

            if hasattr(self, 'complete_sale_btn'):

                self.complete_sale_btn.setFocus()

            return

        

        if hasattr(self, 'complete_sale_btn') and self.complete_sale_btn.hasFocus():

            if hasattr(self, 'clear_cart_btn'):

                self.clear_cart_btn.setFocus()

            return

        

        if hasattr(self, 'clear_cart_btn') and self.clear_cart_btn.hasFocus():

            if hasattr(self, 'product_search'):

                self.product_search.setFocus()

            return



    def navigate_left(self):

        """Navigate to the left - from checkout back to cart, from cart to search"""

        # From checkout section back to cart (stay in cart until sale is complete)

        if hasattr(self, 'pay_method_combo') and self.pay_method_combo.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        if hasattr(self, 'amount_paid_input') and self.amount_paid_input.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        if hasattr(self, 'sale_type_combo') and self.sale_type_combo.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        if hasattr(self, 'customer_combo') and self.customer_combo.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        if hasattr(self, 'complete_sale_btn') and self.complete_sale_btn.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        if hasattr(self, 'clear_cart_btn') and self.clear_cart_btn.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return

        

        # From cart to search/barcode

        if hasattr(self, 'cart_table') and self.cart_table.hasFocus():

            # Move from cart to suggestions if available

            if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

                self.search_suggestions_list.setFocus()

                self.search_suggestions_list.setCurrentRow(0)

                return

            # If no suggestions, move to search

            elif hasattr(self, 'product_search'):

                self.product_search.setFocus()

                return

        

        # From suggestions back to search/barcode

        if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.hasFocus():

            if hasattr(self, 'product_search'):

                self.product_search.setFocus()

            return

        

        if hasattr(self, 'barcode_suggestions_list') and self.barcode_suggestions_list.hasFocus():

            if hasattr(self, 'barcode_input'):

                self.barcode_input.setFocus()

            return

        

        # From product search wrap to clear button

        if hasattr(self, 'product_search') and self.product_search.hasFocus():

            if hasattr(self, 'clear_cart_btn'):

                self.clear_cart_btn.setFocus()

            return

        

        # From barcode input, move to cart if items exist, otherwise stay

        if hasattr(self, 'barcode_input') and self.barcode_input.hasFocus():

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = 0

                self.cart_table.selectRow(row)

            return



    def navigate_down(self):

        """Navigate down in current table/list"""

        # From product/barcode edit into their suggestion lists

        if hasattr(self, 'product_search') and self.product_search.hasFocus():

            if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

                self.search_suggestions_list.setFocus()

                self.search_suggestions_list.setCurrentRow(0)

                return

        if hasattr(self, 'barcode_input') and self.barcode_input.hasFocus():

            if hasattr(self, 'barcode_suggestions_list') and self.barcode_suggestions_list.count() > 0:

                self.barcode_suggestions_list.setFocus()

                self.barcode_suggestions_list.setCurrentRow(0)

                return

        # In checkout section, move down through fields

        if hasattr(self, 'pay_method_combo') and self.pay_method_combo.hasFocus():

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setFocus()

            return

        if hasattr(self, 'amount_paid_input') and self.amount_paid_input.hasFocus():

            if hasattr(self, 'sale_type_combo'):

                self.sale_type_combo.setFocus()

            return

        if hasattr(self, 'sale_type_combo') and self.sale_type_combo.hasFocus():

            if hasattr(self, 'customer_combo'):

                self.customer_combo.setFocus()

            return

        if hasattr(self, 'customer_combo') and self.customer_combo.hasFocus():

            # Stay at bottom of checkout section on further Down

            return

        if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.hasFocus():

            current_row = self.search_suggestions_list.currentRow()

            if current_row < self.search_suggestions_list.count() - 1:

                self.search_suggestions_list.setCurrentRow(current_row + 1)

        elif hasattr(self, 'barcode_suggestions_list') and self.barcode_suggestions_list.hasFocus():

            current_row = self.barcode_suggestions_list.currentRow()

            if current_row < self.barcode_suggestions_list.count() - 1:

                self.barcode_suggestions_list.setCurrentRow(current_row + 1)

        elif hasattr(self, 'cart_table') and self.cart_table.hasFocus():

            current_row = self.cart_table.currentRow()

            row_count = self.cart_table.rowCount()

            if current_row < row_count - 1:

                # Move down within cart items

                self.cart_table.selectRow(current_row + 1)

            elif row_count > 0:

                # From last cart row, move into checkout (pay method)

                if hasattr(self, 'pay_method_combo'):

                    self.pay_method_combo.setFocus()





    def navigate_up(self):

        """Navigate up in current table/list"""

        # In checkout section, move up through fields

        if hasattr(self, 'customer_combo') and self.customer_combo.hasFocus():

            if hasattr(self, 'sale_type_combo'):

                self.sale_type_combo.setFocus()

            return

        if hasattr(self, 'sale_type_combo') and self.sale_type_combo.hasFocus():

            if hasattr(self, 'amount_paid_input'):

                self.amount_paid_input.setFocus()

            return

        if hasattr(self, 'amount_paid_input') and self.amount_paid_input.hasFocus():

            if hasattr(self, 'pay_method_combo'):

                self.pay_method_combo.setFocus()

            return

        if hasattr(self, 'pay_method_combo') and self.pay_method_combo.hasFocus():

            # From checkout back to cart (keep current or last row)

            if hasattr(self, 'cart_table') and self.cart_table.rowCount() > 0:

                self.cart_table.setFocus()

                row = self.cart_table.currentRow()

                if row < 0:

                    row = self.cart_table.rowCount() - 1

                self.cart_table.selectRow(row)

            return



        if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.hasFocus():

            current_row = self.search_suggestions_list.currentRow()

            if current_row > 0:

                self.search_suggestions_list.setCurrentRow(current_row - 1)

        elif hasattr(self, 'barcode_suggestions_list') and self.barcode_suggestions_list.hasFocus():

            current_row = self.barcode_suggestions_list.currentRow()

            if current_row > 0:

                self.barcode_suggestions_list.setCurrentRow(current_row - 1)

        elif hasattr(self, 'cart_table') and self.cart_table.hasFocus():

            current_row = self.cart_table.currentRow()

            if current_row > 0:

                # Move up within cart items

                self.cart_table.selectRow(current_row - 1)

            else:

                # From top cart row, move back to product search section

                if hasattr(self, 'product_search'):

                    self.product_search.setFocus()



    def _on_cart_item_double_clicked(self, index):

        """Handle double-click on cart item to edit quantity or price"""

        try:

            row = index.row()

            col = index.column()

            

            # Only allow editing quantity (col 1) or price (col 3)

            if col not in (1, 3):  # Quantity column is 1, Price column is 3

                return

            

            # Get current item

            item = self.cart_table.item(row, col)

            if not item:

                return

            

            current_value = item.text()

            

            # Create input dialog

            try:

                from PySide6.QtWidgets import QInputDialog

            except ImportError:

                from PyQt6.QtWidgets import QInputDialog

            

            if col == 1:  # Quantity column

                title = "Edit Quantity"

                label = "Enter new quantity:"

                try:

                    current_qty = float(current_value)

                except ValueError:

                    current_qty = 1.0

                

                # Allow decimal quantities for weighted items

                new_value, ok = QInputDialog.getDouble(

                    self, title, label, current_qty, 0.01, 999999.99, 2

                )

                

                if ok:

                    # Update the quantity in cart

                    self._update_cart_item_quantity(row, new_value)

                    

            elif col == 3:  # Price column

                title = "Edit Price"

                label = "Enter new price:"

                try:

                    current_price = float(current_value.replace('Rs ', '').replace(',', ''))

                except ValueError:

                    current_price = 0.0

                

                new_value, ok = QInputDialog.getDouble(

                    self, title, label, current_price, 0.01, 999999.99, 2

                )

                

                if ok:

                    # Update the price in cart

                    self._update_cart_item_price(row, new_value)

                    

        except Exception as e:

            print(f"Error in _on_cart_item_double_clicked: {e}")

    

    def _update_cart_item_quantity(self, row, new_quantity):

        """Update quantity of a cart item"""

        try:

            if row < 0 or row >= len(self.current_cart):

                return

            

            # Get the cart item

            cart_item = self.current_cart[row]

            old_quantity = cart_item.get('quantity', 1)

            

            # Update quantity

            cart_item['quantity'] = new_quantity

            

            # Recalculate total

            unit_price = cart_item.get('unit_price', 0)

            cart_item['total'] = unit_price * new_quantity

            

            # Update the table

            self.update_cart_table()

            

            # Update totals

            self.update_totals()

            

        except Exception as e:

            print(f"Error updating cart item quantity: {e}")

    

    def _update_cart_item_price(self, row, new_price):

        """Update price of a cart item"""

        try:

            if row < 0 or row >= len(self.current_cart):

                return

            

            # Get the cart item

            cart_item = self.current_cart[row]

            

            # Update price

            cart_item['unit_price'] = new_price

            

            # Recalculate total

            quantity = cart_item.get('quantity', 1)

            cart_item['total'] = quantity * new_price

            

            # Update the table

            self.update_cart_table()

            

            # Update totals

            self.update_totals()

            

        except Exception as e:

            print(f"Error updating cart item price: {e}")



    def edit_cart_item_price(self, row):

        """Allow editing price of a cart item (sale-specific only) - DISABLED"""

        # Price editing dialog disabled - use shortcut keys instead

        return



    def process_sale(self, print_receipt=False):

        """Simplified sale processing - ignores validation and just creates sale

        

        Args:

            print_receipt: If True, print receipt after sale. For refunds, only print if True.

        """

        print("[DEBUG] Starting simplified process_sale")

        try:

            print(f"[DEBUG] Current cart has {len(self.current_cart)} items")

            # Reset wholesale balance capture (populated for wholesale sales only)

            self._receipt_prev_balance = None

            self._receipt_new_balance = None

            self._receipt_customer_obj = None

            if not self.current_cart:

                print("[DEBUG] Cart is empty, returning")

                return



            # Skip all validation - just create sale

            customer_id = self.customer_combo.currentData() if hasattr(self, 'customer_combo') else None

            pay_method = self.pay_method_combo.currentText() if hasattr(self, 'pay_method_combo') else 'Cash'

            amount_paid = float(self.amount_paid_input.value()) if hasattr(self, 'amount_paid_input') else 0.0

            

            # Calculate totals

            _items_count, subtotal, _total_cost, _profit, discount, tax_amount, final_total = self._calculate_totals()



            # Validate totals don't exceed database limit (precision 12, scale 2 = max 10^10 = 10,000,000,000)

            MAX_DB_VALUE = 10_000_000_000.0  # 10 billion

            if subtotal > MAX_DB_VALUE or final_total > MAX_DB_VALUE:

                msg = QMessageBox(self)

                msg.setIcon(QMessageBox.Critical)

                msg.setWindowTitle("Error")

                msg.setText(f"Total amount exceeds maximum allowed value (10 billion). Subtotal: {subtotal:,.2f}, Total: {final_total:,.2f}")

                msg.setStandardButtons(QMessageBox.Ok)

                msg.exec()

                print(f"[ERROR] Total exceeds database limit: subtotal={subtotal}, final_total={final_total}")

                return



            # Create sale items

            items = []

            # In refund mode, separate returned items from new sale items

            marked_items = getattr(self, '_refund_marked_items', set())

            if getattr(self, 'is_refund_mode', False):

                print(f"[DEBUG] Refund mode: Processing mixed return/sale transaction")

                print(f"[DEBUG] Marked items (returns): {marked_items}")

                

                # Process marked items as returns

                return_items = []

                for cart_item in self.current_cart:

                    if cart_item.get('id') in marked_items:

                        return_items.append({

                            'product_id': cart_item.get('id'),

                            'quantity': cart_item.get('quantity', 0),

                            'unit_price': cart_item.get('refund_unit_subtotal', cart_item.get('price', 0.0)),

                        })

                        print(f"[DEBUG] Return item: {cart_item.get('name')} (id={cart_item.get('id')}) @ {cart_item.get('refund_unit_subtotal')}")

                

                # Process unmarked items as new sales

                sale_items = []

                for cart_item in self.current_cart:

                    if cart_item.get('id') not in marked_items:

                        sale_items.append({

                            'product_id': cart_item.get('id'),

                            'quantity': cart_item.get('quantity', 0),

                            'unit_price': cart_item.get('price', 0.0),

                        })

                        print(f"[DEBUG] Sale item: {cart_item.get('name')} (id={cart_item.get('id')})")

                

                # If we have both returns and sales, create two separate transactions

                if return_items and sale_items:

                    print(f"[DEBUG] Creating mixed transaction: {len(return_items)} returns + {len(sale_items)} sales")

                    

                    # First, create the refund transaction

                    if return_items:

                        refund_sale = self.controller.create_sale(

                            customer_id,

                            return_items,

                            self.is_wholesale_selected(),  # is_wholesale - use actual selection

                            pay_method,

                            0.0,  # amount_paid = 0 for refund

                            is_refund=True,

                            refund_of_sale_id=getattr(self, 'refund_of_sale_id', None),

                            discount_amount=0.0  # No discount on refunds

                        )

                        print(f"[DEBUG] Refund sale created: {getattr(refund_sale, 'id', 'N/A')}")

                    

                    # Then, create the sale transaction

                    sale = self.controller.create_sale(

                        customer_id,

                        sale_items,

                        self.is_wholesale_selected(),  # is_wholesale - use actual selection

                        pay_method,

                        amount_paid,

                        is_refund=False,

                        refund_of_sale_id=None,

                        discount_amount=discount

                    )

                    print(f"[DEBUG] Sale created: {getattr(sale, 'id', 'N/A')}")

                    

                    # For receipt, combine both transactions

                    items = return_items + sale_items

                elif return_items:

                    # Only returns

                    items = return_items

                    sale = self.controller.create_sale(

                        customer_id,

                        items,

                        self.is_wholesale_selected(),  # is_wholesale - use actual selection

                        pay_method,

                        0.0,  # amount_paid = 0 for refund

                        is_refund=True,

                        refund_of_sale_id=getattr(self, 'refund_of_sale_id', None),

                        discount_amount=0.0  # Discount is already baked into refund_unit_subtotal

                    )

                    print(f"[DEBUG] Refund-only sale created: {getattr(sale, 'id', 'N/A')}")

                elif sale_items:

                    # Only sales (shouldn't happen in refund mode, but handle it)

                    items = sale_items

                    sale = self.controller.create_sale(

                        customer_id,

                        items,

                        self.is_wholesale_selected(),  # is_wholesale - use actual selection

                        pay_method,

                        amount_paid,

                        is_refund=False,

                        refund_of_sale_id=None,

                        discount_amount=discount

                    )

                    print(f"[DEBUG] Sale-only created: {getattr(sale, 'id', 'N/A')}")

                else:

                    print("[DEBUG] No items to process")

                    return

            else:

                # Normal sale - include all items

                for cart_item in self.current_cart:

                    items.append({

                        'product_id': cart_item.get('id'),

                        'quantity': cart_item.get('quantity', 0),

                        'unit_price': cart_item.get('price', 0.0),

                    })

                

                print(f"[DEBUG] Creating sale with {len(items)} items")

                # Capture previous balance (before sale) for wholesale customer receipt

                try:

                    if customer_id:

                        from pos_app.models.database import Customer

                        cust_obj = self.controller.session.query(Customer).get(customer_id)

                        if cust_obj and (
                            str(getattr(cust_obj, 'type', '') or '').upper() == 'WHOLESALE'
                            or self.is_wholesale_selected()
                        ):

                            self._receipt_prev_balance = float(getattr(cust_obj, 'current_credit', 0) or 0)

                            self._receipt_customer_obj = cust_obj

                            print(f"[DEBUG] Wholesale prev balance captured: Rs {self._receipt_prev_balance:.2f}")

                except Exception as e:

                    print(f"[DEBUG] Error capturing previous balance: {e}")

                # Create the sale

                sale = self.controller.create_sale(

                    customer_id,

                    items,

                    self.is_wholesale_selected(),  # is_wholesale - use actual selection

                    pay_method,

                    amount_paid,

                    is_refund=False,

                    refund_of_sale_id=None,

                    discount_amount=discount

                )

                print(f"[DEBUG] Sale created successfully: {getattr(sale, 'id', 'N/A')}")

                # Capture new balance (after sale) for wholesale customer receipt

                try:

                    if self._receipt_customer_obj is not None:

                        try:

                            self.controller.session.refresh(self._receipt_customer_obj)

                        except Exception:

                            pass

                        self._receipt_new_balance = float(getattr(self._receipt_customer_obj, 'current_credit', 0) or 0)

                        print(f"[DEBUG] Wholesale new balance captured: Rs {self._receipt_new_balance:.2f}")

                except Exception as e:

                    print(f"[DEBUG] Error capturing new balance: {e}")



            # Generate and print receipt

            try:

                is_refund_mode = getattr(self, 'is_refund_mode', False)

                print(f"[DEBUG] Receipt generation - is_refund_mode: {is_refund_mode}")

                print(f"[DEBUG] print_receipt parameter: {print_receipt}")



                # Only print receipt if:

                # 1. print_receipt=True (explicit request via Ctrl+Shift+Enter)

                # 2. It's not a refund mode (normal sales always print)

                should_print = print_receipt or not is_refund_mode

                print(f"[DEBUG] Should print receipt: {should_print}")



                if should_print:

                    # For receipt, include all items (both returns and sales) with proper marking

                    receipt_items = []

                    if is_refund_mode:

                        marked_items = getattr(self, '_refund_marked_items', set())

                        print(f"[DEBUG] Refund mode - marked_items: {marked_items}")

                        print(f"[DEBUG] Refund mode - current_cart size: {len(self.current_cart)}")

                        

                        # Include both marked (returns) and unmarked (sales) items

                        for cart_item in self.current_cart:

                            item_id = cart_item.get('id')

                            # Mark returned items with "R" suffix

                            if item_id in marked_items:

                                # Create a copy with return marker

                                receipt_item = cart_item.copy()

                                receipt_item['is_return'] = True

                                receipt_items.append(receipt_item)

                                print(f"[DEBUG] Receipt: Added return item: {cart_item.get('name')}")

                            else:

                                # Regular sale item

                                receipt_item = cart_item.copy()

                                receipt_item['is_return'] = False

                                receipt_items.append(receipt_item)

                                print(f"[DEBUG] Receipt: Added sale item: {cart_item.get('name')}")

                    else:

                        receipt_items = self.current_cart

                        print(f"[DEBUG] Normal sale - using all {len(receipt_items)} cart items")



                    # Calculate totals separately for returns and sales

                    receipt_subtotal = 0.0

                    receipt_discount = discount  # Use the global discount amount

                    receipt_tax = 0.0

                    return_total = 0.0

                    sale_total = 0.0



                    print(f"[DEBUG] Receipt items to process: {len(receipt_items)}")

                    print(f"[DEBUG] Initial discount value: {receipt_discount}")

                    for idx, item in enumerate(receipt_items):

                        print(f"[DEBUG] Item {idx}: {item}")

                        qty = item.get('quantity', 0) or 0

                        price = item.get('price', 0.0) or 0.0

                        item_total = qty * price

                        receipt_subtotal += item_total

                        

                        # Track returns and sales separately

                        if item.get('is_return', False):

                            return_total += item_total

                        else:

                            sale_total += item_total



                    print(f"[DEBUG] Subtotal: {receipt_subtotal}, Sale Total: {sale_total}, Return Total: {return_total}, Discount: {receipt_discount}")



                    # Apply discount only to sales (not returns)

                    # For refunds, calculate discount proportionally based on refunded items

                    discounted_sale_total = 0.0  # Initialize for refund mode

                    net_total = 0.0  # Initialize for refund mode

                    

                    if is_refund_mode:

                        # For refunds, discount should be prorated based on what portion is being refunded

                        # If refunding all items, discount should match original discount

                        if receipt_subtotal > 0:

                            # Prorate discount based on refunded portion

                            refund_portion = return_total / receipt_subtotal

                            receipt_discount = discount * refund_portion

                        else:

                            receipt_discount = 0.0

                        receipt_final = return_total - receipt_discount

                        receipt_tax = 0.0  # No tax on refunds

                    else:

                        discounted_sale_total = sale_total - receipt_discount

                        net_total = discounted_sale_total - return_total  # Sales - Returns

                        

                        # Apply tax on net total

                        receipt_tax = net_total * (self.tax_rate / 100.0)

                        receipt_final = net_total + receipt_tax



                    # Get payment method from UI

                    pay_method = self.pay_method_combo.currentText() if hasattr(self, 'pay_method_combo') else 'Cash'

                    customer_name = self.customer_combo.currentText() if hasattr(self, 'customer_combo') else "Walk-in Customer"

                    

                    # Create receipt data

                    receipt_data = {

                        'customer_name': customer_name,

                        'sale_type': 'Refund' if is_refund_mode else 'Sale',

                        'invoice_number': getattr(sale, 'invoice_number', f"INV-{getattr(sale, 'id', 'N/A')}") if 'sale' in locals() else f"INV-{getattr(refund_sale, 'id', 'N/A')}" if 'refund_sale' in locals() else "N/A",

                        'subtotal': receipt_subtotal,

                        'discount_amount': receipt_discount,

                        'tax_amount': receipt_tax,

                        'final_total': receipt_final,

                        'amount_paid': amount_paid,

                        'change_amount': max(0.0, amount_paid - receipt_final),

                        'items': receipt_items,

                        'is_refund': is_refund_mode,

                        'payment_method': pay_method  # Add payment method to receipt data

                    }

                    # Attach wholesale customer balance info for receipt (prev/new balance lines)

                    if customer_id and getattr(self, '_receipt_prev_balance', None) is not None:

                        receipt_data['customer'] = {

                            'name': customer_name,

                            'balance': float(getattr(self, '_receipt_new_balance', 0) or 0),

                            'prev_balance': getattr(self, '_receipt_prev_balance', None),

                            'new_balance': getattr(self, '_receipt_new_balance', None),

                        }

                        print(f"[DEBUG] Receipt data wholesale customer balance attached: prev={receipt_data['customer']['prev_balance']} new={receipt_data['customer']['new_balance']}")

                    print(f"[DEBUG] Receipt data payment_method: {receipt_data['payment_method']}")

                    print("[DEBUG] Printing receipt")

                    receipt_dialog = ReceiptPreviewDialog(receipt_data, self)

                    receipt_dialog.print_receipt()  # Print directly without dialog

                else:

                    print("[DEBUG] Skipping receipt printing (refund mode without explicit print request)")

            except Exception as e:

                print(f"[DEBUG] Error printing receipt: {e}")



            # Clear cart and reset

            try:

                self.current_cart.clear()

                self.update_cart_table()

                self.update_totals()

                

                # Reset amount paid to 0

                if hasattr(self, 'amount_paid_input'):

                    self.amount_paid_input.setValue(0.00)

                

                # Reset customer to Walk-in Customer

                if hasattr(self, 'customer_combo'):

                    try:

                        walk_in_index = self.customer_combo.findText("Walk-in Customer")

                        if walk_in_index >= 0:

                            self.customer_combo.setCurrentIndex(walk_in_index)

                            print("[DEBUG] Reset customer to Walk-in Customer")

                    except Exception as e:

                        print(f"[DEBUG] Error resetting customer: {e}")

                

                # Reset discount to 0

                if hasattr(self, 'discount_amount'):

                    try:

                        self.discount_amount.setValue(0.00)

                        print("[DEBUG] Reset discount to 0")

                    except Exception as e:

                        print(f"[DEBUG] Error resetting discount: {e}")

                elif hasattr(self, 'discount_amount_input'):

                    try:

                        self.discount_amount_input.setText("0")

                        print("[DEBUG] Reset discount_amount_input to 0")

                    except Exception as e:

                        print(f"[DEBUG] Error resetting discount_amount_input: {e}")

                

                # Reset payment method to Cash

                if hasattr(self, 'pay_method_combo'):

                    try:

                        cash_index = self.pay_method_combo.findText("Cash")

                        if cash_index >= 0:

                            self.pay_method_combo.setCurrentIndex(cash_index)

                            print("[DEBUG] Reset payment method to Cash")

                    except Exception as e:

                        print(f"[DEBUG] Error resetting payment method: {e}")

                

                # Reset sales type to Walk-in / Retail

                if hasattr(self, 'sale_type_combo'):

                    try:

                        retail_index = self.sale_type_combo.findText("Walk-in / Retail")

                        if retail_index >= 0:

                            self.sale_type_combo.setCurrentIndex(retail_index)

                            print("[DEBUG] Reset sales type to Walk-in / Retail")

                    except Exception as e:

                        print(f"[DEBUG] Error resetting sales type: {e}")

                

                print("[DEBUG] Cart cleared and reset")

                

                # Refresh customer list to update balance display

                try:

                    self.refresh_customers()

                    print("[DEBUG] Customer list refreshed after sale")

                except Exception as e:

                    print(f"[DEBUG] Error refreshing customers after sale: {e}")

                

                # Auto-focus search bar after sale completion

                try:

                    if hasattr(self, 'product_search') and self.product_search:

                        self.product_search.clear()

                        self.product_search.setFocus()

                        print("[DEBUG] Auto-focused product search after sale")

                    elif hasattr(self, 'barcode_input') and self.barcode_input:

                        self.barcode_input.clear()

                        self.barcode_input.setFocus()

                        print("[DEBUG] Auto-focused barcode input after sale")

                except Exception as e:

                    print(f"[DEBUG] Error auto-focusing after sale: {e}")

                    

            except Exception as e:

                print(f"[DEBUG] Error in cleanup: {e}")



            print("[DEBUG] Sale completed successfully")



        except Exception as e:

            print(f"[DEBUG] Error in process_sale: {e}")

            import traceback

            traceback.print_exc()



            # Show user-friendly error message

            error_msg = str(e)

            try:

                from PySide6.QtWidgets import QMessageBox

            except ImportError:

                from PyQt6.QtWidgets import QMessageBox



            msg = QMessageBox(self)

            msg.setIcon(QMessageBox.Warning)



            # Provide clear, actionable error messages

            if "no refundable quantity remaining" in error_msg.lower():

                msg.setWindowTitle("Refund Not Possible")

                msg.setText("This product has already been fully refunded.")

                msg.setInformativeText("Please select a different invoice that hasn't been refunded yet, or create a new sale to refund.")

            elif "stock validation failed" in error_msg.lower():

                msg.setWindowTitle("Stock Error")

                msg.setText("Not enough stock available.")

                msg.setInformativeText("Please check inventory levels before completing this sale.")

            elif "refund must reference an original sale" in error_msg.lower():

                msg.setWindowTitle("Refund Error")

                msg.setText("Invalid refund operation.")

                msg.setInformativeText("Please load a valid invoice number before processing a refund.")

            else:

                msg.setWindowTitle("Error")

                msg.setText("Failed to process sale.")

                msg.setInformativeText(error_msg)



            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec()



    def add_first_search_result(self):

        """Add the first product from search results when Enter is pressed"""

        search_text = self.product_search.text().strip()

        if not search_text:

            return



        # If we're in refund mode, do not allow adding arbitrary products.

        # Refunds must only contain items from the loaded invoice.

        if getattr(self, 'is_refund_mode', False):

            try:

                QMessageBox.warning(self, "Refund", "You are in refund mode. You can only refund items from the loaded invoice.")

            except Exception:

                pass

            return



        # REMOVED: Do not auto-load refund invoice from search box

        # This was causing confusion when searching for products

        # Users should use the dedicated refund invoice field instead

        

        # Set flag to prevent Enter from completing sale after adding product

        self._product_added_from_search = True

        

        # First, try to use the first item from the suggestions list if it exists

        if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

            first_item = self.search_suggestions_list.item(0)

            if first_item:

                self._on_suggestion_selected(first_item)

                # Keep focus on search field after adding

                self._refocus_search()

                return

        

        # If no suggestions yet, wait a bit for the search to complete

        # by forcing the search to run immediately

        if hasattr(self, '_search_timer'):

            self._search_timer.stop()  # Stop the debounce timer

        

        # Run search immediately

        self.search_products()

        

        # Now try again with the updated suggestions

        if hasattr(self, 'search_suggestions_list') and self.search_suggestions_list.count() > 0:

            first_item = self.search_suggestions_list.item(0)

            if first_item:

                self._on_suggestion_selected(first_item)

                # Keep focus on search field after adding

                self._refocus_search()

                return

        

        # If still no results, try barcode search as fallback

        try:

            from pos_app.models.database import Product

            from pos_app.utils.barcode_validator import validate_barcode_input

            

            validation = validate_barcode_input(search_text)

            cleaned = validation.get('cleaned_barcode', search_text)

            

            # Search by name, SKU, or barcode

            product = self.controller.session.query(Product).filter(

                (Product.name.ilike(f"%{search_text}%")) |

                (Product.sku.ilike(f"%{search_text}%")) |

                (Product.barcode == cleaned) |

                (Product.sku == cleaned)

            ).first()

            

            if product:

                self.add_product_to_cart(product)

                self.product_search.clear()

            # Silently ignore if not found (barcode scanner behavior)

                

        except Exception as e:

            # Silently ignore errors for barcode scanner compatibility

            pass



            # Keep focus on search field

            try:

                self.product_search.setFocus()

                self.product_search.selectAll()

            except:

                pass



    def add_product_by_barcode(self, barcode: str | None = None):

        """Add product to cart by barcode when Enter is pressed or scanner input arrives.



        If `barcode` is None, uses the text from the barcode input field. This keeps

        existing UI behavior while also allowing the global barcode buffer to call

        this method directly.

        """

        # Block adding new products while refunding; refund mode must only use invoice items.

        if getattr(self, 'is_refund_mode', False):

            return

        try:

            if barcode is None:

                barcode = (getattr(self, 'barcode_input', None).text() if getattr(self, 'barcode_input', None) else None)

        except Exception:

            barcode = None

            

        try:

            from pos_app.models.database import Product

            from pos_app.utils.barcode_validator import validate_barcode_input



            # First, validate and clean the barcode similar to the shared barcode widget

            validation = validate_barcode_input(barcode)

            cleaned = validation.get('cleaned_barcode', barcode)



            query = self.controller.session.query(Product)



            # Try exact match on barcode or SKU using cleaned value

            product = query.filter(

                (Product.barcode == cleaned) | (Product.sku == cleaned)

            ).first()



            # If not found, fall back to raw text (in case of formatting differences)

            if not product and cleaned != barcode:

                product = query.filter(

                    (Product.barcode == barcode) | (Product.sku == barcode)

                ).first()



            if product:

                self.add_product_to_cart(product)

                try:

                    self._last_barcode_add_ts = time.monotonic()

                except Exception:

                    self._last_barcode_add_ts = 0.0

                # Set flag to prevent Enter from completing sale immediately after barcode add

                self._barcode_just_added = True

                if hasattr(self, 'barcode_input'):

                    self.barcode_input.clear()

            else:

                # Quietly ignore not found to avoid blocking scanners with popups

                pass



        except Exception as e:

            msg = QMessageBox(self)

            msg.setIcon(QMessageBox.Critical)

            msg.setWindowTitle("Barcode Error")

            msg.setText(f"Error processing barcode: {str(e)}")

            msg.setStandardButtons(QMessageBox.Ok)

            msg.exec()



    def calculate_change(self):

        """Calculate and display change when amount paid changes"""

        try:

            amount_paid = self.amount_paid_input.value()

            

            # Calculate total with tax (same as update_totals)

            if not self.current_cart:

                total_amount = 0.0

            else:

                subtotal = sum(item['quantity'] * item['price'] for item in self.current_cart)



                # Use the unified discount getter (supports both QDoubleSpinBox and QLineEdit variants)

                try:

                    discount = float(self._get_discount_amount_value() or 0.0)

                except Exception:

                    discount = 0.0

                

                taxable_amount = subtotal - discount

                tax = taxable_amount * (self.tax_rate / 100)

                total_amount = taxable_amount + tax

            

            change = amount_paid - total_amount

            

            if change >= 0:

                self.change_display.setText(f"Rs {change:,.2f}")

                self.change_display.setStyleSheet("""

                    QLabel {

                        border: 2px solid #10b981;

                        border-radius: 8px;

                        padding: 12px 16px;

                        font-size: 18px;

                        font-weight: 700;

                        background: #f0fdf4;

                        color: #059669;

                        min-height: 20px;

                    }

                """)

            else:

                self.change_display.setText(f"Rs {abs(change):,.2f} SHORT")

                self.change_display.setStyleSheet("""

                    QLabel {

                        border: 2px solid #dc2626;

                        border-radius: 8px;

                        padding: 12px 16px;

                        font-size: 18px;

                        font-weight: 700;

                        background: #fef2f2;

                        color: #dc2626;

                        min-height: 20px;

                    }

                """)

                

        except Exception as e:

            self.change_display.setText("Rs 0.00")



    def show_product_selector(self):

        """Show a dialog with a products table for easy product selection"""

        try:

            from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel

            from PySide6.QtCore import Qt

        except ImportError:

            from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QHeaderView, QPushButton, QLabel

            from PyQt6.QtCore import Qt

        

        # Create dialog

        dialog = QDialog(self)

        dialog.setWindowTitle("Select Product")

        dialog.setFixedSize(900, 600)

        dialog.setStyleSheet("""

            QDialog {

                background: #f8fafc;

            }

        """)

        

        # Layout

        layout = QVBoxLayout(dialog)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(16)

        

        # Title

        title = QLabel("📦 Select Product to Add to Cart")

        title.setStyleSheet("""

            font-size: 18px;

            font-weight: 700;

            color: #1e293b;

            margin-bottom: 10px;

        """)

        layout.addWidget(title)

        

        # Products table

        products_table = QTableWidget()

        products_table.setColumnCount(6)

        products_table.setHorizontalHeaderLabels([

            "Product Name", "SKU", "Stock", "Purchase Price", "Retail Price", "Wholesale Price"

        ])

        

        # Style the table

        products_table.setStyleSheet("""

            QTableWidget {

                background: Qt.white;

                border: 1px solid #e2e8f0;

                border-radius: 8px;

                gridline-color: #e2e8f0;

                font-size: 14px;

                color: #1e293b;

                selection-background-color: #fef3c7;

                alternate-background-color: #f8fafc;

            }

            QTableWidget::item {

                padding: 8px;

                border-bottom: 1px solid #e2e8f0;

            }

            QTableWidget::item:selected {

                background: #fef3c7;

                color: #92400e;

            }

            QHeaderView::section {

                background: #f8fafc;

                color: #374151;

                font-weight: 600;

                font-size: 13px;

                padding: 12px;

                border: none;

                border-bottom: 2px solid #e2e8f0;

            }

        """)

        

        # Load products

        try:

            from pos_app.models.database import Product

            products = self.controller.session.query(Product).all()

            products_table.setRowCount(len(products))

            

            for row, product in enumerate(products):

                # Product name

                name_item = QTableWidgetItem(getattr(product, 'name', ''))

                products_table.setItem(row, 0, name_item)

                

                # SKU

                sku_item = QTableWidgetItem(getattr(product, 'sku', ''))

                products_table.setItem(row, 1, sku_item)

                

                # Stock

                stock = getattr(product, 'stock_level', 0)

                stock_item = QTableWidgetItem(str(stock))

                if stock <= 0:

                    stock_item.setForeground(QColor("#ef4444"))  # Red

                elif stock <= getattr(product, 'reorder_level', 5):

                    stock_item.setForeground(QColor("#f59e0b"))  # Orange

                else:

                    stock_item.setForeground(QColor("#10b981"))  # Green

                products_table.setItem(row, 2, stock_item)

                

                # Purchase price

                purchase_price = getattr(product, 'purchase_price', 0)

                try:

                    purchase_item = QTableWidgetItem(f"Rs {float(purchase_price):,.2f}")

                except:

                    purchase_item = QTableWidgetItem("Rs 0.00")

                products_table.setItem(row, 3, purchase_item)

                

                # Retail price

                retail_price = getattr(product, 'retail_price', 0)

                try:

                    retail_item = QTableWidgetItem(f"Rs {float(retail_price):,.2f}")

                except:

                    retail_item = QTableWidgetItem("Rs 0.00")

                products_table.setItem(row, 4, retail_item)

                

                # Wholesale price

                wholesale_price = getattr(product, 'wholesale_price', 0)

                try:

                    wholesale_item = QTableWidgetItem(f"Rs {float(wholesale_price):,.2f}")

                except:

                    wholesale_item = QTableWidgetItem("Rs 0.00")

                products_table.setItem(row, 5, wholesale_item)

            

        except Exception as e:

            print(f"Error loading products: {e}")

        

        # Set column widths to make prices visible

        header = products_table.horizontalHeader()

        header.setSectionResizeMode(0, QHeaderView.Stretch)  # Product name - stretch

        header.resizeSection(1, 120)  # SKU

        header.resizeSection(2, 80)   # Stock

        header.resizeSection(3, 120)  # Purchase Price

        header.resizeSection(4, 120)  # Retail Price

        header.resizeSection(5, 120)  # Wholesale Price

        

        # Configure table

        products_table.setSelectionBehavior(QTableWidget.SelectRows)

        products_table.setAlternatingRowColors(True)

        products_table.setSortingEnabled(True)

        

        layout.addWidget(products_table)

        

        # Buttons

        button_layout = QHBoxLayout()

        button_layout.addStretch()

        

        cancel_btn = QPushButton("Cancel")

        cancel_btn.setStyleSheet("""

            QPushButton {

                background: #f1f5f9;

                color: #374151;

                border: 1px solid #d1d5db;

                border-radius: 6px;

                padding: 8px 16px;

                font-size: 14px;

                font-weight: 500;

            }

            QPushButton:hover {

                background: #e5e7eb;

            }

        """)

        cancel_btn.clicked.connect(dialog.reject)

        button_layout.addWidget(cancel_btn)

        

        add_btn = QPushButton("➕ Add Selected Product")

        add_btn.setStyleSheet("""

            QPushButton {

                background: #10b981;

                color: Qt.white;

                border: none;

                border-radius: 6px;

                padding: 8px 16px;

                font-size: 14px;

                font-weight: 600;

            }

            QPushButton:hover {

                background: #059669;

            }

        """)

        add_btn.clicked.connect(lambda: self._add_selected_product(products_table, dialog))

        button_layout.addWidget(add_btn)

        

        layout.addLayout(button_layout)

        

        # Double-click to add

        products_table.doubleClicked.connect(lambda: self._add_selected_product(products_table, dialog))

        

        # Show dialog

        dialog.exec()

        

    def _add_selected_product(self, table, dialog):

        """Add the selected product from the table to cart"""

        current_row = table.currentRow()

        if current_row >= 0:

            try:

                from pos_app.models.database import Product

                products = self.controller.session.query(Product).all()

                if current_row < len(products):

                    product = products[current_row]

                    self.add_product_to_cart(product)

                    dialog.accept()

            except Exception as e:

                QMessageBox.warning(self, "Error", f"Failed to add product: {str(e)}")

    

    def load_refund_invoice(self):

        """Load a refund invoice by ID"""

        try:

            invoice_id_text = self.refund_invoice_input.text().strip()

            if not invoice_id_text:

                QMessageBox.warning(self, "Error", "Please enter an invoice ID to refund")

                return

            

            try:

                sale = self._find_sale_by_invoice_input(invoice_id_text)

                

                if not sale:

                    QMessageBox.warning(self, "Error", f"Invoice '{invoice_id_text}' not found")

                    return



                self._refund_source_sale = sale



                try:

                    self._refund_original_subtotal = float(getattr(sale, 'subtotal', 0.0) or 0.0)

                except Exception:

                    self._refund_original_subtotal = 0.0

                try:

                    self._refund_original_discount = float(getattr(sale, 'discount_amount', 0.0) or 0.0)

                except Exception:

                    self._refund_original_discount = 0.0



                # Backward compatibility: some older invoices may not have discount_amount stored.

                # In that case, derive discount from stored totals (or paid amount for cash sales).

                try:

                    if float(getattr(self, '_refund_original_discount', 0.0) or 0.0) <= 0.0:

                        try:

                            sub = float(getattr(sale, 'subtotal', 0.0) or 0.0)

                        except Exception:

                            sub = 0.0

                        try:

                            tax = float(getattr(sale, 'tax_amount', 0.0) or 0.0)

                        except Exception:

                            tax = 0.0

                        try:

                            tot = float(getattr(sale, 'total_amount', 0.0) or 0.0)

                        except Exception:

                            tot = 0.0

                        try:

                            paid = float(getattr(sale, 'paid_amount', 0.0) or 0.0)

                        except Exception:

                            paid = 0.0



                        derived = 0.0

                        # Preferred derivation: subtotal + tax - total_amount

                        if sub > 0.0 and tot > 0.0:

                            derived = (sub + tax) - tot



                        # Fallback: for completed CASH retail sales, paid amount often equals final total.

                        if derived <= 0.0:

                            try:

                                pm = str(getattr(sale, 'payment_method', '') or '').strip().lower()

                            except Exception:

                                pm = ''

                            try:

                                is_wh = bool(getattr(sale, 'is_wholesale', False))

                            except Exception:

                                is_wh = False

                            if (pm == 'cash') and (not is_wh) and sub > 0.0 and paid > 0.0:

                                derived = (sub + tax) - paid



                        if derived > 0.0:

                            # Cap derived discount so it can't exceed subtotal (including tax buffer)

                            derived = min(float(derived), float(sub + tax))

                            self._refund_original_discount = float(derived)

                except Exception:

                    pass



                # Inline refund: load items into cart, user sets refund quantities in main table

                if not self._show_refund_selection_dialog(sale):

                    return

                

                # Enter refund mode after loading items

                self.enter_refund_mode()

                self.refund_of_sale_id = sale.id

                print(f"[DEBUG] Entered refund mode for sale ID: {sale.id}")



                # After the cart table/spinboxes are built, recompute and re-apply refund discount.

                # This prevents the discount widget from ending up as 0 due to early recalculation.

                try:

                    # Ensure original subtotals are usable for proration

                    if float(getattr(self, '_refund_original_items_subtotal', 0.0) or 0.0) <= 0.0:

                        try:

                            self._refund_original_items_subtotal = float(getattr(self, '_refund_original_subtotal', 0.0) or 0.0)

                        except Exception:

                            self._refund_original_items_subtotal = 0.0

                    if float(getattr(self, '_refund_original_items_subtotal', 0.0) or 0.0) <= 0.0:

                        try:

                            self._refund_original_items_subtotal = float(sum(

                                [float(getattr(it, 'total', 0.0) or 0.0) for it in (getattr(sale, 'items', []) or [])]

                            ) or 0.0)

                        except Exception:

                            self._refund_original_items_subtotal = 0.0



                    self._update_refund_discount_from_current_cart()



                    # Always ensure we display the (original/derived) discount, not the stored field which may be 0.

                    try:

                        self._set_discount_amount_value(float(getattr(self, '_refund_original_discount', 0.0) or 0.0))

                    except Exception:

                        sub = 0.0

                    try:

                        tax = float(getattr(sale, 'tax_amount', 0.0) or 0.0)

                    except Exception:

                        tax = 0.0

                    try:

                        tot = float(getattr(sale, 'total_amount', 0.0) or 0.0)

                    except Exception:

                        tot = 0.0

                    try:

                        paid = float(getattr(sale, 'paid_amount', 0.0) or 0.0)

                    except Exception:

                        paid = 0.0



                    derived = 0.0

                    # Preferred derivation: subtotal + tax - total_amount

                    if sub > 0.0 and tot > 0.0:

                        derived = (sub + tax) - tot



                    # Fallback: for completed CASH retail sales, paid amount often equals final total.

                    if derived <= 0.0:

                        try:

                            pm = str(getattr(sale, 'payment_method', '') or '').strip().lower()

                        except Exception:

                            pm = ''

                        try:

                            is_wh = bool(getattr(sale, 'is_wholesale', False))

                            pass



                            self.amount_paid_input.setValue(float(getattr(sale, 'paid_amount', 0.0) or 0.0))

                        except Exception:

                            pass

                            

                except Exception:

                    pass

                

                # Set customer from original sale

                try:

                    inv = str(getattr(sale, 'invoice_number', '') or '')

                    paid = float(getattr(sale, 'paid_amount', 0.0) or 0.0)

                    disc = float(getattr(sale, 'discount_amount', 0.0) or 0.0)

                    tot = float(getattr(sale, 'total_amount', 0.0) or 0.0)

                    cust = getattr(getattr(sale, 'customer', None), 'name', None) or 'Walk-in'

                    

                    # Get original payment method and sales type

                    original_payment_method = str(getattr(sale, 'payment_method', 'Cash') or 'Cash').strip()

                    original_is_wholesale = bool(getattr(sale, 'is_wholesale', False))

                    

                    if hasattr(self, 'refund_sale_info_label'):

                        self.refund_sale_info_label.setText(

                            f"Invoice: {inv} | Customer: {cust} | Paid: Rs {paid:,.2f} | Discount: Rs {disc:,.2f} | Total: Rs {tot:,.2f}"

                        )

                    

                    # Set customer dropdown to original sale's customer

                    try:

                        if hasattr(self, 'customer_combo') and cust != 'Walk-in':

                            # Find customer in dropdown

                            customer_index = self.customer_combo.findText(cust)

                            if customer_index >= 0:

                                self.customer_combo.setCurrentIndex(customer_index)

                                print(f"[DEBUG] Set customer to: {cust}")

                            else:

                                print(f"[DEBUG] Customer '{cust}' not found in dropdown")

                    except Exception as e:

                        print(f"[DEBUG] Error setting customer dropdown: {e}")

                    

                    # Set payment method to original sale's payment method

                    try:

                        if hasattr(self, 'pay_method_combo'):

                            payment_index = self.pay_method_combo.findText(original_payment_method)

                            if payment_index >= 0:

                                self.pay_method_combo.setCurrentIndex(payment_index)

                                print(f"[DEBUG] Set payment method to: {original_payment_method}")

                            else:

                                print(f"[DEBUG] Payment method '{original_payment_method}' not found, using default")

                    except Exception as e:

                        print(f"[DEBUG] Error setting payment method: {e}")

                    

                    # Set sales type to original sale's sales type

                    try:

                        if hasattr(self, 'sale_type_combo'):

                            retail_index = self.sale_type_combo.findText("Walk-in / Retail")

                            wholesale_index = self.sale_type_combo.findText("Wholesale")

                            

                            if original_is_wholesale and wholesale_index >= 0:

                                self.sale_type_combo.setCurrentIndex(wholesale_index)

                                print(f"[DEBUG] Set sales type to: Wholesale")

                            elif retail_index >= 0:

                                self.sale_type_combo.setCurrentIndex(retail_index)

                                print(f"[DEBUG] Set sales type to: Walk-in / Retail")

                            else:

                                print(f"[DEBUG] Sales type not found in combo")

                    except Exception as e:

                        print(f"[DEBUG] Error setting sales type: {e}")

                        

                except Exception:

                    pass

                

                # Ensure totals reflect the final discount/qty state

                try:

                    self.update_totals()

                except Exception:

                    pass

                try:

                    if hasattr(self, 'calculate_change'):

                        self.calculate_change()

                except Exception:

                    pass

                

            except Exception as db_error:

                # Auto-recovery: Try to handle database errors

                print(f"[ERROR] Database error loading refund invoice: {db_error}")

                self.controller.session.rollback()

                QMessageBox.critical(self, "Error", f"Failed to load refund invoice: {str(db_error)}")

            

        except Exception as e:

            print(f"[ERROR] Unexpected error in load_refund_invoice: {e}")

            QMessageBox.critical(self, "Error", f"Failed to load refund invoice: {str(e)}")



    def _find_sale_by_invoice_input(self, invoice_input: str):

        """Best-effort lookup for invoice numbers.



        Supports:

        - Numeric: 1 / 0001

        - Strings: "1", "INV-1", "INV-0001"

        - Any exact stored invoice_number string

        """

        try:

            from pos_app.models.database import Sale

            from sqlalchemy import or_

        except Exception:

            return None



        raw = (invoice_input or "").strip()

        if not raw:

            return None



        candidates = []

        def _add(v):

            v = (v or "").strip()

            if v and v not in candidates:

                candidates.append(v)



        _add(raw)



        # If numeric-like, normalize leading zeros

        numeric_part = ""

        try:

            if raw.isdigit():

                numeric_part = str(int(raw))

                _add(numeric_part)

                _add(raw.lstrip('0') or '0')

            else:

                # Extract trailing digits (e.g. INV-0001)

                import re

                m = re.search(r"(\d+)$", raw)

                if m:

                    numeric_part = str(int(m.group(1)))

                    _add(m.group(1))

                    _add(numeric_part)

        except Exception:

            numeric_part = ""



        # Common prefixes

        if numeric_part:

            _add(f"INV-{numeric_part}")

            _add(f"INV-{numeric_part.zfill(4)}")

            _add(f"INV-{numeric_part.zfill(6)}")



        session = getattr(self.controller, 'session', None)

        if session is None:

            return None



        # Exact match first

        try:

            q = session.query(Sale).filter(Sale.invoice_number.in_(candidates))

            sale = q.order_by(Sale.id.desc()).first()

            if sale:

                return sale

        except Exception:

            pass



        # Fallback: LIKE match on trailing digits

        try:

            if numeric_part:

                like_patterns = [f"%{numeric_part}", f"%{numeric_part.zfill(4)}", f"%{numeric_part.zfill(6)}"]

                q = session.query(Sale).filter(or_(*[Sale.invoice_number.ilike(p) for p in like_patterns]))

                sale = q.order_by(Sale.id.desc()).first()

                if sale:

                    return sale

        except Exception:

            pass



        return None



    def _show_refund_selection_dialog(self, sale):

        try:

            items = list(getattr(sale, 'items', []) or [])

            if not items:

                return False



            try:

                self._refund_original_items_subtotal = float(sum([float(getattr(it, 'total', 0.0) or 0.0) for it in items]) or 0.0)

            except Exception:

                self._refund_original_items_subtotal = float(getattr(sale, 'subtotal', 0.0) or 0.0)



            # Build inline cart: include all items from original sale.

            # User will set `quantity` (refund qty) directly on the main cart table.

            new_cart = []

            qa_mode = str(os.environ.get('POS_QA_MODE', '') or '').strip() == '1'

            

            # Fetch remaining refund capacity from controller

            remaining_capacity = {}

            try:

                if self.controller and hasattr(self.controller, 'get_remaining_refund_capacity'):

                    remaining_capacity = self.controller.get_remaining_refund_capacity(getattr(sale, 'id', None))

                    print(f"[DEBUG] Remaining refund capacity: {remaining_capacity}")

            except Exception as e:

                print(f"[DEBUG] Error fetching refund capacity: {e}")



            for idx, it in enumerate(items):

                try:

                    pid = getattr(it, 'product_id', None)

                    p = getattr(it, 'product', None)

                    name = p.name if p is not None else str(pid)

                    bought_qty = float(getattr(it, 'quantity', 0) or 0)

                    unit_price = float(getattr(it, 'unit_price', 0.0) or 0.0)

                    purchase_price = float(getattr(p, 'purchase_price', 0.0) or 0.0) if p is not None else 0.0

                    stock_level = getattr(p, 'stock_level', None) if p is not None else None

                    item_discount = float(getattr(it, 'discount', 0.0) or 0.0)

                    item_discount_type = str(getattr(it, 'discount_type', '') or '')

                    line_total = float(getattr(it, 'total', 0.0) or 0.0)

                except Exception:

                    continue



                rq = min(bought_qty, float(remaining_capacity.get(pid, bought_qty)))

                # Always default to remaining refundable qty

                

                if rq <= 0 and not qa_mode:

                    print(f"[DEBUG] Skipping product {name} (id={pid}) - already fully refunded")

                    continue



                new_cart.append({

                    'id': pid,

                    'name': name,

                    'price': unit_price,

                    'purchase_price': purchase_price,

                    'quantity': rq,

                    'bought_qty': bought_qty,

                    'max_refund_qty': float(remaining_capacity.get(pid, bought_qty)),

                    'stock_level': stock_level if stock_level is not None else '',

                    'item_discount': item_discount,

                    'item_discount_type': item_discount_type,

                    'refund_unit_subtotal': (line_total / bought_qty) if bought_qty else unit_price,

                })

                

                # Fix negative stock for this product if needed

                if pid is not None:

                    try:

                        self.controller.fix_negative_stock_for_product(pid)

                    except Exception as e:

                        print(f"[DEBUG] Error fixing negative stock for product {pid}: {e}")

            

            # Assign the built cart to current_cart

            self.current_cart = new_cart

            

            # Automatically mark all items for refund when loading a refund invoice

            # This ensures items are processed as returns, not as new sales

            if hasattr(self, '_refund_marked_items'):

                self._refund_marked_items.clear()

            else:

                self._refund_marked_items = set()

            

            # Mark all loaded items for refund

            for item in new_cart:

                if item.get('id'):

                    self._refund_marked_items.add(item['id'])

                    print(f"[DEBUG] Auto-marked item for refund: {item.get('name')} (id={item['id']})")

            

            print(f"[DEBUG] Total items marked for refund: {len(self._refund_marked_items)}")

            

            self.refund_of_sale_id = getattr(sale, 'id', None)



            self.update_totals()

            return True

        except Exception:

            return False

    

    def update_totals(self):

        """Update all total labels using a single consistent calculation."""

        try:

            items_count, subtotal, total_cost, profit, discount, tax, total = self._calculate_totals()



            if hasattr(self, 'cart_items_label'):

                try:

                    self.cart_items_label.setText(f"Items: {items_count}")

                except Exception:

                    pass



            if hasattr(self, 'cart_subtotal_label'):

                self.cart_subtotal_label.setText(f"Subtotal: Rs {subtotal:,.2f}")

            if hasattr(self, 'cart_total_cost_label'):

                self.cart_total_cost_label.setText(f"Total Cost: Rs {total_cost:,.2f}")

            if hasattr(self, 'cart_profit_label'):

                self.cart_profit_label.setText(f"Total Profit: Rs {profit:,.2f}")



            if hasattr(self, 'cart_tax_label'):

                try:

                    tr = float(getattr(self, 'tax_rate', 0.0) or 0.0)

                except Exception:

                    tr = 0.0

                self.cart_tax_label.setText(f"Tax ({tr:.0f}%): Rs {tax:,.2f}")



            if hasattr(self, 'cart_total_label'):

                self.cart_total_label.setText(f"Final Total: Rs {total:,.2f}")



            # Update change display

            try:

                if hasattr(self, 'calculate_change'):

                    self.calculate_change()

                elif hasattr(self, 'change_label') and hasattr(self, 'amount_paid_input'):

                    paid = float(self.amount_paid_input.value())

                    change = max(0.0, paid - total)

                    self.change_label.setText(f"Change to Give: Rs {change:,.2f}")

            except Exception as e:

                print(f"[DEBUG] Error updating change display: {e}")

        except Exception as e:

            print(f"[DEBUG] Error updating totals: {e}")

            return

