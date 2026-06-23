try:
    from PySide6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QFrame, QGridLayout, QPushButton, QComboBox
    )
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtGui import QShortcut, QKeySequence
except ImportError:
    from PyQt6.QtWidgets import (
        QWidget, QVBoxLayout, QHBoxLayout, QLabel,
        QFrame, QGridLayout, QPushButton, QComboBox
    )
    from PyQt6.QtCore import Qt, pyqtSignal as Signal
    from PyQt6.QtGui import QShortcut, QKeySequence
from datetime import datetime, timedelta

class DashboardWidget(QWidget):
    # Signals for quick actions
    action_new_sale = Signal()
    action_add_product = Signal()
    action_add_customer = Signal()
    action_generate_report = Signal()
    action_view_low_stock = Signal()
    def __init__(self, controllers):
        super().__init__()
        self.controllers = controllers
        self.current_period = 'today'  # Default to today
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # Header with time period selector
        header_layout = QHBoxLayout()
        header = QLabel("📊 Dashboard")
        header.setProperty('role', 'heading')
        header.setStyleSheet("font-size: 28px; font-weight: bold; color: #f8fafc; margin-bottom: 20px;")
        header_layout.addWidget(header)
        
        # Time period selector
        header_layout.addStretch()
        period_label = QLabel("Period:")
        period_label.setStyleSheet("font-size: 14px; color: #94a3b8;")
        header_layout.addWidget(period_label)
        
        self.period_selector = QComboBox()
        self.period_selector.addItems(["Today", "Yesterday", "This Month", "This Year"])
        self.period_selector.setMinimumWidth(150)
        self.period_selector.currentTextChanged.connect(self.on_period_changed)
        header_layout.addWidget(self.period_selector)
        
        layout.addLayout(header_layout)

        # Keyboard shortcut (F5) for refresh
        try:
            sc = QShortcut(QKeySequence("F5"), self)
        except Exception:
            pass

        # Stats Grid
        stats_grid = QGridLayout()
        stats_grid.setSpacing(20)

        # fetch metrics if available
        metrics = self.load_metrics_for_period('today')

        # Store metric labels for dynamic updates
        self.sales_label = QLabel()
        self.revenue_label = QLabel()
        
        stats_cards = [
            ("Sales (Period)", f"Rs {metrics.get('sales', 0.0):,.2f}"),
            ("Revenue (Period)", f"Rs {metrics.get('revenue', 0.0):,.2f}"),
            ("Low Stock Items", str(metrics.get('low_stock', 0))),
            ("Active Customers", str(metrics.get('active_customers', 0)))
        ]

        for i, (title, value) in enumerate(stats_cards):
            card = self.create_stat_card(title, value)
            stats_grid.addWidget(card, i // 2, i % 2)

        # keep reference to stat cards for refresh
        self._stat_grid = stats_grid
        self._stat_cards = stats_cards

        layout.addLayout(stats_grid)

        # Quick Actions
        actions_label = QLabel("Quick Actions")
        actions_label.setStyleSheet("font-size: 18px; font-weight: bold; margin-top: 20px; color: #f8fafc;")
        layout.addWidget(actions_label)

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(12)
        quick_actions = [
            ("💰 New Sale", "Qt.green"),
            ("📦 Add Product", "Qt.blue"),
            ("👥 Add Customer", "purple"),
            ("📊 Generate Report", "orange"),
            ("⚠️ View Low Stock", "Qt.red"),
        ]

        # Create real buttons that pop on dark background
        for title, accent in quick_actions:
            btn = QPushButton(title)
            try:
                btn.setProperty("accent", accent)
            except Exception:
                pass
            btn.setMinimumHeight(44)
            btn.setMinimumWidth(140)
            btn.setCursor(Qt.PointingHandCursor)
            # Connect
            t = title.lower()
            if "new sale" in t:
                btn.clicked.connect(self.action_new_sale.emit)
            elif "add product" in t:
                btn.clicked.connect(self.action_add_product.emit)
            elif "add customer" in t:
                btn.clicked.connect(self.action_add_customer.emit)
            elif "generate report" in t:
                btn.clicked.connect(self.action_generate_report.emit)
            elif "low stock" in t:
                btn.clicked.connect(self.action_view_low_stock.emit)
            actions_layout.addWidget(btn)

        layout.addLayout(actions_layout)

        # Additional financial summary
        finance_grid = QGridLayout()
        finance_grid.setSpacing(12)
        finance_cards = [
            ("Outstanding Purchases", f"Rs {metrics.get('outstanding_purchases', 0.0):,.2f}"),
            ("Total Expenses", f"Rs {metrics.get('total_expenses', 0.0):,.2f}")
        ]
        for i, (title, value) in enumerate(finance_cards):
            card = self.create_stat_card(title, value)
            finance_grid.addWidget(card, 0, i)
        layout.addLayout(finance_grid)
        layout.addStretch()

    def create_stat_card(self, title, value):
        card = QFrame()
        card.setStyleSheet("""
            QFrame {
                background-color: #0b1220;
                border-radius: 12px;
                padding: 20px;
                border: 1px solid #1f2937;
            }
        """)
        
        layout = QVBoxLayout(card)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #9ca3af; font-size: 13px; font-weight: 500;")
        title_label.setWordWrap(False)

        value_label = QLabel(value)
        value_label.setStyleSheet("color: #60a5fa; font-size: 20px; font-weight: 600;")
        value_label.setWordWrap(False)
        value_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        layout.addWidget(title_label)
        layout.addWidget(value_label)
        
        return card

    def create_action_card(self, title):
        # Legacy method retained for compatibility; now unused
        btn = QPushButton(title)
        btn.setMinimumHeight(44)
        return btn

    def load_metrics_for_period(self, period):
        """Load metrics for specific time period.

        Uses SQL aggregation (func.sum / func.count) so the database does the
        math instead of loading every Sale row into memory. Without this, picking
        "This Year" pulled thousands of ORM rows onto the UI thread and froze the app.
        """
        try:
            from pos_app.models.database import Sale, Customer, Product
            from sqlalchemy import func, or_

            # Get controller session
            controller = None
            if 'inventory' in self.controllers:
                controller = self.controllers['inventory']
            elif 'reports' in self.controllers:
                controller = self.controllers['reports']

            if not controller or not hasattr(controller, 'session'):
                return {'sales': 0.0, 'revenue': 0.0, 'low_stock': 0, 'active_customers': 0}

            session = controller.session

            # Calculate date range based on period
            now = datetime.now()
            if period == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            elif period == 'yesterday':
                yesterday = now - timedelta(days=1)
                start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = yesterday.replace(hour=23, minute=59, second=59)
            elif period == 'month':
                start_date = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            elif period == 'year':
                start_date = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
                end_date = now
            else:
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                end_date = now

            date_filter = (Sale.sale_date >= start_date, Sale.sale_date <= end_date)

            # NET sales = sum(normal sales) - sum(abs(refund totals)), computed in SQL
            normal_total = session.query(func.sum(Sale.total_amount)).filter(
                *date_filter, Sale.is_refund != True
            ).scalar() or 0
            refund_total = session.query(func.sum(func.abs(Sale.total_amount))).filter(
                *date_filter, Sale.is_refund == True
            ).scalar() or 0
            total_sales = float(normal_total) - float(refund_total)

            # Revenue from completed sales only (status COMPLETED or NULL)
            completed_normal = session.query(func.sum(Sale.total_amount)).filter(
                *date_filter, Sale.is_refund != True,
                or_(Sale.status.is_(None), Sale.status == 'COMPLETED')
            ).scalar() or 0
            completed_refunds = session.query(func.sum(func.abs(Sale.total_amount))).filter(
                *date_filter, Sale.is_refund == True,
                or_(Sale.status.is_(None), Sale.status.in_(['COMPLETED', 'REFUNDED']))
            ).scalar() or 0
            total_revenue = float(completed_normal) - float(completed_refunds)

            # Low stock products
            low_stock = session.query(Product).filter(
                Product.stock_level <= Product.reorder_level
            ).count()

            # Active customers
            active_customers = session.query(Customer).filter(
                Customer.is_active == True
            ).count()

            return {
                'sales': total_sales,
                'revenue': total_revenue,
                'low_stock': low_stock,
                'active_customers': active_customers
            }
        except Exception as e:
            print(f"Error loading metrics: {e}")
            return {'sales': 0.0, 'revenue': 0.0, 'low_stock': 0, 'active_customers': 0}
    
    def on_period_changed(self, period_text):
        """Handle period selector change"""
        period_map = {
            'Today': 'today',
            'Yesterday': 'yesterday',
            'This Month': 'month',
            'This Year': 'year'
        }
        period = period_map.get(period_text, 'today')
        self.current_period = period
        
        # Reload metrics
        metrics = self.load_metrics_for_period(period)
        
        # Update stat cards
        values = [
            f"Rs {metrics.get('sales', 0.0):,.2f}",
            f"Rs {metrics.get('revenue', 0.0):,.2f}",
            str(metrics.get('low_stock', 0)),
            str(metrics.get('active_customers', 0))
        ]
        
        # Update stat card labels
        for idx in range(self._stat_grid.count()):
            item = self._stat_grid.itemAt(idx)
            widget = item.widget()
            if widget:
                try:
                    val_label = widget.findChildren(QLabel)[1]
                    val_label.setText(values[idx])
                except Exception:
                    pass
    
    def refresh_metrics(self):
        """Refresh metrics for current period"""
        self.on_period_changed(self.period_selector.currentText())
