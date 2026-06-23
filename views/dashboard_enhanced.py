"""
Enhanced Dashboard with Cash Register and Daily Summary
"""
try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QGridLayout, QComboBox, QScrollArea, QGroupBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QMessageBox,
        QAbstractItemView, QSizePolicy
    )
    from PySide6.QtCore import Qt, Signal, QTimer, QDate
    from PySide6.QtGui import QFont
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QFrame, QGridLayout, QComboBox, QScrollArea, QGroupBox,
        QTableWidget, QTableWidgetItem, QHeaderView, QDateEdit, QMessageBox,
        QAbstractItemView, QSizePolicy
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal, QTimer, QDate
    from PyQt6.QtGui import QFont
from datetime import datetime, timedelta, date
from decimal import Decimal

from pos_app.database.db_utils import get_db_session
from pos_app.models.database import (
    Sale, Purchase, Expense, Payment, CashDrawerSession,
    CashMovement, Product, Customer, Supplier, SaleItem, PurchaseItem
)
from pos_app.views.dialogs.cash_register_dialog import CashRegisterDialog
from pos_app.views.dialogs.cash_register_close_dialog import CashRegisterCloseDialog

class DashboardEnhanced(QWidget):
    """Enhanced dashboard with cash register and daily summary"""
    
    refresh_requested = Signal()
    action_new_sale = Signal()
    action_add_product = Signal()
    action_add_customer = Signal()
    action_generate_report = Signal()
    action_view_low_stock = Signal()
    
    def __init__(self, controllers, parent=None):
        super().__init__(parent)
        print("[DEBUG] DashboardEnhanced initialized - CASH REGISTER SHOULD WORK!")
        self.controllers = controllers
        self.current_session = None
        self.start_date = date.today()
        self.end_date = date.today()
        
        self.setup_ui()
        self.load_data()
        
        # Auto-refresh every 5 minutes (reduced from 30s to prevent UI freezing)
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.load_data)
        self.refresh_timer.start(300000)  # 5 minutes (300 seconds)
    
    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(15)

        # Create scrollable content area
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollBar:vertical {
                background: #f3f4f6;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #d1d5db;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9ca3af;
            }
        """)

        # Create content widget for scroll area
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(15)
        
        # Apply modern dashboard styling - Dark theme with good contrast
        self.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #0f172a, stop:0.5 #1e293b, stop:1 #1a1f35);
                color: #f1f5f9;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
            QScrollArea {
                background: transparent;
                border: none;
            }
        """)
        
        # Modern Header with clean design
        header_widget = QWidget()
        header_widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #4f46e5, stop:1 #7c3aed);
                border-radius: 12px;
                padding: 20px;
                margin-bottom: 10px;
                color: white;
            }
        """)
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 15, 20, 15)
        
        # Modern title with icon
        title_layout = QVBoxLayout()
        title = QLabel("📊 Business Dashboard")
        title.setStyleSheet("""
            font-size: 24px; 
            font-weight: 700; 
            color: Qt.white;
            margin: 0;
        """)
        
        subtitle = QLabel("Real-time business insights")
        subtitle.setStyleSheet("""
            font-size: 12px; 
            color: rgba(255,255,255,0.9);
            margin-top: 3px;
            font-weight: 400;
        """)
        
        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)
        header_layout.addLayout(title_layout)
        
        header_layout.addStretch()
        
        # Modern controls container
        controls_widget = QWidget()
        controls_widget.setStyleSheet("""
            QWidget {
                background: rgba(255,255,255,0.1);
                border-radius: 10px;
                padding: 15px;
            }
        """)
        controls_layout = QHBoxLayout(controls_widget)
        controls_layout.setSpacing(15)
        
        # Date filter with modern styling
        filter_label = QLabel("📅 Period:")
        filter_label.setStyleSheet("""
            font-size: 14px; 
            color: Qt.white;
            font-weight: 600;
        """)
        controls_layout.addWidget(filter_label)
        
        self.period_combo = QComboBox()
        self.period_combo.addItems(["Today", "Yesterday", "Last 7 Days", "This Month", "Custom"])
        self.period_combo.setStyleSheet("""
            QComboBox {
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                padding: 8px 15px;
                font-size: 13px;
                font-weight: 600;
                color: Qt.white;
                min-width: 120px;
            }
            QComboBox:hover {
                background: rgba(255,255,255,0.3);
                border-color: rgba(255,255,255,0.5);
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid Qt.white;
                margin-right: 5px;
            }
        """)
        self.period_combo.currentTextChanged.connect(self.on_period_changed)
        controls_layout.addWidget(self.period_combo)
        
        # Custom date range with modern styling
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setDate(QDate.currentDate())
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setVisible(False)
        self.start_date_edit.setStyleSheet("""
            QDateEdit {
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: Qt.white;
                font-weight: 600;
            }
        """)
        self.start_date_edit.dateChanged.connect(self.on_custom_date_changed)
        controls_layout.addWidget(self.start_date_edit)
        
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setDate(QDate.currentDate())
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setVisible(False)
        self.end_date_edit.setStyleSheet("""
            QDateEdit {
                background: rgba(255,255,255,0.2);
                border: 2px solid rgba(255,255,255,0.3);
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 13px;
                color: Qt.white;
                font-weight: 600;
            }
        """)
        self.end_date_edit.dateChanged.connect(self.on_custom_date_changed)
        controls_layout.addWidget(self.end_date_edit)
        
        # Modern refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #10b981, stop:1 #059669);
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 13px;
                font-weight: 700;
                color: Qt.white;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                    stop:0 #059669, stop:1 #047857);
                transform: translateY(-1px);
            }
            QPushButton:pressed {
                background: #047857;
                transform: translateY(0px);
            }
        """)
        refresh_btn.clicked.connect(self.load_data)
        controls_layout.addWidget(refresh_btn)
        
        header_layout.addWidget(controls_widget)
        main_layout.addWidget(header_widget)
        
        # Scroll area for content with modern styling
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.1);
                width: 12px;
                border-radius: 6px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: rgba(255,255,255,0.3);
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(255,255,255,0.5);
            }
        """)
        
        content_widget = QWidget()
        content_widget.setStyleSheet("background: transparent;")
        content_layout = QVBoxLayout(content_widget)
        content_layout.setSpacing(15)
        content_layout.setContentsMargins(0, 0, 0, 0)
        
        # Cash Register Section with modern design
        self.cash_register_widget = self.create_cash_register_section()
        content_layout.addWidget(self.cash_register_widget)
        
        # Stats Cards with modern grid layout
        self.stats_widget = self.create_stats_section()
        content_layout.addWidget(self.stats_widget)
        
        # Quick Actions Section
        self.quick_actions_widget = self.create_quick_actions_section()
        content_layout.addWidget(self.quick_actions_widget)
        
        # Daily Summary Receipt with modern design
        self.summary_widget = self.create_summary_section()
        content_layout.addWidget(self.summary_widget)
        
        # Activity Tracking Section
        self.activity_widget = self.create_activity_tracking_section()
        content_layout.addWidget(self.activity_widget)
        
        # Set the content widget to scroll area and add to main layout
        scroll_area.setWidget(content_widget)
        main_layout.addWidget(scroll_area)
    
    def create_cash_register_section(self):
        """Create modern cash register section"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(16, 185, 129, 0.15), stop:1 rgba(59, 130, 246, 0.15));
                border: 1px solid rgba(16, 185, 129, 0.3);
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Modern section title
        title = QLabel("💰 Cash Register")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 10px;
                    """)
        layout.addWidget(title)
        
        # Status and balance in one compact row
        status_layout = QHBoxLayout()
        
        self.register_status_label = QLabel("● CLOSED")
        self.register_status_label.setStyleSheet("font-size: 13px; color: #ef4444; font-weight: 600;")
        status_layout.addWidget(self.register_status_label)
        
        separator = QLabel("|")
        separator.setStyleSheet("color: #475569;")
        status_layout.addWidget(separator)
        
        self.opening_balance_label = QLabel("Opening: Rs 0.00")
        self.opening_balance_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        status_layout.addWidget(self.opening_balance_label)
        
        separator = QLabel("|")
        separator.setStyleSheet("color: #475569;")
        status_layout.addWidget(separator)
        
        self.current_balance_label = QLabel("Current: Rs 0.00")
        self.current_balance_label.setStyleSheet("font-size: 13px; color: #10b981; font-weight: 600;")
        status_layout.addWidget(self.current_balance_label)
        
        status_layout.addStretch()
        
        # Buttons inline
        self.open_register_btn = QPushButton("🔓 Open")
        self.open_register_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: Qt.white;
                border: none;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        self.open_register_btn.clicked.connect(self.open_register)
        # Add a test to verify the button is connected
        print(f"[DEBUG] Open register button connected: {self.open_register_btn}")
        status_layout.addWidget(self.open_register_btn)
        
        self.close_register_btn = QPushButton("🔒 Close")
        self.close_register_btn.setStyleSheet("""
            QPushButton {
                background: #ef4444;
                color: Qt.white;
                border: none;
                padding: 6px 16px;
                font-size: 12px;
                font-weight: 600;
                border-radius: 4px;
            }
            QPushButton:hover {
                background: #dc2626;
            }
            QPushButton:disabled {
                background: #475569;
            }
        """)
        self.close_register_btn.clicked.connect(self.close_register)
        self.close_register_btn.setEnabled(False)
        status_layout.addWidget(self.close_register_btn)
        
        layout.addLayout(status_layout)
        
        return widget
    
    def create_stats_section(self):
        """Create modern stats cards section"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: #172033;
                border: 1px solid #334155;
                border-radius: 8px;
                padding: 4px;
                margin: 4px 0;
            }
        """)
        
        main_layout = QVBoxLayout(widget)
        main_layout.setSpacing(6)
        main_layout.setContentsMargins(8, 8, 8, 8)
        
        # Section title
        title = QLabel("📊 Business Analytics")
        title.setStyleSheet("""
            font-size: 16px;
            font-weight: 700;
            color: #e5e7eb;
            margin-bottom: 4px;
                    """)
        main_layout.addWidget(title)
        
        # Grid for cards
        layout = QGridLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Will be populated in load_data
        self.stats_cards = {}
        
        main_layout.addLayout(layout)
        return widget
    
    def create_summary_section(self):
        """Create modern daily summary section"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: rgba(255,255,255,0.03);
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 15px;
                padding: 20px;
                margin: 10px 0;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(20)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Section title
        title = QLabel("📄 Daily Summary")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #f8fafc;
            margin-bottom: 10px;
                    """)
        layout.addWidget(title)
        
        # Summary table with better spacing and scrolling
        self.summary_table = QTableWidget()
        self.summary_table.setColumnCount(5)
        self.summary_table.setHorizontalHeaderLabels(["Type", "Description", "Items", "Qty", "Amount"])
        
        # Set column widths
        self.summary_table.setColumnWidth(0, 100)  # Type
        self.summary_table.setColumnWidth(2, 60)   # Items
        self.summary_table.setColumnWidth(3, 60)   # Qty
        self.summary_table.setColumnWidth(4, 120)  # Amount
        self.summary_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)  # Description stretches
        
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setMinimumHeight(200)
        self.summary_table.setMaximumHeight(300)
        self.summary_table.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.summary_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.setShowGrid(False)
        self.summary_table.setStyleSheet("""
            QTableWidget {
                background: #0f172a;
                color: #f8fafc;
                border: 1px solid #334155;
                border-radius: 6px;
                font-size: 12px;
            }
            QHeaderView::section {
                background: #1e293b;
                color: #94a3b8;
                padding: 10px 8px;
                border: none;
                font-weight: 600;
                font-size: 11px;
                text-transform: uppercase;
            }
            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #1e293b;
            }
            QTableWidget::item:selected {
                background: #334155;
            }
        """)
        
        layout.addWidget(self.summary_table)
        
        # Totals
        totals_layout = QGridLayout()
        totals_layout.setSpacing(10)
        
        self.total_in_label = QLabel("Total IN: Rs 0.00")
        self.total_in_label.setStyleSheet("font-size: 16px; color: #10b981; font-weight: bold;")
        totals_layout.addWidget(self.total_in_label, 0, 0)
        
        self.total_out_label = QLabel("Total OUT: Rs 0.00")
        self.total_out_label.setStyleSheet("font-size: 16px; color: #ef4444; font-weight: bold;")
        totals_layout.addWidget(self.total_out_label, 0, 1)
        
        self.net_total_label = QLabel("NET: Rs 0.00")
        self.net_total_label.setStyleSheet("font-size: 18px; color: #3b82f6; font-weight: bold;")
        totals_layout.addWidget(self.net_total_label, 1, 0, 1, 2)
        
        layout.addLayout(totals_layout)
        
        return widget
    
    def create_quick_actions_section(self):
        """Create modern quick actions section"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(245, 158, 11, 0.15), stop:1 rgba(239, 68, 68, 0.15));
                border: 1px solid rgba(245, 158, 11, 0.3);
                border-radius: 12px;
                padding: 20px;
                margin: 10px 0;
                box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Section title
        title = QLabel("⚡ Quick Actions")
        title.setStyleSheet("""
            font-size: 20px;
            font-weight: 700;
            color: #1e293b;
            margin-bottom: 10px;
                    """)
        layout.addWidget(title)
        
        # Actions grid
        actions_layout = QGridLayout()
        actions_layout.setSpacing(15)
        
        actions = [
            ("💰", "New Sale", "#10b981", self.action_new_sale),
            ("📦", "Add Product", "#3b82f6", self.action_add_product),
            ("👥", "Add Customer", "#8b5cf6", self.action_add_customer),
            ("📊", "Generate Report", "#f59e0b", self.action_generate_report),
            ("⚠️", "View Low Stock", "#ef4444", self.action_view_low_stock),
        ]
        
        for i, (icon, text, color, signal) in enumerate(actions):
            btn = QPushButton(f"{icon} {text}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {color}, stop:1 {self._darken_color(color)});
                    border: none;
                    border-radius: 10px;
                    padding: 12px 16px;
                    font-size: 13px;
                    font-weight: 600;
                    color: Qt.white;
                    min-height: 40px;
                }}
                QPushButton:hover {{
                    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
                        stop:0 {self._lighten_color(color)}, stop:1 {color});
                    transform: translateY(-2px);
                    box-shadow: 0 4px 12px rgba(0,0,0,0.2);
                }}
                QPushButton:pressed {{
                    background: {self._darken_color(color)};
                    transform: translateY(0px);
                }}
            """)
            btn.clicked.connect(signal.emit)
            row = i // 3
            col = i % 3
            actions_layout.addWidget(btn, row, col)
        
        layout.addLayout(actions_layout)
        return widget
    
    def open_register(self):
        """Open cash register"""
        print("[TEST] Open register method called - BUTTON IS WORKING!")
        try:
            print("[DEBUG] Open register button clicked")
            from pos_app.views.dialogs.cash_register_dialog import CashRegisterDialog
            print("[DEBUG] Import successful, creating dialog")
            # Explicitly use 'open' mode so dialog returns opening_balance
            dialog = CashRegisterDialog(mode='open', parent=self)
            print("[DEBUG] Dialog created, showing dialog")
            if dialog.exec():
                print("[DEBUG] Dialog accepted")
                data = dialog.get_data() or {}
                opening_balance = float(data.get('opening_balance', 0.0))
                notes = data.get('notes')
                print(f"[DEBUG] Opening balance: {opening_balance}, Notes: {notes}")

                # Persist to DB
                from pos_app.database.db_utils import get_db_session
                from pos_app.models.database import CashDrawerSession, User
                from datetime import datetime
                print("[DEBUG] Starting database session")

                with get_db_session() as session:
                    # Close any existing OPEN sessions defensively
                    try:
                        open_sessions = session.query(CashDrawerSession).filter(
                            CashDrawerSession.status == 'OPEN'
                        ).all()
                        for s in open_sessions:
                            s.status = 'CLOSED'
                            s.closed_at = datetime.now()
                    except Exception:
                        pass

                    # Use 'admin' user for now
                    user = session.query(User).filter(User.username == 'admin').first()
                    sess = CashDrawerSession(
                        user_id=getattr(user, 'id', None),
                        opening_balance=opening_balance,
                        expected_balance=opening_balance,
                        status='OPEN',
                        notes=notes,
                        opened_by=getattr(user, 'username', 'admin')
                    )
                    session.add(sess)
                    # Flush to get the ID, then commit
                    try:
                        session.flush()
                        print(f"[CashRegister] Opened session id={sess.id} opening={opening_balance}")
                        session.commit()  # Commit the transaction to persist the changes
                        print("[DEBUG] Database commit successful")
                    except Exception as e:
                        session.rollback()
                        print(f"[CashRegister] Error committing session: {e}")
                        raise
                print("[DEBUG] About to call load_cash_register_status")
                self.load_cash_register_status()
                print("[DEBUG] load_cash_register_status completed")
        except Exception as e:
            print(f"Error opening register: {e}")
    
    def close_register(self):
        """Close cash register"""
        try:
            print("[DEBUG] Close register button clicked")
            from pos_app.views.dialogs.cash_register_close_dialog import CashRegisterCloseDialog
            print(f"[DEBUG] Current session: {self.current_session}")
            if self.current_session:
                print("[DEBUG] Creating close dialog")
                dialog = CashRegisterCloseDialog(self.current_session, self)
                print("[DEBUG] Dialog created, showing dialog")
                if dialog.exec():
                    print("[DEBUG] Dialog accepted, reloading status")
                    self.load_cash_register_status()
            else:
                print("[DEBUG] No current session to close")
        except Exception as e:
            print(f"[DEBUG] Error closing register: {e}")
            import traceback
            traceback.print_exc()
    
    def _lighten_color(self, color):
        """Lighten a hex color"""
        color_map = {
            "#10b981": "#34d399",
            "#3b82f6": "#60a5fa", 
            "#8b5cf6": "#a78bfa",
            "#f59e0b": "#fbbf24",
            "#ef4444": "#f87171"
        }
        return color_map.get(color, color)
    
    def _darken_color(self, color):
        """Darken a hex color"""
        color_map = {
            "#10b981": "#059669",
            "#3b82f6": "#2563eb",
            "#8b5cf6": "#7c3aed", 
            "#f59e0b": "#d97706",
            "#ef4444": "#dc2626"
        }
        return color_map.get(color, color)

    def create_stat_card(self, title, value, color="#3b82f6", icon="📊"):
        """Create a clean professional stat card with visible values"""
        card = QFrame()
        card.setStyleSheet(f"""
            QFrame {{
                background: #0f172a;
                border: 1px solid {color};
                border-radius: 6px;
                padding: 6px;
                min-height: 86px;
            }}
            QFrame:hover {{
                background: #111c31;
            }}
        """)
        card.setLineWidth(0)
        card.setFrameShape(QFrame.NoFrame)
        card.setMinimumHeight(110)
        card.setMaximumHeight(160)
        card.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        
        layout = QVBoxLayout(card)
        layout.setSpacing(3)
        layout.setContentsMargins(8, 6, 8, 6)
        
        # Icon - Centered at top
        icon_label = QLabel(icon)
        icon_label.setStyleSheet(f"""
            font-size: 18px;
            color: {color};
            background: transparent;
            border: none;
            margin: 0px;
            padding: 0px;
        """)
        icon_label.setAlignment(Qt.AlignCenter)
        icon_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(icon_label, 0, Qt.AlignCenter)
        
        # Title - Centered
        title_label = QLabel(title)
        title_label.setStyleSheet("""
            font-size: 11px; 
            color: #cbd5e1; 
            font-weight: 600; 
            background: transparent;
            border: none;
            margin: 0px;
            padding: 0px;
        """)
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(title_label, 0, Qt.AlignCenter)
        
        # Value - Centered and prominent (MUST BE VISIBLE)
        value_label = QLabel(str(value))
        value_label.setStyleSheet(f"""
            font-size: 15px; 
            color: {color}; 
            font-weight: 800;
            background: transparent;
            border: none;
            margin: 0px;
            padding: 2px;
        """)
        value_label.setAlignment(Qt.AlignCenter)
        value_label.setWordWrap(True)
        value_label.setMinimumHeight(28)
        value_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        layout.addWidget(value_label, 1, Qt.AlignCenter)
        
        return card, value_label
    
    def on_period_changed(self, period):
        """Handle period change"""
        if period == "Custom":
            self.start_date_edit.setVisible(True)
            self.end_date_edit.setVisible(True)
        else:
            self.start_date_edit.setVisible(False)
            self.end_date_edit.setVisible(False)
            
            today = date.today()
            if period == "Today":
                self.start_date = today
                self.end_date = today
            elif period == "Yesterday":
                yesterday = today - timedelta(days=1)
                self.start_date = yesterday
                self.end_date = yesterday
            elif period == "Last 7 Days":
                self.start_date = today - timedelta(days=7)
                self.end_date = today
            elif period == "This Month":
                self.start_date = today.replace(day=1)
                self.end_date = today
            
            self.load_data()
    
    def on_custom_date_changed(self):
        """Handle custom date change"""
        self.start_date = self.start_date_edit.date().toPython()
        self.end_date = self.end_date_edit.date().toPython()
        self.load_data()
    
    def load_data(self):
        """Load all dashboard data"""
        self.load_cash_register_status()
        self.load_stats()
        self.load_summary()
    
    def load_cash_register_status(self):
        """Load current cash register session status"""
        try:
            print("[DEBUG] Loading cash register status")
            with get_db_session() as session:
                # Prefer the most recently opened session and infer status from its field
                active_session = (
                    session.query(CashDrawerSession)
                    .order_by(CashDrawerSession.opened_at.desc())
                    .first()
                )
                print(f"[DEBUG] Active session found: {active_session}")
                if active_session:
                    print(f"[DEBUG] Session status: {active_session.status}")
                    print(f"[DEBUG] Session opening balance: {active_session.opening_balance}")

                if active_session and str(active_session.status).upper() == 'OPEN':
                    print("[DEBUG] Session is OPEN, updating UI")
                    self.current_session = active_session
                    self.register_status_label.setText("● OPEN")
                    self.register_status_label.setStyleSheet("font-size: 13px; color: #10b981; font-weight: 600;")

                    self.opening_balance_label.setText(
                        f"Opening: Rs {Decimal(str(active_session.opening_balance or 0)):,.2f}"
                    )
                    print(f"[DEBUG] Set opening balance to: {Decimal(str(active_session.opening_balance or 0)):,.2f}")

                    # Calculate current balance from opening + movements, but never crash UI if query fails
                    current = Decimal(str(active_session.opening_balance or 0))
                    try:
                        movements = (
                            session.query(CashMovement)
                            .filter(CashMovement.session_id == active_session.id)
                            .all()
                        )
                        for mov in movements:
                            amount = Decimal(str(mov.amount or 0))
                            if mov.movement_type in ['SALE', 'DEPOSIT']:
                                current += amount
                            else:
                                current -= amount
                    except Exception:
                        pass

                    self.current_balance_label.setText(f"Current: Rs {current:,.2f}")

                    self.open_register_btn.setEnabled(False)
                    self.close_register_btn.setEnabled(True)
                    print("[DEBUG] UI updated for OPEN session")
                else:
                    print("[DEBUG] No OPEN session found, setting CLOSED state")
                    # No open session found – treat as closed
                    self.current_session = None
                    self.register_status_label.setText("● CLOSED")
                    self.register_status_label.setStyleSheet("font-size: 13px; color: #ef4444; font-weight: 600;")
                    self.opening_balance_label.setText("Opening: Rs 0.00")
                    self.current_balance_label.setText("Current: Rs 0.00")

                    self.open_register_btn.setEnabled(True)
                    self.close_register_btn.setEnabled(False)
                    print("[DEBUG] UI updated for CLOSED state")
        except Exception as e:
            # If anything goes wrong, fall back to CLOSED state but don't break dashboard
            print(f"Error loading cash register status: {e}")
            self.current_session = None
            self.register_status_label.setText("● CLOSED")
            self.register_status_label.setStyleSheet("font-size: 13px; color: #ef4444; font-weight: 600;")
            self.opening_balance_label.setText("Opening: Rs 0.00")
            self.current_balance_label.setText("Current: Rs 0.00")

            self.open_register_btn.setEnabled(True)
            self.close_register_btn.setEnabled(False)
    
    def load_stats(self):
        """Load statistics cards"""
        with get_db_session() as session:
            # Get the grid layout (it's the second item in the main layout)
            main_layout = self.stats_widget.layout()
            if main_layout.count() > 1:
                grid_layout_item = main_layout.itemAt(1)  # Grid layout is the second item
                if grid_layout_item and grid_layout_item.layout():
                    layout = grid_layout_item.layout()
                    # Clear existing cards
                    while layout.count():
                        item = layout.takeAt(0)
                        if item.widget():
                            item.widget().deleteLater()
                else:
                    return
            else:
                return
            
            # Calculate stats
            start_dt = datetime.combine(self.start_date, datetime.min.time())
            end_dt = datetime.combine(self.end_date, datetime.max.time())
            
            # SQL aggregation for sales/refunds totals. The old code did .all() and
            # summed in Python; for "This Year" that loaded 20k+ rows. func.sum lets
            # the database do it and returns one row.
            from sqlalchemy import or_, func

            date_filter = (Sale.sale_date >= start_dt, Sale.sale_date <= end_dt)
            # Include NULL status for backward compatibility with existing data
            status_ok = or_(Sale.status == 'COMPLETED', Sale.status == 'REFUNDED', Sale.status == None)

            total_normal_sales = Decimal(str(session.query(func.sum(Sale.total_amount)).filter(
                *date_filter, Sale.is_refund != True, status_ok
            ).scalar() or 0))
            total_refunds = Decimal(str(session.query(func.sum(func.abs(Sale.total_amount))).filter(
                *date_filter, Sale.is_refund == True, status_ok
            ).scalar() or 0))
            total_normal_paid = Decimal(str(session.query(func.sum(Sale.paid_amount)).filter(
                *date_filter, Sale.is_refund != True, status_ok
            ).scalar() or 0))
            total_refund_paid = Decimal(str(session.query(func.sum(func.abs(Sale.paid_amount))).filter(
                *date_filter, Sale.is_refund == True, status_ok
            ).scalar() or 0))
            sales_count = session.query(func.count(Sale.id)).filter(
                *date_filter, Sale.is_refund != True, status_ok
            ).scalar() or 0

            # NET Sales = Normal Sales - Refunds (this is the correct total)
            total_sales = total_normal_sales - total_refunds
            total_paid_on_sales = total_normal_paid - total_refund_paid
            new_credit_sales = total_sales - total_paid_on_sales

            print(f"[DASHBOARD] Normal sales: {sales_count}, Total: Rs {total_normal_sales:,.2f}")
            print(f"[DASHBOARD] Refunds: Rs {total_refunds:,.2f}")
            print(f"[DASHBOARD] Net Sales: Rs {total_sales:,.2f}")
            print(f"[DASHBOARD] New Credit Sales: Rs {new_credit_sales:,.2f}")
            
            # Purchases - Only count RECEIVED or COMPLETED
            total_purchases = Decimal(str(session.query(func.sum(Purchase.total_amount)).filter(
                Purchase.order_date >= start_dt,
                Purchase.order_date <= end_dt,
                Purchase.status.in_(['RECEIVED', 'PAID', 'PARTIAL', 'COMPLETED'])
            ).scalar() or 0))

            # Supplier Payments (actual cash paid to suppliers)
            from pos_app.models.database import PurchasePayment
            supplier_payments_count = session.query(func.count(PurchasePayment.id)).filter(
                PurchasePayment.payment_date >= start_dt,
                PurchasePayment.payment_date <= end_dt,
                PurchasePayment.status == 'COMPLETED'
            ).scalar() or 0
            total_supplier_payments = Decimal(str(session.query(func.sum(PurchasePayment.amount)).filter(
                PurchasePayment.payment_date >= start_dt,
                PurchasePayment.payment_date <= end_dt,
                PurchasePayment.status == 'COMPLETED'
            ).scalar() or 0))

            print(f"[DASHBOARD] Supplier Payments count: {supplier_payments_count}")
            print(f"[DASHBOARD] Total Supplier Payments: Rs {total_supplier_payments:,.2f}")

            # Other Expenses
            total_expenses = Decimal(str(session.query(func.sum(Expense.amount)).filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt
            ).scalar() or 0))

            print(f"[DASHBOARD] Purchases: Rs {total_purchases:,.2f}")
            print(f"[DASHBOARD] Supplier Payments: Rs {total_supplier_payments:,.2f}")
            print(f"[DASHBOARD] Expenses: Rs {total_expenses:,.2f}")

            # --- COGS, computed in BULK (this is the freeze fix) ---
            # The old sale_cost() ran a separate PurchaseItem query for EVERY item of
            # EVERY sale in the period. For "This Year" that was 100,000+ individual
            # queries on the UI thread -> the dashboard froze until force-closed.
            #
            # Now: 1 query for all sale items in the period + 1 window-function query
            # for the latest purchase unit_cost per product (as of period end) + 1 query
            # for product.purchase_price fallbacks. Then a plain Python loop, no per-item SQL.
            #
            # Semantic note: cost is now "latest purchase cost as of period END" rather than
            # "latest cost as of each sale's date". For a dashboard gross-profit estimate this
            # is an acceptable approximation and removes the O(sales x items) query storm.
            sale_item_rows = session.query(
                SaleItem.product_id, SaleItem.quantity, SaleItem.unit_price, Sale.is_refund
            ).join(Sale, SaleItem.sale_id == Sale.id).filter(
                *date_filter, status_ok
            ).all()

            # Latest purchase unit_cost per product as of end_dt (window function, one query)
            rn = func.row_number().over(
                partition_by=PurchaseItem.product_id,
                order_by=[Purchase.order_date.desc(), PurchaseItem.id.desc()]
            ).label('rn')
            cost_subq = session.query(
                PurchaseItem.product_id.label('pid'),
                PurchaseItem.unit_cost.label('unit_cost'),
                rn,
            ).join(Purchase, PurchaseItem.purchase_id == Purchase.id).filter(
                Purchase.order_date <= end_dt,
                Purchase.status.in_(['RECEIVED', 'PAID', 'PARTIAL', 'COMPLETED'])
            ).subquery()
            cost_map = {
                row.pid: Decimal(str(row.unit_cost or 0))
                for row in session.query(cost_subq.c.pid, cost_subq.c.unit_cost).filter(cost_subq.c.rn == 1).all()
            }

            # product.purchase_price fallback for products with no usable purchase history
            product_ids = {r[0] for r in sale_item_rows if r[0] is not None}
            pp_map = {}
            if product_ids:
                pp_map = {
                    pid: Decimal(str(pp or 0))
                    for pid, pp in session.query(Product.id, Product.purchase_price)
                        .filter(Product.id.in_(product_ids)).all()
                }

            def _cogs(rows):
                total = Decimal('0')
                for product_id, quantity, unit_price, _is_refund in rows:
                    qty = Decimal(str(quantity or 0))
                    sale_unit_price = Decimal(str(unit_price or 0))
                    product_cost = cost_map.get(product_id, Decimal('0'))
                    if product_cost <= 0:
                        product_cost = pp_map.get(product_id, Decimal('0'))
                    # Sanity guard: if purchase cost is wildly higher than the selling unit
                    # price (units mismatch / bad data), fall back to purchase_price, else cap.
                    if sale_unit_price > 0 and product_cost > (sale_unit_price * Decimal('10')):
                        fallback_cost = pp_map.get(product_id, Decimal('0'))
                        if fallback_cost > 0 and fallback_cost <= (sale_unit_price * Decimal('10')):
                            product_cost = fallback_cost
                        else:
                            product_cost = sale_unit_price
                    total += qty * product_cost
                return total

            total_cogs = _cogs([r for r in sale_item_rows if not r[3]]) - _cogs([r for r in sale_item_rows if r[3]])
            gross_profit = total_sales - total_cogs
            
            # Low stock
            low_stock = session.query(Product).filter(
                Product.stock_level <= Product.reorder_level
            ).count()
            
            print(f"[DASHBOARD] Cost of Goods Sold: Rs {total_cogs:,.2f}")
            print(f"[DASHBOARD] Gross Profit: Rs {gross_profit:,.2f}")
            
            # Customer Payments (actual money received from customers)
            total_customer_payments = Decimal(str(session.query(func.sum(Payment.amount)).filter(
                Payment.payment_date >= start_dt,
                Payment.payment_date <= end_dt,
                Payment.status == 'COMPLETED',
                Payment.customer_id != None
            ).scalar() or 0))
            
            print(f"[DASHBOARD] Customer Payments: Rs {total_customer_payments:,.2f}")

            cash_received = total_paid_on_sales + total_customer_payments
            net_cash = cash_received - total_supplier_payments - total_expenses

            print(f"[DASHBOARD] Paid on Sales: Rs {total_paid_on_sales:,.2f}")
            print(f"[DASHBOARD] Cash Received: Rs {cash_received:,.2f}")
            print(f"[DASHBOARD] Net Cash: Rs {net_cash:,.2f}")

            net_profit = gross_profit - total_expenses

            print(f"[DASHBOARD] Net Profit: Rs {net_profit:,.2f}")
            
            # Sales are invoice value. Customer payments are separate credit collections,
            # so they are not added into gross profit.
            cards_data = [
                ("Total Sales", f"Rs {total_sales:,.2f}", "#10b981", "💰"),
                ("Purchases", f"Rs {total_purchases:,.2f}", "#f59e0b", "🛒"),
                ("Supplier Payments", f"Rs {total_supplier_payments:,.2f}", "#f97316", "💳"),
                ("Expenses", f"Rs {total_expenses:,.2f}", "#ef4444", "💸"),
                ("Customer Payments", f"Rs {total_customer_payments:,.2f}", "#06b6d4", "💵"),
                ("Net Profit", f"Rs {net_profit:,.2f}", "#8b5cf6", "🧾"),
            ]
            
            for i, (title, value, color, icon) in enumerate(cards_data):
                card, value_label = self.create_stat_card(title, value, color, icon)
                row = i // 4
                col = i % 4
                layout.addWidget(card, row, col)
    
    def load_summary(self):
        """Load daily summary receipt"""
        with get_db_session() as session:
            self.summary_table.setRowCount(0)
            
            start_dt = datetime.combine(self.start_date, datetime.min.time())
            end_dt = datetime.combine(self.end_date, datetime.max.time())
            
            total_in = Decimal(0)
            total_out = Decimal(0)
            
            from sqlalchemy import or_

            # Sales / Refunds. Keep this aligned with the stats cards.
            sales = session.query(Sale).filter(
                Sale.sale_date >= start_dt,
                Sale.sale_date <= end_dt,
                or_(Sale.status == 'COMPLETED', Sale.status == 'REFUNDED', Sale.status == None)
            ).all()
            
            for sale in sales:
                # Get product names
                product_names = []
                total_qty = 0
                for item in sale.items:
                    if item.product:
                        product_names.append(item.product.name)
                    total_qty += item.quantity
                
                description = ", ".join(product_names[:3])  # Show first 3
                if len(product_names) > 3:
                    description += f" +{len(product_names)-3} more"
                
                row = self.summary_table.rowCount()
                self.summary_table.insertRow(row)

                is_refund = False
                try:
                    is_refund = bool(getattr(sale, 'is_refund', False))
                except Exception:
                    is_refund = False

                if is_refund:
                    self.summary_table.setItem(row, 0, QTableWidgetItem("↩ REFUND"))
                    self.summary_table.setItem(row, 1, QTableWidgetItem(description or f"Refund Invoice #{sale.invoice_number}"))
                else:
                    self.summary_table.setItem(row, 0, QTableWidgetItem("💰 SALE"))
                    self.summary_table.setItem(row, 1, QTableWidgetItem(description or f"Invoice #{sale.invoice_number}"))
                self.summary_table.setItem(row, 2, QTableWidgetItem(str(len(sale.items))))
                self.summary_table.setItem(row, 3, QTableWidgetItem(str(total_qty)))

                # Money direction:
                # - SALE: money IN (positive)
                # - REFUND: money OUT (negative display, counted into total_out)
                try:
                    sale_total = Decimal(str(getattr(sale, 'total_amount', 0) or 0))
                except Exception:
                    sale_total = Decimal(0)

                if is_refund:
                    amount_item = QTableWidgetItem(f"Rs {-abs(sale_total):,.2f}")
                    try:
                        amount_item.setForeground(Qt.red)
                    except Exception:
                        pass
                    total_out += abs(sale_total)
                else:
                    amount_item = QTableWidgetItem(f"Rs {sale_total:,.2f}")
                    try:
                        amount_item.setForeground(Qt.green)
                    except Exception:
                        pass
                    total_in += sale_total
                self.summary_table.setItem(row, 4, amount_item)
            
            # Purchases (Money OUT). Keep this aligned with the stats cards.
            purchases = session.query(Purchase).filter(
                Purchase.order_date >= start_dt,
                Purchase.order_date <= end_dt,
                Purchase.status.in_(['RECEIVED', 'COMPLETED'])
            ).all()
            
            for purchase in purchases:
                # Get supplier name and products
                supplier_name = "Unknown"
                if purchase.supplier:
                    supplier_name = purchase.supplier.name
                
                product_names = []
                total_qty = 0
                for item in purchase.items:
                    if item.product:
                        product_names.append(item.product.name)
                    total_qty += item.quantity
                
                description = f"{supplier_name}: " + ", ".join(product_names[:2])
                if len(product_names) > 2:
                    description += f" +{len(product_names)-2} more"
                
                row = self.summary_table.rowCount()
                self.summary_table.insertRow(row)
                
                self.summary_table.setItem(row, 0, QTableWidgetItem("🛒 PURCHASE"))
                self.summary_table.setItem(row, 1, QTableWidgetItem(description))
                self.summary_table.setItem(row, 2, QTableWidgetItem(str(len(purchase.items))))
                self.summary_table.setItem(row, 3, QTableWidgetItem(str(total_qty)))
                
                amount_item = QTableWidgetItem(f"Rs {Decimal(str(purchase.total_amount)):,.2f}")
                amount_item.setForeground(Qt.red)
                self.summary_table.setItem(row, 4, amount_item)
                
                total_out += Decimal(str(purchase.total_amount))
            
            # Expenses (Money OUT)
            expenses = session.query(Expense).filter(
                Expense.expense_date >= start_dt,
                Expense.expense_date <= end_dt
            ).all()
            
            for expense in expenses:
                row = self.summary_table.rowCount()
                self.summary_table.insertRow(row)
                
                self.summary_table.setItem(row, 0, QTableWidgetItem("💸 EXPENSE"))
                self.summary_table.setItem(row, 1, QTableWidgetItem(expense.title or "Expense"))
                self.summary_table.setItem(row, 2, QTableWidgetItem("1"))
                self.summary_table.setItem(row, 3, QTableWidgetItem("1"))
                
                amount_item = QTableWidgetItem(f"Rs {Decimal(str(expense.amount)):,.2f}")
                amount_item.setForeground(Qt.red)
                self.summary_table.setItem(row, 4, amount_item)
                
                total_out += Decimal(str(expense.amount))
            
            # Update totals
            self.total_in_label.setText(f"Total IN: Rs {total_in:,.2f}")
            self.total_out_label.setText(f"Total OUT: Rs {total_out:,.2f}")
            
            net = total_in - total_out
            self.net_total_label.setText(f"NET: Rs {net:,.2f}")
            
            if net > 0:
                self.net_total_label.setStyleSheet("font-size: 18px; color: #10b981; font-weight: bold;")
            elif net < 0:
                self.net_total_label.setStyleSheet("font-size: 18px; color: #ef4444; font-weight: bold;")
            else:
                self.net_total_label.setStyleSheet("font-size: 18px; color: #94a3b8; font-weight: bold;")
    
    def open_register(self):
        """Open cash register"""
        dialog = CashRegisterDialog(mode='open', parent=self)
        if dialog.exec():
            data = dialog.get_data()
            
            with get_db_session() as session:
                new_session = CashDrawerSession(
                    opening_balance=data['opening_balance'],
                    opened_at=datetime.now(),
                    status='OPEN',
                    notes=data['notes'],
                    opened_by='admin'  # TODO: Get from current user
                )
                session.add(new_session)
                session.commit()
                
                QMessageBox.information(self, "Success", "Cash register opened successfully!")
                self.load_data()
    
    def close_register(self):
        """Close cash register"""
        if not self.current_session:
            QMessageBox.warning(self, "Error", "No active cash register session!")
            return
        
            # Calculate expected balance
        with get_db_session() as session:
            movements = session.query(CashMovement).filter(
                CashMovement.session_id == self.current_session.id
            ).all()
            
            expected = Decimal(str(self.current_session.opening_balance or 0))
            for mov in movements:
                amount = Decimal(str(mov.amount or 0))
                if mov.movement_type in ['SALE', 'DEPOSIT']:
                    expected += amount
                else:
                    expected -= amount
            
            session_data = {
                'opened_at': self.current_session.opened_at,
                'opening_balance': float(self.current_session.opening_balance),
                'expected_balance': expected
            }
        
        dialog = CashRegisterCloseDialog(session_data=session_data, parent=self)
        if dialog.exec():
            data = dialog.get_data()
            
            with get_db_session() as session:
                # Update session
                sess = session.query(CashDrawerSession).get(self.current_session.id)
                sess.closing_balance = data['closing_balance']
                sess.expected_balance = data['expected_balance']
                sess.variance = data['variance']
                sess.closed_at = datetime.now()
                sess.status = 'CLOSED'
                sess.notes = (sess.notes or '') + '\n' + (data['notes'] or '')
                sess.closed_by = 'admin'  # TODO: Get from current user
                
                session.commit()
                
                # Show variance message
                if data['variance'] != 0:
                    msg = f"Cash register closed!\n\nVariance: Rs {data['variance']:,.2f}"
                    if data['variance'] > 0:
                        msg += "\n(Over)"
                    else:
                        msg += "\n(Short)"
                    QMessageBox.information(self, "Register Closed", msg)
                else:
                    QMessageBox.information(self, "Success", "Cash register closed successfully!\n\nNo variance - Perfect!")
                
                self.load_data()

    def create_activity_tracking_section(self):
        """Create activity tracking section with recent transactions"""
        widget = QWidget()
        widget.setStyleSheet("""
            QWidget {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 rgba(59, 130, 246, 0.1), stop:1 rgba(16, 185, 129, 0.1));
                border: 1px solid rgba(255,255,255,0.1);
                border-radius: 15px;
                padding: 20px;
                margin: 10px 0;
            }
        """)
        
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # Section title
        title = QLabel("📊 Recent Activity")
        title.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #1e293b;
                margin-bottom: 15px;
                padding: 10px 0;
            }
        """)
        layout.addWidget(title)
        
        # Activity table
        self.activity_table = QTableWidget()
        self.activity_table.setColumnCount(6)
        self.activity_table.setHorizontalHeaderLabels([
            "Time", "Type", "Description", "Amount", "Status", "Details"
        ])
        
        self.activity_table.setStyleSheet("""
            QTableWidget {
                background: Qt.white;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                gridline-color: #e2e8f0;
                font-size: 14px;
                color: #1e293b;
                selection-background-color: #fef3c7;
                min-height: 300px;
            }
            QTableWidget::item {
                padding: 12px 16px;
                border-bottom: 1px solid #e2e8f0;
                color: #1e293b;
                background: Qt.white;
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
                padding: 16px;
                border: none;
                border-bottom: 2px solid #e2e8f0;
            }
        """)
        
        # Configure table
        self.activity_table.verticalHeader().setVisible(False)
        self.activity_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.activity_table.setAlternatingRowColors(True)
        
        header = self.activity_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)    # Time
        header.resizeSection(0, 120)
        header.setSectionResizeMode(1, QHeaderView.Fixed)    # Type
        header.resizeSection(1, 100)
        header.setSectionResizeMode(2, QHeaderView.Stretch)  # Description
        header.setSectionResizeMode(3, QHeaderView.Fixed)    # Amount
        header.resizeSection(3, 120)
        header.setSectionResizeMode(4, QHeaderView.Fixed)    # Status
        header.resizeSection(4, 100)
        header.setSectionResizeMode(5, QHeaderView.Fixed)    # Details
        header.resizeSection(5, 80)
        
        layout.addWidget(self.activity_table)
        
        # Search and filter controls
        controls_layout = QHBoxLayout()
        
        # Search input
        try:
            from PySide6.QtWidgets import QLineEdit
        except ImportError:
            from PyQt6.QtWidgets import QLineEdit
        self.activity_search = QLineEdit()
        self.activity_search.setPlaceholderText("Search activities...")
        self.activity_search.setStyleSheet("""
            QLineEdit {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                background: Qt.white;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #3b82f6;
            }
        """)
        self.activity_search.textChanged.connect(self.filter_activities)
        
        # Type filter
        self.activity_type_filter = QComboBox()
        self.activity_type_filter.addItems(["All Types", "Sales", "Purchases", "Payments", "Expenses"])
        self.activity_type_filter.setStyleSheet("""
            QComboBox {
                border: 2px solid #e2e8f0;
                border-radius: 8px;
                padding: 8px 12px;
                font-size: 14px;
                background: Qt.white;
                color: #1e293b;
                min-width: 120px;
            }
        """)
        self.activity_type_filter.currentTextChanged.connect(self.filter_activities)
        
        # Refresh button
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setStyleSheet("""
            QPushButton {
                background: #10b981;
                color: Qt.white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 14px;
                font-weight: 600;
            }
            QPushButton:hover {
                background: #059669;
            }
        """)
        refresh_btn.clicked.connect(self.load_recent_activities)
        
        controls_layout.addWidget(QLabel("Search:"))
        controls_layout.addWidget(self.activity_search)
        controls_layout.addWidget(QLabel("Type:"))
        controls_layout.addWidget(self.activity_type_filter)
        controls_layout.addWidget(refresh_btn)
        controls_layout.addStretch()
        
        layout.addLayout(controls_layout)
        
        return widget

    def load_recent_activities(self):
        """Load recent activities from database"""
        try:
            activities = []
            
            with get_db_session() as session:
                # Get recent sales
                sales = session.query(Sale).order_by(Sale.sale_date.desc()).limit(10).all()
                for sale in sales:
                    customer_name = "Walk-in"
                    if sale.customer_id:
                        customer = session.query(Customer).get(sale.customer_id)
                        if customer:
                            customer_name = customer.name
                    
                    activities.append({
                        'time': sale.sale_date.strftime("%H:%M") if sale.sale_date else "",
                        'type': 'Sale',
                        'description': f"Sale to {customer_name}",
                        'amount': f"Rs {sale.total_amount:,.2f}" if sale.total_amount else "Rs 0.00",
                        'status': 'Completed',
                        'details_data': sale
                    })
                
                # Get recent purchases
                purchases = session.query(Purchase).order_by(Purchase.order_date.desc()).limit(5).all()
                for purchase in purchases:
                    supplier_name = "Unknown"
                    if purchase.supplier_id:
                        supplier = session.query(Supplier).get(purchase.supplier_id)
                        if supplier:
                            supplier_name = supplier.name
                    
                    activities.append({
                        'time': purchase.order_date.strftime("%H:%M") if purchase.order_date else "",
                        'type': 'Purchase',
                        'description': f"Purchase from {supplier_name}",
                        'amount': f"Rs {purchase.total_amount:,.2f}" if purchase.total_amount else "Rs 0.00",
                        'status': purchase.status or 'Pending',
                        'details_data': purchase
                    })
            
            # Sort by time (most recent first)
            activities.sort(key=lambda x: x['time'], reverse=True)
            
            # Update table
            self.activity_table.setRowCount(len(activities))
            for i, activity in enumerate(activities):
                self.activity_table.setItem(i, 0, QTableWidgetItem(activity['time']))
                self.activity_table.setItem(i, 1, QTableWidgetItem(activity['type']))
                self.activity_table.setItem(i, 2, QTableWidgetItem(activity['description']))
                self.activity_table.setItem(i, 3, QTableWidgetItem(activity['amount']))
                self.activity_table.setItem(i, 4, QTableWidgetItem(activity['status']))
                
                # Details button
                details_btn = QPushButton("👁️")
                details_btn.setStyleSheet("""
                    QPushButton {
                        background: #3b82f6;
                        color: Qt.white;
                        border: none;
                        border-radius: 4px;
                        padding: 4px 8px;
                        font-size: 12px;
                    }
                    QPushButton:hover {
                        background: #2563eb;
                    }
                """)
                details_btn.clicked.connect(lambda checked, data=activity['details_data']: self.show_activity_details(data))
                self.activity_table.setCellWidget(i, 5, details_btn)
                
        except Exception as e:
            print(f"Error loading activities: {e}")

    def filter_activities(self):
        """Filter activities based on search and type"""
        search_text = self.activity_search.text().lower()
        type_filter = self.activity_type_filter.currentText()
        
        for i in range(self.activity_table.rowCount()):
            show_row = True
            
            # Check search text
            if search_text:
                description = self.activity_table.item(i, 2).text().lower()
                if search_text not in description:
                    show_row = False
            
            # Check type filter
            if type_filter != "All Types":
                row_type = self.activity_table.item(i, 1).text()
                if type_filter.rstrip('s') not in row_type:  # Remove 's' for matching
                    show_row = False
            
            self.activity_table.setRowHidden(i, not show_row)

    def show_activity_details(self, data):
        """Show detailed information about an activity"""
        from PySide6.QtWidgets import QDialog, QTextEdit
        
        dialog = QDialog(self)
        dialog.setWindowTitle("Activity Details")
        dialog.setModal(True)
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)
        
        details_text = QTextEdit()
        details_text.setReadOnly(True)
        details_text.setStyleSheet("""
            QTextEdit {
                background: Qt.white;
                color: #1e293b;
                font-family: 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #e2e8f0;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        
        # Format details based on data type
        if hasattr(data, 'total_amount'):  # Sale or Purchase
            if hasattr(data, 'sale_date'):  # Sale
                content = f"""
SALE DETAILS
============
ID: {data.id}
Date: {data.sale_date}
Customer ID: {data.customer_id or 'Walk-in'}
Total Amount: Rs {data.total_amount:,.2f}
Payment Method: {data.payment_method or 'Cash'}
Status: Completed
                """
            else:  # Purchase
                content = f"""
PURCHASE DETAILS
================
ID: {data.id}
Date: {data.order_date}
Supplier ID: {data.supplier_id}
Total Amount: Rs {data.total_amount:,.2f}
Status: {data.status}
Notes: {data.notes or 'None'}
                """
        else:  # Payment
            content = f"""
PAYMENT DETAILS
===============
ID: {data.id}
Date: {data.payment_date}
Customer ID: {data.customer_id or 'Walk-in'}
Amount: Rs {data.amount:,.2f}
Method: {data.payment_method or 'Cash'}
Status: {data.status or 'Completed'}
Reference: {data.reference or 'None'}
            """
        
        details_text.setPlainText(content)
        layout.addWidget(details_text)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)
        
        dialog.exec()

    def load_data(self):
        """Load all dashboard data including activities"""
        # Load existing data
        self.load_cash_register_status()
        self.load_stats()
        self.load_summary()
        
        # Load new activity data
        if hasattr(self, 'activity_table'):
            self.load_recent_activities()
