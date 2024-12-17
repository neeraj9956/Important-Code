from erpnext.accounts.party import get_party_account
from erpnext.controllers.accounts_controller import get_advance_journal_entries, get_advance_payment_entries_for_regional
import frappe
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder
from frappe.utils.data import cint, flt
from jaleel_ho.custom_selling.sales_order import get_foc_items
from erpnext.selling.doctype.sales_order.sales_order import SalesOrder

class CustomSalesOrder(SalesOrder):
    def validate(self):
        # Ensure a Cashier Ledger is open
        cashier_ledger = frappe.get_all(
            "Cashier Ledger",
            filters={"user": frappe.session.user, "status": "Open"},
            fields=["name", "status"]
        )
        if not cashier_ledger:
            frappe.throw("You should open a Cashier Ledger first before creating a Sales Order.")

        if self.items:
            customer = self.customer
            customer_group = self.customer_group
            site = self.custom_site
            dc = self.custom_distribution_channel_code
            company = self.company
            sales_organization_code = self.custom_sales_organization_code
            customer_hierarchy = self.custom_customer_hierarchy

            for row in self.items:
                item_code = row.item_code
                item_grp = row.item_group
                brnd = row.brand
                item_category = getattr(row, "item_category", None)

                # Fetch FOC rule using the helper function
                foc_rule = get_foc_items(
                    item_code=item_code,
                    customer=customer,
                    customer_group=customer_group,
                    site=site,
                    item_grp=item_grp,
                    brnd=brnd,
                    item_category=item_category,
                    dc=dc,
                    company=company,
                    sales_organization_code=sales_organization_code,
                    customer_hierarchy=customer_hierarchy,
                    has_priority=0  # Assuming priority-based sorting
                )

                if foc_rule:
                    for rule in foc_rule:
                        if row.qty >= rule["min_qty"]:
                            existing_free_item = next(
                                (item for item in self.items if item.item_code == rule["free_item"] and item.is_free_item),
                                None
                            )
                            existing_parent_item = next(
                                (item for item in self.custom_foc_reference if item.item_code == rule["item_code"]),
                                None
                            )

                            if not (existing_free_item and existing_parent_item):
                                self.append("items", {
                                    "item_code": rule["free_item"],
                                    "is_free_item": 1,
                                    "qty": rule["free_qty"],
                                    "pricing_rules":rule['pricing_rule_name'],
                                    "rate": 0.0,
                                    "amount": 0.0,
                                    "description": f"Free item as per FOC rule {rule['pricing_rule_name']}"
                                })
                                self.append("custom_foc_reference", {
                                    "pricing_rule": rule["pricing_rule_name"],
                                    "item_code": rule["item_code"],
                                    "rule_applied": 1
                                })
                else:
                    pass

        return super().validate()

        
    @frappe.whitelist()
    def set_advances(self):
        """Returns list of advances against Account, Party, Reference"""

        # Fetch advance entries
        res = self.get_advance_entries(
            include_unallocated=not cint(self.get("only_include_allocated_payments"))
        )

        # Initialize advances list
        self.set("advances", [])
        advance_allocated = 0

        for d in res:
            # Determine the amount to allocate
            if self.get("party_account_currency") == self.company_currency:
                amount = self.get("base_rounded_total") or self.base_grand_total
            else:
                amount = self.get("rounded_total") or self.grand_total
            
            allocated_amount = min(amount - advance_allocated, d.amount)
            advance_allocated += flt(allocated_amount)

            # Create advance entry row
            advance_row = {
                "doctype": self.doctype + " Advance",
                "reference_type": d.reference_type,
                "reference_name": d.reference_name,
                "reference_row": d.reference_row,
                "remarks": d.remarks,
                "advance_amount": flt(d.amount),
                "allocated_amount": allocated_amount,
                "ref_exchange_rate": flt(d.exchange_rate),  # exchange_rate of advance entry
            }

            # Set paid from/to account if available
            if d.get("paid_from"):
                advance_row["account"] = d.paid_from
            if d.get("paid_to"):
                advance_row["account"] = d.paid_to

            # Append to advances list
            self.append("custom_advances", advance_row)

    def get_advance_entries(self, include_unallocated=True):
        party_account = []
        if self.doctype == "Sales Order":
            party_type = "Customer"
            party = self.customer
            amount_field = "credit_in_account_currency"
            order_field = "sales_order"
            order_doctype = "Sales Order"
            party_account.append(self.custom_debit_to)
        else:
            party_type = "Supplier"
            party = self.supplier
            amount_field = "debit_in_account_currency"
            order_field = "purchase_order"
            order_doctype = "Purchase Order"
            party_account.append(self.credit_to)

        party_account.extend(
            get_party_account(party_type, party=party, company=self.company, include_advance=True)
        )

        # Fetch orders and journal entries
        order_list = list(set(d.get(order_field) for d in self.get("items") if d.get(order_field)))
        journal_entries = get_advance_journal_entries(
            party_type, party, party_account, amount_field, order_doctype, order_list, include_unallocated
        )
        payment_entries = get_advance_payment_entries_for_regional(
            party_type, party, party_account, order_doctype, order_list, include_unallocated
        )

        # Combine journal entries and payment entries
        res = journal_entries + payment_entries

        return res
    @frappe.whitelist()
    def get_customer(mobile_no=None, name=None):
        res = frappe._dict()
        sql = frappe.db.sql(
            """SELECT EXISTS(SELECT * FROM `tabCustomer` WHERE mobile_no = %s OR name = %s)""",
            (mobile_no, name)
        )
        result = sql[0][0]

def custom_insert_item_price(args):
    pass

