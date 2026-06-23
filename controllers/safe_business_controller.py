"""Wrapped BusinessController with crash reporting"""
from pos_app.utils.crash_decorator import report_crashes
from pos_app.controllers.business_logic import BusinessController

class SafeBusinessController(BusinessController):
    """BusinessController with automatic crash reporting"""
    
    @report_crashes
    def create_sale(self, *args, **kwargs):
        # Pre-flight guard: a refund must never exceed the remaining
        # (not-yet-refunded) quantity of its original sale. Enforced here in
        # the wrapper rather than in BusinessController, and it covers every
        # create_sale caller (sales, wholesale, qa, tests). Without this, the
        # refund branch in the parent blindly adds `quantity` to stock_level,
        # inflating inventory (phantom stock) and over-refunding the customer.
        # Signature: create_sale(customer_id, items, is_wholesale=False,
        #   payment_method='Cash', paid_amount=0.0, is_refund=False,
        #   refund_of_sale_id=None, discount_amount=0.0)
        is_refund = kwargs.get('is_refund', args[5] if len(args) > 5 else False)
        if is_refund:
            refund_of_sale_id = kwargs.get(
                'refund_of_sale_id', args[6] if len(args) > 6 else None
            )
            items = kwargs.get('items', args[1] if len(args) > 1 else None)
            if refund_of_sale_id is None:
                raise ValueError(
                    "Refund requires an original sale (refund_of_sale_id is missing)."
                )
            if items:
                remaining = self.get_remaining_refund_capacity(refund_of_sale_id) or {}
                aggregated = self._aggregate_item_quantities(items)
                for product_id, qty in aggregated.items():
                    remaining_qty = remaining.get(product_id, None)
                    if remaining_qty is None:
                        raise ValueError(
                            f"Cannot refund product {product_id}: it was not part of "
                            f"the original sale."
                        )
                    if qty > remaining_qty:
                        raise ValueError(
                            f"Refund exceeds remaining capacity for product "
                            f"{product_id}: {remaining_qty} left to refund, "
                            f"{qty} requested."
                        )
        return super().create_sale(*args, **kwargs)
    
    @report_crashes
    def create_purchase(self, *args, **kwargs):
        return super().create_purchase(*args, **kwargs)
    
    @report_crashes
    def update_stock(self, *args, **kwargs):
        return super().update_stock(*args, **kwargs)
    
    @report_crashes
    def get_product(self, *args, **kwargs):
        return super().get_product(*args, **kwargs)

    @report_crashes
    def get_suppliers(self, *args, **kwargs):
        return super().get_suppliers(*args, **kwargs)

    @report_crashes
    def list_suppliers(self, *args, **kwargs):
        return super().list_suppliers(*args, **kwargs)

    @report_crashes
    def add_supplier(self, *args, **kwargs):
        return super().add_supplier(*args, **kwargs)

    @report_crashes
    def list_expenses(self, *args, **kwargs):
        return super().list_expenses(*args, **kwargs)

    @report_crashes
    def record_expense(self, *args, **kwargs):
        return super().record_expense(*args, **kwargs)

    @report_crashes
    def list_recurring_expenses(self, *args, **kwargs):
        return super().list_recurring_expenses(*args, **kwargs)

    @report_crashes
    def process_recurring_expenses(self, *args, **kwargs):
        return super().process_recurring_expenses(*args, **kwargs)
    
    @report_crashes
    def list_standard_expenses(self, *args, **kwargs):
        return super().list_standard_expenses(*args, **kwargs)
    
    @report_crashes
    def add_product(self, *args, **kwargs):
        return super().add_product(*args, **kwargs)
    
    @report_crashes
    def get_products(self, *args, **kwargs):
        return super().get_products(*args, **kwargs)
    
    @report_crashes
    def get_all_products(self, *args, **kwargs):
        return super().get_all_products(*args, **kwargs)
    
    @report_crashes
    def get_customers(self, *args, **kwargs):
        return super().get_customers(*args, **kwargs)
    
    @report_crashes
    def get_all_customers(self, *args, **kwargs):
        return super().get_all_customers(*args, **kwargs)
    
    @report_crashes
    def list_customers(self, *args, **kwargs):
        return super().get_customers(*args, **kwargs)
    
    @report_crashes
    def add_customer(self, *args, **kwargs):
        return super().add_customer(*args, **kwargs)
    
    @report_crashes
    def update_customer(self, *args, **kwargs):
        return super().update_customer(*args, **kwargs)
    
    @report_crashes
    def delete_customer(self, *args, **kwargs):
        return super().delete_customer(*args, **kwargs)
    
    @report_crashes
    def update_supplier(self, *args, **kwargs):
        return super().update_supplier(*args, **kwargs)
    
    @report_crashes
    def delete_supplier(self, *args, **kwargs):
        return super().delete_supplier(*args, **kwargs)
    
    @report_crashes
    def create_supplier_purchase(self, *args, **kwargs):
        return super().create_supplier_purchase(*args, **kwargs)
    
    @report_crashes
    def record_purchase_payment(self, *args, **kwargs):
        return super().record_purchase_payment(*args, **kwargs)
    
    @report_crashes
    def receive_purchase(self, *args, **kwargs):
        return super().receive_purchase(*args, **kwargs)
    
    @report_crashes
    def get_supplier_purchase_history(self, *args, **kwargs):
        return super().get_supplier_purchase_history(*args, **kwargs)
    
    @report_crashes
    def get_remaining_refund_capacity(self, *args, **kwargs):
        return super().get_remaining_refund_capacity(*args, **kwargs)
    
    @report_crashes
    def validate_stock_availability(self, *args, **kwargs):
        return super().validate_stock_availability(*args, **kwargs)
    
    @report_crashes
    def fix_negative_stock_for_product(self, *args, **kwargs):
        return super().fix_negative_stock_for_product(*args, **kwargs)
    
    @report_crashes
    def get_product_by_barcode(self, *args, **kwargs):
        return super().get_product_by_barcode(*args, **kwargs)
    
    @report_crashes
    def search_products(self, *args, **kwargs):
        return super().search_products(*args, **kwargs)
    
    @report_crashes
    def create_recurring_expense(self, *args, **kwargs):
        return super().create_recurring_expense(*args, **kwargs)
    
    @report_crashes
    def update_recurring_expense(self, *args, **kwargs):
        return super().update_recurring_expense(*args, **kwargs)
    
    @report_crashes
    def delete_recurring_expense(self, *args, **kwargs):
        return super().delete_recurring_expense(*args, **kwargs)
    
    @report_crashes
    def export_expenses_csv(self, *args, **kwargs):
        return super().export_expenses_csv(*args, **kwargs)
    
    @report_crashes
    def record_customer_payment(self, *args, **kwargs):
        return super().record_customer_payment(*args, **kwargs)
