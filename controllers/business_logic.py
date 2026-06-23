"""Business logic controller for POS operations"""
from decimal import Decimal
from datetime import datetime, time
from typing import List, Dict, Optional, Any
import logging

from pos_app.database.db_utils import get_db_session
from pos_app.models import (Product, Sale, SaleItem, Customer, Supplier, Expense, ExpenseSchedule,
                          Purchase, PurchaseItem, PurchasePayment, Payment)

logger = logging.getLogger(__name__)

class BusinessController:
    """Main business logic controller for POS operations"""
    
    def __init__(self, session=None):
        self.session = session or get_db_session()

    def _get_product_query(self, product_id: int, lock_for_update: bool = False):
        """Return a product query, locking the row when the backend supports it."""
        query = self.session.query(Product).filter_by(id=product_id)
        if lock_for_update:
            try:
                query = query.with_for_update()
            except Exception:
                pass
        return query

    def _aggregate_item_quantities(self, items: List[Dict[str, Any]]) -> Dict[int, Decimal]:
        """Aggregate per-product quantities to avoid duplicate-line oversells."""
        quantities: Dict[int, Decimal] = {}
        for item in items or []:
            product_id = item.get('product_id')
            if product_id is None:
                continue
            quantity = Decimal(str(item.get('quantity', 0) or 0))
            quantities[product_id] = quantities.get(product_id, Decimal('0')) + quantity
        return quantities
    
    def create_sale(self, customer_id: int, items: List[Dict[str, Any]], 
                   is_wholesale: bool = False, payment_method: str = 'Cash',
                   paid_amount: float = 0.0, is_refund: bool = False,
                   refund_of_sale_id: Optional[int] = None,
                   discount_amount: float = 0.0) -> Sale:
        """Create a new sale transaction"""
        try:
            logger.info(f"Creating sale: is_refund={is_refund}, customer_id={customer_id}, items_count={len(items)}")
            
            # Convert inputs to Decimal
            d_paid = Decimal(str(paid_amount or 0))
            d_discount = Decimal(str(discount_amount or 0))
            
            # Validate stock for sales (not refunds)
            if not is_refund:
                logger.info("Validating stock for sale (not refund)")
                stock_errors = self.validate_stock_availability(items, is_refund=False)
                if stock_errors:
                    logger.error(f"Stock validation failed: {stock_errors}")
                    raise ValueError(f"Stock issues: {', '.join(stock_errors)}")
            else:
                logger.info("Skipping stock validation for refund")
            
            # Calculate subtotal from items
            subtotal = Decimal('0')
            for item in items:
                quantity = Decimal(str(item['quantity']))
                unit_price = Decimal(str(item['unit_price']))
                subtotal += quantity * unit_price
            
            # Calculate total amount
            total_amount = subtotal - d_discount
            
            # Generate invoice number
            invoice_number = self._generate_invoice_number()
            
            # Create sale record
            sale = Sale(
                invoice_number=invoice_number,
                customer_id=customer_id,
                is_wholesale=is_wholesale,
                payment_method=payment_method,
                paid_amount=d_paid,
                discount_amount=d_discount,
                subtotal=subtotal,
                total_amount=total_amount,
                is_refund=is_refund,
                refund_of_sale_id=refund_of_sale_id
            )
            
            self.session.add(sale)
            self.session.flush()  # Get sale ID
            
            # Add sale items and update stock
            for item in items:
                product_id = item['product_id']
                quantity = Decimal(str(item['quantity']))
                unit_price = Decimal(str(item['unit_price']))
                
                # Get product
                product = self._get_product_query(product_id, lock_for_update=not is_refund).first()
                if not product:
                    raise ValueError(f"Product {product_id} not found")
                
                logger.info(f"Processing item: product_id={product_id}, quantity={quantity}, current_stock={product.stock_level}")
                
                # Create sale item
                sale_item = SaleItem(
                    sale_id=sale.id,
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                    total=quantity * unit_price
                )
                self.session.add(sale_item)
                
                # Update stock
                if is_refund:
                    # Refunds increase stock
                    old_stock = Decimal(str(product.stock_level or 0))
                    new_stock = old_stock + quantity
                    product.stock_level = new_stock
                    logger.info(f"Refund: Increased stock for product {product_id} from {old_stock} to {new_stock}")
                else:
                    # Sales decrease stock
                    old_stock = Decimal(str(product.stock_level or 0))
                    if old_stock < quantity:
                        raise ValueError(
                            f"Insufficient stock for {product.name}: {old_stock} available, {quantity} requested"
                        )
                    new_stock = old_stock - quantity
                    product.stock_level = new_stock
                    logger.info(f"Sale: Decreased stock for product {product_id} from {old_stock} to {new_stock}")
            
            # Update customer credit balance
            if customer_id:
                customer = self.session.query(Customer).filter_by(id=customer_id).first()
                if customer:
                    logger.info(f"Customer credit update: is_refund={is_refund}, customer_id={customer_id}, customer_name={customer.name}, customer_type={customer.type}, current_credit={customer.current_credit}")
                    
                    if not is_refund:
                        # For sales: increase credit if customer owes money
                        credit_amount = total_amount - d_paid
                        logger.info(f"Sale processing: subtotal={subtotal}, discount={d_discount}, total_amount={total_amount}, paid_amount={d_paid}, credit_amount={credit_amount}, payment_method={payment_method}")
                        
                        # Debug: Log the decision logic
                        owes_money = credit_amount > 0
                        is_credit_payment = payment_method.upper() == 'CREDIT'
                        is_wholesale = customer.type.upper() == 'WHOLESALE'
                        is_retail = customer.type.upper() == 'RETAIL'
                        
                        logger.info(f"DEBUG: Credit decision - owes_money={owes_money}, is_credit_payment={is_credit_payment}, is_wholesale={is_wholesale}, is_retail={is_retail}")
                        
                        # Update credit balance if customer owes money
                        # Allow both wholesale and retail customers to get credit for credit sales
                        if credit_amount > 0 and is_credit_payment:
                            # Ensure customer.current_credit is a Decimal
                            if not isinstance(customer.current_credit, Decimal):
                                customer.current_credit = Decimal(str(customer.current_credit or 0))
                            old_credit = customer.current_credit
                            customer.current_credit += credit_amount
                            logger.info(f"SALE: Increased customer {customer_id} ({customer.name}) credit from {old_credit} to {customer.current_credit} (credit_amount: {credit_amount})")
                        else:
                            logger.info(f"SALE: No credit update needed - owes_money={owes_money}, is_credit_payment={is_credit_payment}, is_wholesale={is_wholesale}, is_retail={is_retail}, payment_method={payment_method}")
                    else:
                        # For refunds: handle customer balance properly
                        logger.info(f"Refund processing: refund_of_sale_id={refund_of_sale_id}, total_amount={total_amount}")
                        
                        # Ensure customer.current_credit is a Decimal
                        if not isinstance(customer.current_credit, Decimal):
                            customer.current_credit = Decimal(str(customer.current_credit or 0))
                        
                        old_balance = customer.current_credit
                        refund_amount = Decimal(str(total_amount))
                        
                        # For refunds, we create negative balance (store credit) for customer
                        # This means customer can use this amount for future purchases
                        customer.current_credit -= refund_amount  # Subtract to create negative balance (store credit)
                        
                        logger.info(f"REFUND: Updated customer {customer_id} balance from {old_balance} to {customer.current_credit} (refund amount: {refund_amount})")
                        
                        # Additionally, if original sale was on credit, reduce that credit too
                        if refund_of_sale_id:
                            original_sale = self.session.query(Sale).filter_by(id=refund_of_sale_id).first()
                            if original_sale:
                                logger.info(f"Found original sale: total_amount={original_sale.total_amount}, paid_amount={original_sale.paid_amount}")
                                
                                # Calculate how much credit was used in original sale
                                original_credit_amount = original_sale.total_amount - original_sale.paid_amount
                                logger.info(f"Original credit amount: {original_credit_amount}")
                                
                                if original_credit_amount > 0:
                                    # Original sale was on credit, so refund should reduce that credit too
                                    refund_credit_reduction = min(refund_amount, original_credit_amount)
                                    logger.info(f"Refund credit reduction: {refund_credit_reduction}")
                                    
                                    # Reduce credit balance (customer owes less)
                                    customer.current_credit = max(customer.current_credit, Decimal('0'))  # Don't go below what we already set
                                    
                                    logger.info(f"REFUND: Final customer {customer_id} balance after credit reduction: {customer.current_credit}")
                                else:
                                    logger.info(f"REFUND: Original sale was cash sale, only store credit created")
                            else:
                                logger.warning(f"REFUND: Could not find original sale {refund_of_sale_id} for credit analysis")
                        else:
                            logger.warning(f"REFUND: No refund_of_sale_id provided, only store credit created")
            
            self.session.commit()
            logger.info(f"Created {'refund' if is_refund else 'sale'} {sale.id} with invoice {invoice_number}")
            return sale
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating sale: {e}")
            raise
    
    def _generate_invoice_number(self) -> str:
        """Generate a unique invoice number as simple sequential number"""
        try:
            # Get all sales with numeric invoice numbers and find the highest
            from sqlalchemy import func, cast, Integer
            from sqlalchemy.sql import text
            
            # Query to get the maximum numeric invoice number
            result = self.session.execute(
                text("SELECT MAX(CAST(invoice_number AS INTEGER)) as max_num FROM sales WHERE invoice_number ~ '^[0-9]+$'")
            )
            max_num = result.scalar()
            
            if max_num is not None:
                new_number = max_num + 1
            else:
                # Start with 2029 as requested
                new_number = 2029
            
            # Return as string
            return str(new_number)
            
        except Exception as e:
            logger.error(f"Error generating invoice number: {e}")
            # Fallback to timestamp-based number
            return str(int(datetime.now().timestamp()))
    
    def validate_stock_availability(self, items: List[Dict[str, Any]], 
                                  is_refund: bool = False) -> List[str]:
        """Validate stock availability for items"""
        errors = []
        aggregated_quantities = self._aggregate_item_quantities(items)

        for product_id, quantity in aggregated_quantities.items():
            
            product = self.session.query(Product).filter_by(id=product_id).first()
            if not product:
                errors.append(f"Product {product_id} not found")
                continue
            
            # Check stock availability (only for sales, not refunds)
            if not is_refund:
                # Handle negative stock levels - treat as zero available
                available_stock = product.stock_level if product.stock_level >= 0 else Decimal('0')
                if available_stock < quantity:
                    errors.append(f"Insufficient stock for {product.name}: {available_stock} available, {quantity} requested")
            # Note: For refunds, we don't check stock level here as negative stock is normal
            # Refund capacity is properly validated by get_remaining_refund_capacity method
        
        return errors
    
    def get_remaining_refund_capacity(self, sale_id: int) -> Dict[int, Decimal]:
        """Calculate remaining refund capacity for a sale"""
        # Get original sale items
        original_items = self.session.query(SaleItem).filter_by(sale_id=sale_id).all()
        
        # Get existing refunds for this sale
        refunded_items = self.session.query(SaleItem).join(Sale).filter(
            Sale.refund_of_sale_id == sale_id
        ).all()
        
        # Calculate remaining capacity
        remaining = {}
        for item in original_items:
            product_id = item.product_id
            original_qty = item.quantity
            
            # Sum refunded quantities for this product
            refunded_qty = sum(
                r_item.quantity for r_item in refunded_items 
                if r_item.product_id == product_id
            )
            
            remaining[product_id] = original_qty - refunded_qty
        
        return remaining
    
    def update_stock(self, product_id: int, qty: float, 
                    movement_type: str = 'OUT', location: Optional[str] = None,
                    commit: bool = True) -> bool:
        """Update product stock level"""
        try:
            qty_decimal = Decimal(str(qty))
            if qty_decimal <= 0:
                raise ValueError("Stock quantity must be positive")
            
            product = self._get_product_query(product_id, lock_for_update=True).first()
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            if movement_type == 'OUT':
                current_stock = Decimal(str(product.stock_level or 0))
                if current_stock < qty_decimal:
                    raise ValueError(
                        f"Insufficient stock for {product.name}: {current_stock} available, {qty_decimal} requested"
                    )
                new_stock = current_stock - qty_decimal
                product.stock_level = new_stock
            else:
                current_stock = Decimal(str(product.stock_level or 0))
                new_stock = current_stock + qty_decimal
                product.stock_level = new_stock
            
            if commit:
                self.session.commit()
            
            logger.info(f"Updated stock for product {product_id}: {movement_type} {qty}")
            return True
            
        except Exception as e:
            if commit:
                self.session.rollback()
            logger.error(f"Error updating stock: {e}")
            return False
    
    def get_all_products(self) -> List[Product]:
        """Get all products"""
        return self.session.query(Product).all()
    
    def get_all_customers(self) -> List[Customer]:
        """Get all customers"""
        return self.session.query(Customer).all()
    
    def list_suppliers(self) -> List[Supplier]:
        """Get all suppliers"""
        return self.session.query(Supplier).all()
    
    def list_expenses(self, start_date=None, end_date=None) -> List[Expense]:
        """Get all expenses, optionally filtered by date range.

        expense_date is a DateTime column, so a plain date comparison would
        treat the end date as midnight and exclude expenses recorded later on
        that same day. Convert to datetime boundaries to include the full day.
        """
        query = self.session.query(Expense)
        if start_date:
            start_dt = datetime.combine(start_date, time.min)
            query = query.filter(Expense.expense_date >= start_dt)
        if end_date:
            end_dt = datetime.combine(end_date, time.max)
            query = query.filter(Expense.expense_date <= end_dt)
        return query.all()
    
    def list_recurring_expenses(self) -> List[Expense]:
        """Get all recurring expenses (Expense objects with is_recurring=True)"""
        try:
            from pos_app.models.database import Expense
            return self.session.query(Expense).filter(Expense.is_recurring == True).all()
        except Exception as e:
            logger.error(f"Error listing recurring expenses: {e}")
            self.session.rollback()
            return []
    
    def get_product_by_barcode(self, barcode: str) -> Optional[Product]:
        """Get product by barcode"""
        return self.session.query(Product).filter_by(barcode=barcode).first()
    
    def search_products(self, query: str) -> List[Product]:
        """Search products by name or barcode"""
        return self.session.query(Product).filter(
            (Product.name.ilike(f'%{query}%')) |
            (Product.barcode.ilike(f'%{query}%'))
        ).all()
    
    def close(self):
        """Close database session"""
        if self.session:
            self.session.close()
    
    def add_product(self, name: str, description: str = None, sku: str = None, 
                   barcode: str = None, retail_price: float = 0.0, 
                   wholesale_price: float = 0.0, purchase_price: float = 0.0,
                   stock_level: int = 0, reorder_level: int = 0,
                   supplier_id: int = None, unit: str = None,
                   product_category_id: int = None, product_subcategory_id: int = None,
                   **kwargs) -> Product:
        """Add a new product to the database"""
        try:
            # Convert prices to Decimal
            d_retail = Decimal(str(retail_price))
            d_wholesale = Decimal(str(wholesale_price))
            d_purchase = Decimal(str(purchase_price))
            
            # Create product
            product = Product(
                name=name,
                description=description,
                sku=sku,
                barcode=barcode,
                retail_price=d_retail,
                wholesale_price=d_wholesale,
                purchase_price=d_purchase,
                stock_level=Decimal(str(stock_level)),
                reorder_level=reorder_level,
                supplier_id=supplier_id,
                unit=unit,
                product_category_id=product_category_id,
                product_subcategory_id=product_subcategory_id,
                # Handle any additional fields from kwargs
                **{k: v for k, v in kwargs.items() if hasattr(Product, k)}
            )
            
            self.session.add(product)
            self.session.commit()
            logger.info(f"Added product: {name}")
            return product
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding product: {e}")
            raise
    
    def get_products(self) -> List[Product]:
        """Get all products (alias for get_all_products)"""
        return self.get_all_products()
    
    def get_customers(self) -> List[Customer]:
        """Get all customers (alias for get_all_customers)"""
        return self.get_all_customers()
    
    def get_suppliers(self) -> List[Supplier]:
        """Get all suppliers (alias for list_suppliers)"""
        return self.list_suppliers()
    
    def add_supplier(self, name: str, contact: str = None, email: str = None, 
                    phone: str = None, address: str = None, **kwargs) -> Supplier:
        """Add a new supplier"""
        try:
            supplier = Supplier(
                name=name,
                contact=contact,
                email=email,
                phone_secondary=phone,  # Map phone parameter to phone_secondary field
                address=address,
                # Handle any additional fields from kwargs
                **{k: v for k, v in kwargs.items() if hasattr(Supplier, k)}
            )
            
            self.session.add(supplier)
            self.session.commit()
            logger.info(f"Added supplier: {name}")
            return supplier
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding supplier: {e}")
            raise
    
    def update_supplier(self, supplier_id: int, **kwargs) -> Supplier:
        """Update an existing supplier"""
        try:
            supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
            if not supplier:
                raise ValueError(f"Supplier {supplier_id} not found")
            
            for key, value in kwargs.items():
                if hasattr(supplier, key):
                    setattr(supplier, key, value)
            
            self.session.commit()
            logger.info(f"Updated supplier: {supplier_id}")
            return supplier
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating supplier: {e}")
            raise
    
    def delete_supplier(self, supplier_id: int) -> bool:
        """Delete a supplier"""
        try:
            supplier = self.session.query(Supplier).filter_by(id=supplier_id).first()
            if not supplier:
                raise ValueError(f"Supplier {supplier_id} not found")

            self.session.delete(supplier)
            self.session.commit()
            logger.info(f"Deleted supplier: {supplier_id}")
            return True

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting supplier: {e}")
            raise
    
    # Customer Management Methods
    def add_customer(self, name: str, type: str = 'RETAIL', contact: str = None, 
                    email: str = None, phone: str = None, address: str = None,
                    credit_limit: float = 0.0, **kwargs) -> Customer:
        """Add a new customer"""
        try:
            customer = Customer(
                name=name,
                type=type.upper(),
                contact=contact,
                email=email,
                phone_secondary=phone,  # Map phone parameter to phone_secondary field
                address=address,
                credit_limit=Decimal(str(credit_limit)),
                current_credit=Decimal('0'),
                is_active=True,
                # Handle any additional fields from kwargs
                **{k: v for k, v in kwargs.items() if hasattr(Customer, k)}
            )
            
            self.session.add(customer)
            self.session.commit()
            logger.info(f"Added customer: {name}")
            return customer
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error adding customer: {e}")
            raise
    
    def update_customer(self, customer_id: int, **kwargs) -> Customer:
        """Update an existing customer"""
        try:
            customer = self.session.query(Customer).filter_by(id=customer_id).first()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            for key, value in kwargs.items():
                if hasattr(customer, key):
                    if key in ['credit_limit', 'current_credit']:
                        # Convert numeric fields to Decimal
                        setattr(customer, key, Decimal(str(value)))
                    else:
                        setattr(customer, key, value)
            
            self.session.commit()
            logger.info(f"Updated customer: {customer_id}")
            return customer
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating customer: {e}")
            raise
    
    def delete_customer(self, customer_id: int) -> bool:
        """Delete a customer"""
        try:
            customer = self.session.query(Customer).filter_by(id=customer_id).first()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            self.session.delete(customer)
            self.session.commit()
            logger.info(f"Deleted customer: {customer_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting customer: {e}")
            raise
    
    def list_customers(self) -> List[Customer]:
        """Get all customers (alias for get_all_customers)"""
        return self.get_all_customers()
    
    def create_supplier_purchase(self, supplier_id: int, items: List[Dict[str, Any]], 
                               notes: str = None, **kwargs) -> Purchase:
        """Create a purchase from a supplier"""
        return self.create_purchase(supplier_id, items, notes=notes, **kwargs)
    
    def create_purchase(self, supplier_id: int, items: List[Dict[str, Any]], 
                       notes: str = None, **kwargs) -> Purchase:
        """Create a purchase"""
        try:
            from pos_app.models.database import Purchase, PurchaseItem
            
            # Validate items
            if not items or len(items) == 0:
                raise ValueError("Purchase must contain at least one item")
            
            # Calculate total amount and validate item data
            total_amount = Decimal('0')
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    raise ValueError(f"Item {i} must be a dictionary")
                
                # Validate required fields
                if 'product_id' not in item:
                    raise ValueError(f"Item {i} missing required field: product_id")
                if 'quantity' not in item or item.get('quantity', 0) <= 0:
                    raise ValueError(f"Item {i} must have a positive quantity")
                if 'unit_cost' not in item or item.get('unit_cost', 0) < 0:
                    raise ValueError(f"Item {i} must have a non-negative unit_cost")
                
                quantity = Decimal(str(item.get('quantity', 0)))
                unit_cost = Decimal(str(item.get('unit_cost', 0)))
                total_amount += quantity * unit_cost
            
            # Create purchase
            purchase = Purchase(
                supplier_id=supplier_id,
                total_amount=total_amount,
                paid_amount=Decimal('0'),
                notes=notes,
                status='ORDERED',
                order_date=datetime.now()
            )
            
            self.session.add(purchase)
            self.session.flush()  # Get purchase ID
            
            # Add purchase items
            for item in items:
                purchase_item = PurchaseItem(
                    purchase_id=purchase.id,
                    product_id=item.get('product_id'),
                    quantity=Decimal(str(item.get('quantity', 0))),
                    unit_cost=Decimal(str(item.get('unit_cost', 0))),
                    total_cost=Decimal(str(item.get('quantity', 0))) * Decimal(str(item.get('unit_cost', 0)))
                )
                self.session.add(purchase_item)
            
            self.session.commit()
            logger.info(f"Created purchase {purchase.id} for supplier {supplier_id}")
            return purchase
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating purchase: {e}")
            raise
    
    def record_purchase_payment(self, purchase_id: int, supplier_id: int, 
                             amount, **kwargs) -> PurchasePayment:
        """Record a payment for a purchase"""
        try:
            from pos_app.models.database import Purchase, PurchasePayment
            
            # Get purchase
            purchase = self.session.query(Purchase).filter_by(id=purchase_id).first()
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            
            # Create payment
            payment = PurchasePayment(
                purchase_id=purchase_id,
                supplier_id=supplier_id,
                amount=amount,
                payment_date=datetime.now(),
                payment_method=kwargs.get('payment_method', 'CASH')
            )
            
            self.session.add(payment)
            
            # Update purchase paid amount and status
            # Ensure both values are Decimal
            current_paid = purchase.paid_amount or Decimal('0')
            if not isinstance(current_paid, Decimal):
                current_paid = Decimal(str(current_paid))
            
            new_total_paid = current_paid + amount
            purchase.paid_amount = new_total_paid
            
            # Update status based on payment progress
            if new_total_paid >= purchase.total_amount:
                purchase.status = 'PAID'
            elif current_paid == 0 and new_total_paid > 0:
                purchase.status = 'PARTIAL'
            elif new_total_paid > 0 and new_total_paid < purchase.total_amount:
                purchase.status = 'PARTIAL'
            # Keep existing status if no change in payment progress
            
            logger.info(f"Updated purchase {purchase_id} paid amount to {new_total_paid}, status: {purchase.status}")
            
            self.session.commit()
            logger.info(f"Recorded payment of {amount} for purchase {purchase_id}")
            return payment
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error recording purchase payment: {e}")
            raise
    
    def receive_purchase(self, purchase_id: int, items_received: List[Dict[str, Any]] = None, 
                        **kwargs) -> bool:
        """Receive a purchase and update inventory"""
        try:
            from pos_app.models.database import Purchase, PurchaseItem, Product
            
            # Get purchase
            purchase = self.session.query(Purchase).filter_by(id=purchase_id).first()
            if not purchase:
                raise ValueError(f"Purchase {purchase_id} not found")
            
            # Get all purchase items
            purchase_items = self.session.query(PurchaseItem).filter_by(purchase_id=purchase_id).all()
            
            # Update stock for each item
            for purchase_item in purchase_items:
                product = self._get_product_query(purchase_item.product_id, lock_for_update=True).first()
                if product:
                    # If specific items received provided, use those quantities
                    received_qty = Decimal(str(purchase_item.quantity))
                    if items_received:
                        for item in items_received:
                            if item.get('product_id') == purchase_item.product_id:
                                received_qty = Decimal(str(item.get('quantity', purchase_item.quantity)))
                                break
                    
                    # Update stock
                    current_stock = Decimal(str(product.stock_level or 0))
                    new_stock = current_stock + received_qty
                    product.stock_level = new_stock
                    logger.info(f"Updated stock for product {product.id}: from {current_stock} to {new_stock}")
            
            # Update purchase status
            purchase.status = 'RECEIVED'
            purchase.received_date = datetime.now()
            
            self.session.commit()
            logger.info(f"Received purchase {purchase_id}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error receiving purchase: {e}")
            raise
    
    def get_supplier_purchase_history(self, supplier_id: int, **kwargs) -> List[Purchase]:
        """Get purchase history for a supplier"""
        try:
            from pos_app.models.database import Purchase
            
            purchases = self.session.query(Purchase).filter_by(supplier_id=supplier_id).order_by(Purchase.order_date.desc()).all()
            return purchases
            
        except Exception as e:
            logger.error(f"Error getting supplier purchase history: {e}")
            return []
    
    def fix_negative_stock_for_product(self, product_id: int) -> bool:
        """Fix negative stock for a product"""
        try:
            product = self.session.query(Product).filter_by(id=product_id).first()
            if not product:
                raise ValueError(f"Product {product_id} not found")
            
            if product.stock_level < 0:
                product.stock_level = Decimal('0')
                self.session.commit()
                logger.info(f"Fixed negative stock for product {product_id}")
            
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error fixing negative stock: {e}")
            raise
    
    # Expense Management Methods
    def create_recurring_expense(self, title: str, amount: float, category: str = None,
                               frequency: str = 'MONTHLY', start_date=None, end_date=None,
                               auto_create: bool = False, **kwargs) -> Expense:
        """Create a recurring expense by creating an Expense and ExpenseSchedule"""
        try:
            from pos_app.models.database import Expense, ExpenseSchedule
            
            # Create the Expense record with title
            expense = Expense(
                title=title,
                amount=Decimal(str(amount)),
                category=category,
                frequency=frequency,
                is_recurring=True,
                auto_create=auto_create,
                next_due_date=start_date or datetime.now().date(),
                expense_date=datetime.now(),
                **{k: v for k, v in kwargs.items() if hasattr(Expense, k)}
            )
            self.session.add(expense)
            self.session.flush()  # Get the expense ID
            
            # Create the ExpenseSchedule record linked to the expense
            schedule = ExpenseSchedule(
                expense_id=expense.id,
                scheduled_date=start_date or datetime.now().date(),
                amount=Decimal(str(amount)),
                status='PENDING',
                notes=f"{category or ''} - {title}"  # Store title in notes for reference
            )
            self.session.add(schedule)
            
            self.session.commit()
            logger.info(f"Created recurring expense: {title}")
            return expense
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating recurring expense: {e}")
            raise
    
    def update_recurring_expense(self, old_id: str, title: str = None, amount: float = None,
                               category: str = None, frequency: str = None,
                               start_date=None, end_date=None, auto_create: bool = None,
                               **kwargs) -> Expense:
        """Update a recurring expense"""
        try:
            from pos_app.models.database import Expense, ExpenseSchedule
            
            # Find the expense by ID
            expense = self.session.query(Expense).filter_by(id=old_id).first()
            if not expense:
                raise ValueError(f"Recurring expense with ID '{old_id}' not found")
            
            # Update expense fields
            if title is not None:
                expense.title = title
            if amount is not None:
                expense.amount = Decimal(str(amount))
            if category is not None:
                expense.category = category
            if frequency is not None:
                expense.frequency = frequency
            if auto_create is not None:
                expense.auto_create = auto_create
            if start_date is not None:
                expense.next_due_date = start_date
            
            # Update associated schedule
            schedule = self.session.query(ExpenseSchedule).filter_by(expense_id=expense.id).first()
            if schedule:
                if start_date is not None:
                    schedule.scheduled_date = start_date
                if amount is not None:
                    schedule.amount = Decimal(str(amount))
                schedule.notes = f"{category or ''} - {title}"
            
            self.session.commit()
            logger.info(f"Updated recurring expense: {title}")
            return expense
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating recurring expense: {e}")
            raise
    
    def record_expense(self, title: str, amount: float, category: str = None,
                      expense_date=None, **kwargs) -> Expense:
        """Record a one-time expense"""
        try:
            expense = Expense(
                title=title,
                amount=Decimal(str(amount)),
                category=category,
                expense_date=expense_date or datetime.now(),
                # Handle any additional fields from kwargs
                **{k: v for k, v in kwargs.items() if hasattr(Expense, k)}
            )
            
            self.session.add(expense)
            self.session.commit()
            logger.info(f"Recorded expense: {title} - {amount}")
            return expense
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error recording expense: {e}")
            raise
    
    def process_recurring_expenses(self) -> int:
        """Process and create expenses for due recurring expenses"""
        try:
            from datetime import date
            today = date.today()
            count = 0
            
            # Get all recurring expenses (Expense objects with is_recurring=True)
            recurring_expenses = self.session.query(Expense).filter(
                Expense.is_recurring == True
            ).all()
            
            for recurring in recurring_expenses:
                # Check if expense is due today
                if not recurring.next_due_date:
                    continue
                
                if recurring.next_due_date > today:
                    # Not due yet
                    continue
                
                # Check if auto_create is enabled
                if not recurring.auto_create:
                    continue
                
                # Check if already created for this period
                from datetime import datetime, timedelta
                period_start = None
                if recurring.frequency == 'MONTHLY':
                    period_start = today.replace(day=1)
                elif recurring.frequency == 'WEEKLY':
                    # Start of current week (Monday)
                    days_since_monday = today.weekday()
                    period_start = today - timedelta(days=days_since_monday)
                elif recurring.frequency == 'DAILY':
                    # Today only
                    period_start = today
                elif recurring.frequency == 'YEARLY':
                    # Start of current year
                    period_start = today.replace(month=1, day=1)
                else:
                    period_start = today
                
                existing = self.session.query(Expense).filter(
                    Expense.title == recurring.title,
                    Expense.expense_date >= period_start,
                    Expense.expense_date <= today,
                    Expense.is_recurring == False  # Don't count the recurring expense itself
                ).first()
                
                if not existing:
                    # Create the expense
                    self.record_expense(
                        title=recurring.title,
                        amount=float(recurring.amount),
                        category=recurring.category
                    )
                    count += 1
                    logger.info(f"Created recurring expense: {recurring.title} ({recurring.frequency})")
                    
                    # Update next_due_date based on frequency
                    if recurring.frequency == 'MONTHLY':
                        # Move to next month
                        if today.month == 12:
                            next_date = today.replace(year=today.year + 1, month=1, day=1)
                        else:
                            next_date = today.replace(month=today.month + 1, day=1)
                        recurring.next_due_date = next_date
                    elif recurring.frequency == 'WEEKLY':
                        # Move to next week
                        next_date = today + timedelta(days=7)
                        recurring.next_due_date = next_date
                    elif recurring.frequency == 'DAILY':
                        # Move to tomorrow
                        next_date = today + timedelta(days=1)
                        recurring.next_due_date = next_date
                    elif recurring.frequency == 'YEARLY':
                        # Move to next year
                        next_date = today.replace(year=today.year + 1, month=today.month, day=today.day)
                        recurring.next_due_date = next_date
            
            self.session.commit()
            logger.info(f"Processed {count} recurring expenses")
            return count
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error processing recurring expenses: {e}")
            raise
    
    def delete_recurring_expense(self, id: str) -> bool:
        """Delete a recurring expense"""
        try:
            from pos_app.models.database import Expense, ExpenseSchedule
            
            # Find the expense by ID
            expense = self.session.query(Expense).filter_by(id=id).first()
            if not expense:
                raise ValueError(f"Recurring expense with ID '{id}' not found")
            
            # Delete associated schedules first
            schedules = self.session.query(ExpenseSchedule).filter_by(expense_id=expense.id).all()
            for schedule in schedules:
                self.session.delete(schedule)
            
            # Delete the expense
            self.session.delete(expense)
            self.session.commit()
            logger.info(f"Deleted recurring expense: {expense.title}")
            return True
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting recurring expense: {e}")
            raise
    
    def export_expenses_csv(self, start_date=None, end_date=None) -> str:
        """Export expenses to CSV file"""
        try:
            import csv
            import os
            from datetime import datetime
            
            # Get expenses
            expenses = self.list_expenses(start_date, end_date)
            
            # Generate filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"expenses_export_{timestamp}.csv"
            filepath = os.path.join(os.getcwd(), filename)
            
            # Write CSV
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['Date', 'Title', 'Category', 'Amount']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for expense in expenses:
                    writer.writerow({
                        'Date': expense.expense_date.strftime('%Y-%m-%d') if expense.expense_date else '',
                        'Title': expense.title or '',
                        'Category': expense.category or '',
                        'Amount': float(expense.amount) if expense.amount else 0.0
                    })
            
            logger.info(f"Exported {len(expenses)} expenses to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting expenses: {e}")
            raise
    
    def add_expense(self, title: str, amount: float, category: str = None, **kwargs) -> Expense:
        """Add a one-time expense"""
        return self.record_expense(title, amount, category, **kwargs)
    
    # Standard Expense Methods
    def list_standard_expenses(self) -> List:
        """List all standard expense accounts"""
        try:
            from pos_app.models.database import StandardExpense
            return self.session.query(StandardExpense).all()
        except Exception as e:
            logger.error(f"Error listing standard expenses: {e}")
            self.session.rollback()
            return []
    
    def create_standard_expense(self, name: str, category: str = None, description: str = None) -> Any:
        """Create a new standard expense account"""
        try:
            from pos_app.models.database import StandardExpense
            standard = StandardExpense(
                name=name,
                category=category,
                description=description,
                is_active=True
            )
            self.session.add(standard)
            self.session.commit()
            logger.info(f"Created standard expense: {name}")
            return standard
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error creating standard expense: {e}")
            raise
    
    def pay_standard_expense(self, id: int, amount: float, payment_method: str = 'CASH',
                            notes: str = None, **kwargs) -> Payment:
        """Record a payment against a standard expense account"""
        try:
            from pos_app.models.database import StandardExpense, Expense, Payment

            # Get standard expense
            standard = self.session.query(StandardExpense).filter_by(id=id).first()
            if not standard:
                raise ValueError(f"Standard expense {id} not found")

            # Create expense record
            expense = Expense(
                title=f"Payment to {standard.name}",
                amount=Decimal(str(amount)),
                category=standard.category,
                payment_method=payment_method,
                notes=notes,
                expense_date=datetime.now()
            )
            self.session.add(expense)

            # Create payment record
            payment = Payment(
                amount=Decimal(str(amount)),
                payment_method=payment_method,
                payment_date=datetime.now(),
                reference=notes,
                notes=notes
            )
            self.session.add(payment)

            self.session.commit()
            logger.info(f"Paid {amount} to standard expense {standard.name}")
            return payment
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error paying standard expense: {e}")
            raise
    
    def update_standard_expense(self, id: int, name: str = None, category: str = None,
                              description: str = None, **kwargs) -> Any:
        """Update a standard expense account"""
        try:
            from pos_app.models.database import StandardExpense
            standard = self.session.query(StandardExpense).filter_by(id=id).first()
            if not standard:
                raise ValueError(f"Standard expense {id} not found")
            
            if name is not None:
                standard.name = name
            if category is not None:
                standard.category = category
            if description is not None:
                standard.description = description
            
            self.session.commit()
            logger.info(f"Updated standard expense: {standard.name}")
            return standard
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error updating standard expense: {e}")
            raise
    
    def delete_standard_expense(self, id: int) -> bool:
        """Delete a standard expense account"""
        try:
            from pos_app.models.database import StandardExpense
            standard = self.session.query(StandardExpense).filter_by(id=id).first()
            if not standard:
                raise ValueError(f"Standard expense {id} not found")
            
            self.session.delete(standard)
            self.session.commit()
            logger.info(f"Deleted standard expense: {standard.name}")
            return True
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error deleting standard expense: {e}")
            raise
            
            logger.info(f"Exported {len(expenses)} expenses to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error exporting expenses: {e}")
            raise
    
    def record_customer_payment(self, customer_id: int, amount: float, payment_method: str = 'CASH',
                              reference: str = None, notes: str = None, **kwargs) -> Payment:
        """Record a payment from a customer"""
        try:
            from pos_app.models.database import Payment, Customer
            
            # Get customer
            customer = self.session.query(Customer).filter_by(id=customer_id).first()
            if not customer:
                raise ValueError(f"Customer {customer_id} not found")
            
            # Create payment record
            payment = Payment(
                customer_id=customer_id,
                amount=Decimal(str(amount)),
                payment_method=payment_method,
                payment_date=datetime.now(),
                reference=reference,
                notes=notes,
                # Handle any additional fields from kwargs
                **{k: v for k, v in kwargs.items() if hasattr(Payment, k)}
            )
            
            self.session.add(payment)
            
            # Update customer credit balance (reduce debt)
            # Ensure current_credit is a Decimal
            if not isinstance(customer.current_credit, Decimal):
                customer.current_credit = Decimal(str(customer.current_credit or 0))
            
            payment_amount = Decimal(str(amount))
            current_credit = customer.current_credit
            
            if current_credit > 0:
                # Customer has debt - apply payment to reduce it
                if payment_amount >= current_credit:
                    # Payment covers full debt with possible overpayment
                    customer.current_credit = Decimal('0')
                    overpayment = payment_amount - current_credit
                    if overpayment > 0:
                        logger.info(f"Customer {customer_id} overpaid by {overpayment} - credit balance is now 0")
                else:
                    # Partial payment
                    customer.current_credit = current_credit - payment_amount
                
                logger.info(f"Updated customer {customer_id} credit from {current_credit} to {customer.current_credit} (payment: {payment_amount})")
            else:
                # Customer has no debt - this is an overpayment or advance payment
                # In this case, we could create a negative credit (customer credit)
                # or handle it as a prepaid amount. For now, just log it.
                logger.info(f"Customer {customer_id} made payment of {payment_amount} but has no debt (current credit: {current_credit})")
                # Optionally: customer.current_credit = -payment_amount  # Create negative credit (prepaid)
            
            self.session.commit()
            logger.info(f"Recorded customer payment of {amount} for customer {customer_id}")
            return payment
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error recording customer payment: {e}")
            raise
