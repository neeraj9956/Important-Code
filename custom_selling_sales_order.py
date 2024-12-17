
import frappe
import json
import math
from frappe.model.mapper import get_mapped_doc
import frappe.utils
from frappe.utils.data import cint, flt
from jaleel_ho.bulk_pricing.doctype.pricing.pricing import fetch_price
import requests
from erpnext.accounts.doctype.payment_entry.payment_entry import get_payment_entry
from frappe.utils import today , now_datetime , add_to_date
from frappe import _
from datetime import datetime, timedelta
from frappe.query_builder import DocType
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from erpnext.stock.get_item_details import get_item_tax_map
from frappe.utils import get_datetime
from types import SimpleNamespace

def validate(self , method):
    stock_reservation(self)

def stock_reservation(self):
    try:
        if self.is_new():
            # Use Case 1: when document is new
            for idx, item in enumerate(self.items):
                bin_id = frappe.db.get_value("Reserved Bin", {"item_code": item.item_code, 'warehouse': item.warehouse})
                if not bin_id:
                    bin_id = create_reserve_bin(item)

                doc = frappe.get_doc("Reserved Bin", bin_id)

                # Update reserved quantity
                reserved_qty = int(doc.reserved_qty or 0)
                doc.reserved_qty = reserved_qty + int(item.qty)
                actual_qty = int(doc.actual_qty or 0)
                doc.available_qty = actual_qty - doc.reserved_qty

                doc.save()
                item.custom_available_qty = doc.available_qty
                if doc.available_qty <= 0:
                    create_out_of_stock_entry(self, item)
        
        else:
            previous_doc = self.get_doc_before_save()

            # Track current items based on index (item_code, warehouse)
            current_items = [(item.item_code, item.warehouse, item.qty) for item in self.items]

            for idx, item in enumerate(self.items):
                bin_id = frappe.db.get_value("Reserved Bin", {"item_code": item.item_code, 'warehouse': item.warehouse})
                if not bin_id:
                    bin_id = create_reserve_bin(item)

                doc = frappe.get_doc("Reserved Bin", bin_id)

                # Use Case 2: Update existing items with increased/decreased quantity
                previous_item = next((i for i in previous_doc.items if i.item_code == item.item_code and i.warehouse == item.warehouse and i.idx == item.idx), None)

                if previous_item:
                    previous_qty = int(previous_item.qty or 0)
                    current_qty = int(item.qty or 0)

                    if current_qty > previous_qty:
                        # Increase reserved quantity
                        doc.reserved_qty += current_qty - previous_qty
                        actual_qty = int(doc.actual_qty or 0)
                        doc.available_qty = actual_qty - doc.reserved_qty
                        doc.save()
                        item.custom_available_qty = doc.available_qty
                        if doc.available_qty <= 0:
                            create_out_of_stock_entry(self, item)
                    elif current_qty < previous_qty:
                        # Decrease reserved quantity
                        qty_difference = previous_qty - current_qty
                        doc.reserved_qty = max(0, doc.reserved_qty - qty_difference)

                        actual_qty = int(doc.actual_qty or 0)
                        doc.available_qty = actual_qty - doc.reserved_qty
                        doc.save()
                        item.custom_available_qty = doc.available_qty
                        if doc.available_qty <= 0:
                            create_out_of_stock_entry(self, item)

                else:
                    # Use Case 3: New line item added in an existing document
                    doc.reserved_qty += int(item.qty)
                    actual_qty = int(doc.actual_qty or 0)
                    doc.available_qty = actual_qty - doc.reserved_qty
                    doc.save()
                    item.custom_available_qty = doc.available_qty
                    if doc.available_qty <= 0:
                        create_out_of_stock_entry(self, item)
                    
            # Use Case 4: Deleting items from the document (release stock)
            if any(
                not any(
                    i.item_code == previous_item.item_code and i.warehouse == previous_item.warehouse and i.idx == previous_item.idx
                    for i in self.items
                )
                for previous_item in previous_doc.items
            ):
                release_deleted_items_stock(self, previous_doc)
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Stock Reservation Error")
        print(e, "Error")
        return str(e)


def release_deleted_items_stock(self, previous_doc):
    for previous_item in previous_doc.items:
        # Check if the previous item is NOT present in the current items
        item_still_exists = any(
            i.item_code == previous_item.item_code and i.warehouse == previous_item.warehouse and i.idx == previous_item.idx
            for i in self.items
        )

        if not item_still_exists:
            bin_id = frappe.db.get_value("Reserved Bin", {"item_code": previous_item.item_code, 'warehouse': previous_item.warehouse})
            if not bin_id:
                bin_id = create_reserve_bin(previous_item)

            doc = frappe.get_doc("Reserved Bin", bin_id)

            qty_to_release = int(previous_item.qty or 0)
            doc.reserved_qty = max(0, int(doc.reserved_qty) - qty_to_release)
            actual_qty = int(doc.actual_qty or 0)
            doc.available_qty = actual_qty - doc.reserved_qty
            doc.save()

def create_out_of_stock_entry(sales_order, item):
    out_of_stock_entry = frappe.new_doc("Out of Stock Entry")

    # Set fields conditionally
    if sales_order.custom_user:
        out_of_stock_entry.user = sales_order.custom_user
    if not sales_order.is_new():  # Set the sales order name
        out_of_stock_entry.sales_order = sales_order.name
    out_of_stock_entry.time_stamp = frappe.utils.now()  # Set the current timestamp
    out_of_stock_entry.item = item.item_code  # Set the item code
    if item.warehouse: 
        out_of_stock_entry.warehouse = item.warehouse  # Set the warehouse

    try:
        out_of_stock_entry.save(ignore_permissions=True)  # Save without committing explicitly
        frappe.msgprint(f"Out of Stock Entry created for item: {item.item_code}")
    except Exception as e:
        frappe.msgprint(f"Error creating Out of Stock Entry: {str(e)}")
        print("Error details:", e)  # Log the error for debugging

def create_reserve_bin(item):
    reserve_bin = frappe.new_doc("Reserved Bin")
    reserve_bin.item_code = item.item_code
    reserve_bin.warehouse = item.warehouse
    reserve_bin.actual_qty = frappe.db.get_value("Bin" ,{"item_code": item.item_code ,'warehouse':item.warehouse } , 'actual_qty' )
    reserve_bin.available_qty = frappe.db.get_value("Bin" ,{"item_code": item.item_code ,'warehouse':item.warehouse } , 'actual_qty' )
    reserve_bin.save()

    return reserve_bin.name


# def updating_rate_on_submission(doc, method):
#     for item in doc.items:
#         # Prepare data for the API call
#         item_data = {
#             'item_no': item.custom_item_number,
#             'customer_no': doc.customer,
#             'distribution_channel_code': doc.custom_distribution_channel_code,
#             'location_code': doc.custom_location_code,
#             'sales_organization_code': doc.custom_sales_organization_code,
#             # 'customer_hierarchy':doc.custom_customer_hierarchy
#         }
    
#         api_response = get_discounted_item_price(json.dumps(item_data))
        
#         if api_response and 'sales_price' in api_response and 'price_with_tax' in api_response and 'tax_percent' in api_response and 'modified_date' in api_response:
#             new_rate = api_response['sales_price']
#             new_price_with_tax = api_response['price_with_tax']
#             new_tax_percent = api_response['tax_percent']

#             modified_date_str = api_response['modified_date']
#             if modified_date_str != "Not Modified Yet":
                
#                 modified_date = get_datetime(modified_date_str)
#                 item_addition_date = get_datetime(item.creation)

#                 # Calculate the time difference
#                 time_difference = modified_date - item_addition_date


#                 # Check if the price was modified within 24 hours
#                 if time_difference >= timedelta(hours=24):
#                     if new_rate != item.rate:
#                         item.rate = new_rate
#                         frappe.msgprint(f"Rate for item {item.item_code} updated from {item.rate} to {new_rate}")

#                     if new_tax_percent != item.custom_tax_percent:
#                         item.custom_tax_percent = new_tax_percent
#                         # Fetch Item Tax Template based on the new_tax_percent
#                         item_tax_templates = frappe.db.sql("""
#                             SELECT parent
#                             FROM `tabItem Tax Template Detail`
#                             WHERE tax_rate = %s
#                             """, (new_tax_percent,), as_dict=True)
                        
#                         if item_tax_templates:
#                             item.item_tax_template = frappe.db.get_value("Item Tax Template", item_tax_templates[0].parent, "name")
#                             # frappe.db.set_value('Sales Order Item','bm805pbsvr', 'item_tax_template', item_tax_templates[0].parent)
#                             frappe.msgprint(f"Item Tax Template for {item.item_code} set to {item.item_tax_template}")
#                             # doc.run_method("set_missing_values")  # Set any default values needed
#                             # doc.run_method("calculate_taxes_and_totals")  # Recalculate taxes
#                             fetch_and_apply_taxes_on_submit(doc,item)

#                     if new_price_with_tax != item.custom_rate_including_vat:
#                         item.custom_rate_including_vat = new_price_with_tax
#                     item.db_update()


def update_mode_of_payment(doc, method):
    if not doc.custom_mode_of_payment:
        selected_modes = [mode.mode_of_payment for mode in doc.custom_mode_of_payment_]  
        if "Cash" in selected_modes:
            cash_entry = doc.append("custom_mode_of_payment", {})
            cash_entry.mode_of_payment = "Cash"
            cash_entry.amount = doc.rounded_total
            doc.custom_advance_total = cash_entry.amount

            if "Credit Card" in selected_modes:
                credit_card_entry = doc.append("custom_mode_of_payment", {})
                credit_card_entry.mode_of_payment = "Credit Card"
                credit_card_entry.amount = 0  


def updating_rate_on_submission(doc, method):
    prev_total=doc.total
    prev_with_vat=doc.custom_total_amt_including_vat
    ratechanged=False
    taxchanged=False
    for item in doc.items:
        # Prepare data for the API call
        item_data = {
            'item_no': item.custom_item_number,
            'customer_no': doc.customer,
            'distribution_channel_code': doc.custom_distribution_channel_code,
            'location_code': doc.custom_location_code,
            'sales_organization_code': doc.custom_sales_organization_code,
            "customer_hierarchy":doc.custom_customer_hierarchy,
            "customer_group":doc.customer_group,
            "transportation_zone_code":doc.custom_transportation_zone_code,
            "unit_of_measure_code":item.uom,
            "qty":item.qty
        }
        if doc.custom_customer_hierarchy:
            item_data['customer_hierarchy'] = doc.custom_customer_hierarchy
        if frappe.db.get_single_value("Jaleel Settings","price_discount_mongodb"):
            api_response = get_discounted_item_price(json.dumps(item_data))
        else:
            api_response = fetch_price(json.dumps(item_data))
        
        if api_response and 'sales_price' in api_response and 'price_with_tax' in api_response and 'tax_percent' in api_response and 'modified_date' in api_response:
            new_rate = api_response['sales_price']
            new_price_with_tax = api_response['price_with_tax']
            new_tax_percent = api_response['tax_percent']

            modified_date_str = api_response['modified_date']
            if modified_date_str != "Not Modified Yet":
                
                modified_date = get_datetime(modified_date_str)
                item_addition_date = get_datetime(item.creation)

                # Calculate the time difference
                time_difference = modified_date - item_addition_date

                # Check if the price was modified within 24 hours
                if time_difference >= timedelta(hours=24):
                    if new_rate != item.rate:
                        frappe.msgprint(f"Rate for item {item.item_code} updated from {item.rate} to {new_rate}")
                        item.rate = new_rate
                        item.amount=item.rate*item.qty
                        ratechanged=True

                    if new_tax_percent != item.custom_tax_percent:
                        item.custom_tax_percent = new_tax_percent
                        # Fetch Item Tax Template based on the new_tax_percent
                        item_tax_templates = frappe.db.sql("""
                            SELECT parent
                            FROM `tabItem Tax Template Detail`
                            WHERE tax_rate = %s
                            """, (new_tax_percent,), as_dict=True)
                        
                        if item_tax_templates:
                            item.item_tax_template = frappe.db.get_value("Item Tax Template", item_tax_templates[0].parent, "name")
                            frappe.msgprint(f"Item Tax Template for {item.item_code} set to {item.item_tax_template}")
                            taxchanged=True

                    if new_price_with_tax != item.custom_rate_including_vat:
                        item.custom_rate_including_vat = new_price_with_tax
                        item.custom_amount_including_vat=item.custom_rate_including_vat*item.qty
                    doc.total+=item.amount
                    doc.custom_total_amt_including_vat+=item.custom_amount_including_vat

    # doc.total=doc.total-prev_total
    # doc.custom_total_amt_including_vat=doc.custom_total_amt_including_vat-prev_with_vat

    # Save t document to persist the changes
    if taxchanged or ratechanged:
        fetch_and_apply_taxes_on_submit(doc)
        
def fetch_and_apply_taxes_on_submit(doc):
    """
    Fetch the latest item tax template and apply taxes during Sales Order submission.
    This is called from a before_submit or on_submit hook.
    """
    for item in doc.items:
        if item.item_tax_template:
            # Fetch the latest tax rates based on the item tax template
            item_tax_map = get_item_tax_map(doc.company, item.item_tax_template, as_json=False)
            if item_tax_map:
                # Apply the fetched tax map to the item
                item.item_tax_rate = json.dumps(item_tax_map)
    # After setting tax rates, calculate the total taxes and apply them to the doc
    # print(frappe.as_json(doc.items))
    calculate_taxes_and_totals(doc)

def calculate_taxes_and_totals(doc):
    """
    This function clears existing taxes and recalculates them based on each item's tax template.
    It checks if the account head already exists in the taxes table, updating the total and amount if it does.
    """
    # Clear existing taxes
    doc.taxes = []
    
    # Initialize total tax and grand total variables
    total_tax = 0
    
    # Iterate through items to calculate tax
    for item in doc.items:
        tax_amount = 0
        
        
        # Parse item_tax_rate if present
        if item.item_tax_rate:
            item_tax_rate = json.loads(item.item_tax_rate)
            
            # Iterate over each tax entry in item tax rate and calculate tax
            for account_head, tax_rate in item_tax_rate.items():
                tax_amount_for_item = (tax_rate / 100) * item.amount
                tax_amount += tax_amount_for_item
                
                # Check if the tax already exists in doc.taxes based on account_head
                existing_tax = next((tax for tax in doc.taxes if tax.account_head == account_head), None)
                
                if existing_tax:
                    # Update the existing tax entry
                    prev_tax_amount=existing_tax.tax_amount
                    existing_tax.tax_amount += tax_amount_for_item
                    existing_tax.total = item.amount + existing_tax.tax_amount + existing_tax.total-prev_tax_amount

                    # existing_tax.total+=existing_tax.tax_amount
                else:
                    # Create a new tax entry as a Document object
                    tax_entry = frappe.get_doc({
                        "doctype": "Sales Taxes and Charges",
                        "parentfield": "taxes",
                        "account_head": account_head,
                        "charge_type": "On Net Total",
                        "rate": tax_rate,
                        "total": item.amount + tax_amount_for_item,
                        "tax_amount": tax_amount_for_item,
                        "description": "sales"
                    })
                    doc.append("taxes", tax_entry)
        
        total_tax += tax_amount
    
    # Update total taxes and grand total
    doc.total_taxes_and_charges = total_tax
    doc.grand_total = doc.total + total_tax
    doc.rounded_total = round(doc.grand_total)
    


# def updating_rate_on_submission(doc, method):
#     for item in doc.items:
#         # Prepare data for the API call
#         item_data = {
#             'item_no': item.custom_item_number,
#             'customer_no': doc.customer,
#             'distribution_channel_code': doc.custom_distribution_channel_code,
#             'location_code': doc.custom_location_code,
#             'sales_organization_code': doc.custom_sales_organization_code,
#             # 'customer_hierarchy':doc.custom_customer_hierarchy
#         }
    
#         api_response = get_discounted_item_price(json.dumps(item_data))
        
#         if api_response!= None and 'sales_price' in api_response and 'price_with_tax' in api_response and 'tax_percent' in api_response and 'modified_date' in api_response:
#             new_rate = api_response['sales_price']
#             new_price_with_tax = api_response['price_with_tax']
#             new_tax_percent = api_response['tax_percent']
            
#             # item_tax_templates = frappe.db.sql("""
#             #                 SELECT parent
#             #                 FROM `tabItem Tax Template Detail`
#             #                 WHERE tax_rate = %s
#             #                 """, (new_tax_percent,), as_dict=True)
#             # print(item_tax_templates[0].parent)

#             modified_date_str = api_response['modified_date']
#             if modified_date_str != "Not Modified Yet":
#                 print(new_tax_percent,new_price_with_tax)
#                 modified_date = datetime.strptime(modified_date_str, '%Y-%m-%d %H:%M:%S')
        
#                 item_addition_date = datetime.strptime(item.creation, '%Y-%m-%d %H:%M:%S.%f')  # Include fractional seconds

#                 # Calculate the time difference
#                 time_difference = modified_date - item_addition_date
#                 print("time",time_difference)
#                 print(timedelta(hours=24))
#                 # Check if the price was modified within 24 hours
#                 if time_difference >= timedelta(hours=24):
#                     print("im in")
#                     if new_rate != item.rate:
#                         item.rate = new_rate
#                         frappe.msgprint(f"Rate for item {item.item_code} updated from {item.rate} to {new_rate}")
#                     if new_tax_percent != item.custom_tax_percent:
#                         item.custom_tax_percent=new_tax_percent
#                         item_tax_templates = frappe.db.sql("""
#                             SELECT parent
#                             FROM `tabItem Tax Template Detail`
#                             WHERE tax_rate = %s
#                             """, (new_tax_percent,), as_dict=True)
#                         print("HIHIHIHIHIHIH",item_tax_templates)
#                         item.item_tax_template=item_tax_templates[0].parent

#                     if new_price_with_tax != item.custom_rate_including_vat:
#                         item.custom_rate_including_vat=new_price_with_tax


@frappe.whitelist()
def cancel_expired_sales_orders():

    # Calculate the timestamp for 72 hours ago
    threshold_time = add_to_date(now_datetime(), hours=-72)
    
    # Fetch Sales Orders in 'Draft' state that were created more than 72 hours ago
    sales_orders = frappe.get_all("Sales Order",
        filters=[
            ["docstatus", "=", 0],  # Draft status
            ["creation", "<=", threshold_time],
            ["custom_distribution_channel_code" , "not in",['11' , '12'] ],
        ],
        fields=["name"]
    )

    for so in sales_orders:
        sales_order_doc = frappe.get_doc("Sales Order", so["name"])

        # Release the reserved stock for each item before canceling
        for item in sales_order_doc.items:
            row = {
                "item_code": item.item_code,
                "warehouse": item.warehouse,
                "qty": item.qty
            }
            stock_release_on_order_cancellation(row , manual_cancellation=False)
       
        sales_order_doc.submit()
        sales_order_doc.cancel()
        frappe.db.commit()


@frappe.whitelist()
def stock_release_on_order_cancellation(row , manual_cancellation = None):
    try:
        if manual_cancellation:
            if isinstance(row, str):
                row = json.loads(row)
                stock_release(row)
        else:
            stock_release(row)

    except Exception as e:
        frappe.log_error(message=str(e), title="Error in stock release on order cancellation")

def stock_release(row):
    bin_id = frappe.db.get_value("Reserved Bin", {"item_code": row.get('item_code') ,'warehouse': row.get('warehouse') })

    if not bin_id:
        frappe.throw("No Reserved Bin found for the specified item code and warehouse.")

    doc = frappe.get_doc("Reserved Bin", bin_id )
    doc.reserved_qty = int(doc.reserved_qty or 0) - int(row.get('qty'))
    doc.available_qty = int(doc.actual_qty or 0) - int(doc.reserved_qty)
    doc.save()

@frappe.whitelist()
def items_substitution(row, site=None, date_time=None ):
    try:
        if isinstance(row, str):
            row = json.loads(row)

        query = """ 
            SELECT 
                asmc.substitution_item, 
                asmc.substitution_item_group, 
                asmc.substitution_item_brand, 
                asmc.substitute_item_uom 
            FROM 
                `tabArticle Substitution Master` asm
            JOIN 
                `tabStore` s ON s.parent = asm.name
            JOIN 
                `tabArticle Substitution Detail Child` asmc ON asmc.parent = asm.name
            WHERE 
                asm.item = %(item)s
                AND asm.uom = %(uom)s
                AND asm.start_date_time <= %(datetime)s
                AND asm.end_date_time >= %(datetime)s
                AND asm.is_active = 1
                AND s.site = %(site)s
        """

        filters = {
            "item": row.get("item_code"),
            "uom": row.get("uom"),
            "site": site if site else None,
            "datetime": date_time,

        }

        data = frappe.db.sql(query, filters, as_dict=True)
        return data
    
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Item Substitution Error")
        print(f"Error encountered: {str(e)}")

@frappe.whitelist()
def article_exclusion(row, company, customer=None, region=None, site=None, dc=None, date_time=None):
    try:
        if isinstance(row, str):
            row = json.loads(row)
        
        query = """
            SELECT 
                aemd.channel,
                aemd.customer ,
                aemd.region_code
            FROM
                `tabArticle Exclusion` ae
            JOIN
                `tabArticle Exclusion Multiselect Details` aemd ON aemd.parent = ae.name
            WHERE
                ae.company_code = %(company)s
                AND ae.site = %(site)s
                AND ae.item = %(item)s
                AND ae.start_date_time <= %(datetime)s
                AND ae.end_date_time >= %(datetime)s
                AND ae.is_active = 1
                AND (
                    (aemd.channel = %(dc)s AND aemd.customer = %(customer)s AND aemd.region_code = %(region)s) OR
                    (aemd.channel = %(dc)s AND aemd.customer = "" AND aemd.region_code = %(region)s) OR
                    (aemd.channel = %(dc)s AND aemd.customer = %(customer)s AND aemd.region_code = "") OR
                    (aemd.channel = %(dc)s AND aemd.customer = "" AND aemd.region_code = "") OR
                    (aemd.channel = "" AND aemd.customer = %(customer)s AND aemd.region_code = %(region)s) OR
                    (aemd.channel = "" AND aemd.customer = "" AND aemd.region_code = %(region)s) OR
                    (aemd.channel = "" AND aemd.customer = "" AND aemd.region_code = "")
                    )
            ORDER BY
                (aemd.channel IS NOT NULL) DESC,
                (aemd.region_code IS NOT NULL) DESC,
                (aemd.customer IS NOT NULL) DESC
        """
        filters = {
            "company" : company,
            "site" : site,
            "item" : row.get("item_code"),
            "datetime" : date_time,
            "dc" : dc,
            "customer" : customer,
            "region" : region
        }

        exclusion_data = frappe.db.sql(query, filters, as_dict=True,debug=True)
        if exclusion_data:
            frappe.msgprint(f"The item {row.get('item_code')} is excluded from sale in this area.")
            return exclusion_data
            # for exclusion in exclusion_data:
                # if exclusion.get('customer') and exclusion.get('region_code'):
            #         pass
        return None

    except Exception as e:
        frappe.log_error(message=str(e), title="Error in article_exclusion function")


        
@frappe.whitelist()
def max_qty(row, customer = None, site=None, dc=None, date_time=None):
    try:
        if isinstance(row, str):
            row = json.loads(row)

        query = """
            SELECT 
                moq.frequency,
                amd.max_item_qty_per_so,
                amd.max_item_qty,
                amd.customer
            FROM
                `tabMax Order Quantity` moq
            JOIN 
                `tabArticle Multiselect Details` amd ON amd.parent = moq.name
            WHERE
                moq.site = %(site)s
                AND moq.item = %(item)s
                AND moq.start_date_time <= %(datetime)s
                AND moq.end_date_time >= %(datetime)s
                AND moq.is_active = 1
                AND (
                    (amd.channel = %(dc)s AND amd.customer = %(customer)s) OR
                    (amd.channel = %(dc)s AND amd.customer IS NULL) OR
                    (amd.channel IS NULL AND amd.customer = %(customer)s) OR
                    (amd.channel IS NULL AND amd.customer IS NULL)
                )
            ORDER BY
                (amd.channel IS NOT NULL) DESC,
                (amd.customer IS NOT NULL) DESC
            """
        filters = {
            "item" : row.get('item_code'),
            "site" : site,
            "datetime" : date_time,
            "dc" : dc,
            "customer" : customer
        }

        max_order_data = frappe.db.sql(query, filters, as_dict=True)
        if max_order_data:
            max_order_dict = None
            for max_child in max_order_data:
                if max_child.get('customer') == customer:
                    max_order_dict = max_child
                    break

                elif max_order_dict is None:
                    max_order_dict = max_child
                
            if max_order_dict is not None and row.get('qty') and row.get('qty') > max_order_dict.get('max_item_qty_per_so'):
                frappe.msgprint(f"Order quantity exceeds the maximum allowed quantity for {row.get('item_code')}. Maximum allowed: {max_order_dict.get('max_item_qty_per_so')}")

            if isinstance(date_time, str):
                date_time_obj = datetime.strptime(date_time, "%Y-%m-%d %H:%M:%S")
            frequency_date = date_time_obj - timedelta(days=max_order_dict.get('frequency'))

            invoice = """
                SELECT 
                    SUM(sii.qty) AS total_quantity
                FROM 
                    `tabSales Invoice Item` sii
                JOIN 
                    `tabSales Invoice` si ON sii.parent = si.name
                WHERE 
                    sii.item_code = %(item)s
                    AND si.customer = %(customer)s
                    AND CONCAT(si.posting_date, ' ', si.posting_time) BETWEEN %(start_date_time)s AND %(end_date_time)s
            """
            filter = {
                "item": row.get("item_code"),
                "customer": customer,
                "start_date_time": frequency_date,
                "end_date_time": date_time_obj,
            }
            
            si_details = frappe.db.sql(invoice, filter, as_dict=True)
            if (si_details and si_details[0].get('total_quantity')) and ((si_details[0].get('total_quantity') + row.get('qty')) > max_order_dict.get('max_item_qty')):
                frappe.msgprint(f"Order quantity exceeds the maximum allowed quantity for frequency {row.get('item_code')}. Maximum allowed: {max_order_dict.get('max_item_qty')}")

        print("Not Found")
        return None

    except Exception as e:
        frappe.log_error(message=str(e), title="Error in max_qty function")
        print(f"An error occurred while processing the max quantity: {str(e)}")
# ----------------------------------------------------------------------Need to be removed-----------------------------------------------------------------------------
# @frappe.whitelist()
# def get_item_price(doc):
#     doc = json.loads(doc)
#     mongoURL = frappe.db.get_single_value("Jaleel Settings", "mongodb_url")
#     url = mongoURL+"/api/get_item_price"
    
#     # Convert all values in the doc dictionary to integers
#     for key in doc:
#         doc[key] = int(doc[key])

#     # Convert the dictionary to a JSON string
#     payload = json.dumps(doc)
    
#     headers = {
#         'Content-Type': 'application/json'
#     }

#     # Make the API request
#     response = requests.request("POST", url, headers=headers, data=payload)
    
#     # Parse the response
#     if response.status_code == 200:
#         response_data = json.loads(response.text)

#         if 'message' in response_data:
#             response = response_data['message']
#             return response
        
#         return None

#     return None


@frappe.whitelist()
def get_discounted_item_price(doc):
    doc = json.loads(doc)
    mongoURL = frappe.db.get_single_value('Jaleel Settings', 'mongodb_url')
    if not mongoURL:
        frappe.msgprint("Please set Mongo URL in Jaleel Settings")
        return 

    url = mongoURL+"/api/get_discounted_item_price"
    # Convert all values in the doc dictionary to integers
    for key in doc:
        if key!="unit_of_measure_code":
            doc[key] = int(doc[key])
        else:
            doc[key]=str(doc[key])

    # Convert the dictionary to a JSON string
    payload = json.dumps(doc)
    
    headers = {
        'Content-Type': 'application/json'
    }

    # Make the API request
    response = requests.request("POST", url, headers=headers, data=payload)
    # Parse the response
    if response.status_code == 200:
        response_data = json.loads(response.text)

        if 'message' in response_data:
            response = response_data['message']
            return response
        
        return None

    return None


@frappe.whitelist()
def create_advance_payments_and_invoice(docname):
    try:
        # Load the Sales Order document
        doc = frappe.get_doc("Sales Order", docname)
        
        # Call the existing `create_advance_payments` method
        create_advance_payments(doc, "on_submit")

        # Call the existing `create_sales_invoice` method
        create_sales_invoice(doc, "on_submit")
        
        return _("Advance payments and Sales Invoice created successfully.")
    except Exception as e:
        frappe.throw(_("Error during payment and invoice creation: {0}").format(str(e)))
        
def create_advance_payments(doc, method):
    try:
        if doc.custom_distribution_channel_code == "02":
            if doc.custom_advance_total < doc.rounded_total and doc.custom_distribution_channel_code == "02":
                raise ValueError("Cannot proceed with Sales Invoice: Advance payment is less than the rounded total.")

            if doc.custom_mode_of_payment:
                for child_entry in doc.custom_mode_of_payment:
                    mode_of_payment = getattr(child_entry, 'mode_of_payment', None)
                    amount = getattr(child_entry, 'amount', 0)
                    if mode_of_payment and amount:
                        payment_entry = create_and_submit_payment(doc, mode_of_payment, amount)
                    child_entry.payment_entry = payment_entry
                    child_entry.db_update()  
                doc.reload()
                doc.save()
    except Exception as e:
        frappe.throw(f"Error creating advance payments: {str(e)}")
  
def create_sales_invoice(doc,method):
    if (doc.custom_distribution_channel_code in ['2', '02']):
        invoice = make_sales_invoice(doc.name)

        mode_of_payments = []

        if doc.custom_mode_of_payment_:
            for mop in doc.custom_mode_of_payment_:
                if hasattr(mop, 'mode_of_payment'):
                    mode_of_payments.append(str(mop.mode_of_payment)) 
        #adjust mop in sales invoice
        if hasattr(invoice, 'custom_mode_of_payment'): 
            for mode in mode_of_payments:
                mop = invoice.append('custom_mode_of_payment') 
                mop.mode_of_payment = mode

        invoice.update_stock = 1
        if len(doc.custom_mode_of_payment)>0:
            for advance in doc.custom_mode_of_payment:
                invoice.append("advances",{
                    "reference_type": "Payment Entry",
                    "reference_name": advance.payment_entry,
                    "advance_amount": advance.amount,
                    "allocated_amount": advance.amount,
                    "remarks": frappe.db.get_value("Payment Entry", advance.payment_entry, "remarks")
                })
        if len(doc.custom_advances)>0:
            for advances in doc.custom_advances:
                invoice.append("advances",{
                    "reference_type": advances.reference_type,
                    "reference_name": advances.reference_name,
                    "advance_amount": advances.advance_amount,
                    "allocated_amount": advances.allocated_amount,
                    "remarks": advances.remarks
                })
        invoice.set_advances()
        invoice.save()
        invoice.submit()
        update_cashier_ledger(invoice)
        create_cash_receipt(doc , invoice.name)

def update_cashier_ledger(invoice):
    for advance in invoice.advances:
        payment_entry = frappe.get_doc("Payment Entry", advance.reference_name)
        
        # Check if payment is by cash and other conditions for Cashier Ledger update
        if payment_entry.mode_of_payment == "Cash":
            cashier_ledger_doc = frappe.get_list(
                "Cashier Ledger",
                filters={
                    "status": "Open",
                    "owner": frappe.session.user
                },
                order_by="creation DESC",
                limit=1
            )

            if not cashier_ledger_doc:
                frappe.throw("No open Cashier Ledger found for the current user.")

            cashier_ledger_doc = frappe.get_doc("Cashier Ledger", cashier_ledger_doc[0].name)

            # Update Cashier Ledger if the distribution channel is allowed
            if invoice.custom_distribution_channel not in ["03", "16", "12", "14"]:
                cashier_ledger_doc.append("cashier_ledger_entries", {
                    "voucher_type": "Payment Entry",
                    "voucher_id": advance.reference_name,
                    "amount": advance.allocated_amount,
                    "id": invoice.name
                })

            cashier_ledger_doc.save(ignore_permissions=True)

def create_cash_receipt(doc , invoice_id):
    invoice = frappe.get_doc("Sales Invoice" ,invoice_id )
    cash_receipt = frappe.new_doc("Cash Receipt")
    cash_receipt.customer = invoice.customer
    cash_receipt.against_sales_order = doc.name
    cash_receipt.total_order_amount = invoice.grand_total
    cash_receipt.paid_amount = invoice.total_advance
    cash_receipt.outstanding_amount = invoice.outstanding_amount
    cash_receipt.save()
    cash_receipt.submit()

@frappe.whitelist()
def from_so_create_sales_invoice(doc):
    try:
        si = make_sales_invoice(doc)
        si.set_advances()
        adjust_invoice_qty_based_on_pick_list(si, doc)
        doc = frappe.get_doc("Sales Order" , doc)
        if doc.custom_multiple_shipment == 0:
            si.update_stock = 1
            
        mode_of_payments = []
        if doc.custom_mode_of_payment_:
            for mop in doc.custom_mode_of_payment_:
                if hasattr(mop, 'mode_of_payment'):
                    mode_of_payments.append(str(mop.mode_of_payment)) 
        #adjust mop in sales invoice
        existing_mops = {mop.mode_of_payment for mop in si.get("custom_mode_of_payment", [])}
        if hasattr(si, 'custom_mode_of_payment'):
            for mode in mode_of_payments:
                if mode not in existing_mops:
                    mop = si.append('custom_mode_of_payment')
                    mop.mode_of_payment = mode

        si.custom_distribution_channel = doc.custom_distribution_channel_code
        si.save(ignore_permissions=True)         

        # Check if the Sales Order has custom mode of payment
        if doc.custom_mode_of_payment:
            existing_payment_entries = { (entry.mode_of_payment, entry.amount) for entry in si.get("custom_mode_of_payments", []) }
            for mop in doc.custom_mode_of_payment:
                if hasattr(mop, 'mode_of_payment') and hasattr(mop, 'amount'):
                    mode_of_payment = str(mop.mode_of_payment)
                    amount = min(si.rounded_total, mop.amount)
                    if (mode_of_payment, amount) not in existing_payment_entries:
                        payment_entry = si.append('custom_mode_of_payments')
                        payment_entry.mode_of_payment = mode_of_payment
                        payment_entry.amount = amount

        si.submit()
        return si.name
        
    except Exception as e:
        frappe.log_error(frappe.get_traceback(),(f"Error during Sales Invoice: {str(e)}", "Sales Invoice Error"))
        frappe.throw(f"An error occurred during invoice creation. Please contact support with the following error: {str(e)}")

    # sales_order = frappe.get_doc("Sales Order", sales_order_name)

    # if (sales_order.custom_distribution_channel_code in ['11', '13'] and 
    #     sales_order.custom_multiple_shipment == 1 and 
    #     sales_order.custom_pick_list_status == "Completed"):
    #     # Create the Sales Invoice from the Sales Order
    #     try:
    #         invoice = make_sales_invoice(sales_order.name)
    #         invoice.set_advances()  # Optionally apply advances if applicable
    #         invoice.custom_sales_order = sales_order.name
    #         invoice.insert() 
    #         invoice.submit()
    #         frappe.msgprint(f"Sales Invoice {invoice.name} created and submitted successfully")
    #     except Exception as e:
    #         frappe.throw(f"Failed to create Sales Invoice: {str(e)}")

def adjust_invoice_qty_based_on_pick_list(sales_invoice, sales_order_id):
    """
    Adjust item quantities in the Sales Invoice based on the Pick List.
    """
    pick_list_items = frappe.get_all(
        "Pick List Item",
        filters={"sales_order": sales_order_id},
        fields=["item_code", "picked_qty", "qty", "sales_order", "sales_order_item"]
    )   
    if not pick_list_items:
        frappe.throw(f"No items found in Pick List for Sales Order {sales_order_id}") # same here code for all
    # Create a dictionary from the Pick List items for easy lookup
    pick_list_dict = {(item["item_code"], item["qty"]): item for item in pick_list_items}
    for si_item in sales_invoice.items:
        key = (si_item.item_code, si_item.qty)
        # If the item exists in the Pick List, update the qty
        if key in pick_list_dict:
            pick_item = pick_list_dict[key]
            si_item.qty = pick_item["picked_qty"]
            si_item.sales_order = pick_item["sales_order"]
            si_item.sales_order_item = pick_item["sales_order_item"]
            # Remove the item from pick_list_dict to avoid adding it again later
            pick_list_dict.pop(key)

@frappe.whitelist()
def create_and_submit_payment_entry(docname,row):
    try:
        print(row)
        doc = frappe.get_doc("Sales Order",docname)
        payment_row = doc.custom_mode_of_payment[int(row)-1]
        print(frappe.as_json(payment_row))
        print(payment_row.amount)
        payment_entry = create_and_submit_payment(doc,payment_row.mode_of_payment,payment_row.amount)
        
        payment_row.payment_entry = payment_entry
        payment_row.db_update() 
        print(payment_row.payment_entry)
        doc.reload()
        doc.save()
        # doc.save(update_modified=False)
        return _("Payment Entry created successfully.")
    except Exception as e:
        frappe.throw(_("Error during payment entry invoice creation: {0}").format(str(e)))



def create_and_submit_payment(doc, mode_of_payment, amount):
    """Helper function to create and submit a payment entry."""
    payment = get_payment_entry(doc.doctype, doc.name)
    payment.mode_of_payment = mode_of_payment
    payment.paid_amount = amount
    payment.received_amount = amount
    payment.reference_no = doc.name
    payment.reference_date = today()
    if payment.references and payment.references[0]:
        payment.references[0].allocated_amount = amount
    payment.insert()
    payment.submit()
    return payment.name

@frappe.whitelist()
def custom_set_advances(self):
    """Returns list of advances against Account, Party, Reference"""

    res = self.get_advance_entries(
        include_unallocated=not cint(self.get("custom_only_include_allocated_payments"))
    )

    self.set("custom_advances", [])
    advance_allocated = 0
    for d in res:
        pass


@frappe.whitelist(allow_guest=True)
def get_meta(doctype):
    # Check if the DocType is provided
    if not doctype:
        frappe.throw(_("Please provide a DocType name."), frappe.MandatoryError)

    # Fetch the metadata for the specified DocType
    try:
        meta = frappe.get_meta(doctype)
        fields_info = [field.as_dict() for field in meta.fields]
        return meta.field_order
    except frappe.DoesNotExistError:
        frappe.throw(_("DocType {0} does not exist").format(doctype), frappe.DoesNotExistError)
    except Exception as e:
        frappe.throw(_("An error occurred: {0}").format(str(e)), frappe.InternalServerError)

#  ----------------------------------------------------------------------Need to be removed-----------------------------------------------------------------------------
# @frappe.whitelist()
# def get_discount(doc):
#     doc = json.loads(doc)
#     mongoURL = frappe.db.get_single_value("Jaleel Settings", "mongodb_url")
#     url = mongoURL + "/api/get_discount_item"
#     for key in doc:
#         if key != "customer_group":
#             doc[key] = int(doc[key])


#     payload = json.dumps(doc)
#     headers = {
#         'Content-Type': 'application/json'
#     }

#     response = requests.request("POST", url, headers=headers, data=payload)
#     if response.status_code==200:
#         data = json.loads(response.text)
#         if len(data["message"])>0:
#             return data["message"]["sales_price"]
        
#     else:
#         return None

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_item_uom(doctype,txt,searchfield,start,page_len,filters):
    uoms = frappe.db.sql("""
        SELECT uom
        FROM `tabUOM Conversion Detail`
        WHERE parent = '{item_code}'
    """.format(item_code = filters.get('item_code')))
    return uoms

@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_distribution_channel_based_on_customer(doctype, txt, searchfield, start, page_len, filters):
    customer_id = filters.get('customer')

    customer_doc = frappe.get_doc("Customer" , customer_id)

    # Define the distribution channels to check against
    distribution_channels = ['02', '03', '06', '07', '11', '12', '13', '14']

    # Fetch all valid distribution channels from the master
    master_dccodes = frappe.get_all("Distribution Channel Code", fields=["name"])

    # Convert the list of master dccodes into a set for quick lookup
    valid_master_dccodes = {dccode.name for dccode in master_dccodes}

    # Create a set of existing distribution channels in the customer document
    existing_dccodes = {child.dccode for child in customer_doc.custom_distribution_channel}

    # Loop through the distribution channels and check against both the master and the customer's existing channels
    for dccode in distribution_channels:
        if dccode in valid_master_dccodes and dccode not in existing_dccodes:
            # Append the new distribution channel to the customer's child table
            customer_doc.append('custom_distribution_channel', {
                'dccode': dccode
            })
    customer_doc.save()

    # Fetch the allowed payment modes for the customer
    allowed_payment_modes = frappe.db.sql("""
        SELECT mode_of_payment 
        FROM `tabCustomer Mode of Payment` 
        WHERE parent = %s
    """, (customer_id,), as_dict=True)

    # Check if 'Credit Card' is not in the allowed payment modes
    credit_card_allowed = any(mode.mode_of_payment == 'Credit Card' for mode in allowed_payment_modes)

    # Construct the query to fetch distribution channel codes
    if credit_card_allowed:
        # Include all distribution channel codes
        distribution_channel_query = """
            SELECT dccode 
            FROM `tabDistribution Channel` 
            WHERE parent = %s
            ORDER BY dccode ASC
        """
        distribution_channels = frappe.db.sql(distribution_channel_query, (customer_id,))
    else:
        # Exclude 15 and 16 if Credit Card is not allowed
        distribution_channel_query = """
            SELECT dccode 
            FROM `tabDistribution Channel` 
            WHERE parent = %s AND dccode NOT IN ('15', '16')
            ORDER BY dccode ASC
        """
        distribution_channels = frappe.db.sql(distribution_channel_query, (customer_id,))

    return distribution_channels

# this function will be called at submission of Sales order and will create zone wise picklist or will add locations to items
def create_picklist_zone_wise(doc, method):
    if doc.custom_distribution_channel_code == '02' or doc.custom_distribution_channel_code == '2':
        pass
    else:
        target_doc = None
        PickingPriority = DocType("Picking Priority")
        PickingSequenceConfiguration = DocType("Picking Sequence Configuration")
        
        # Validate Sales Order for reserved stock
        def validate_sales_order():
            so = doc  # Use doc directly
            for item in so.items:
                if item.stock_reserved_qty > 0:
                    frappe.throw(
                        _("Cannot create a pick list for Sales Order {0} because it has reserved stock. Please unreserve the stock in order to create a pick list.").format(frappe.bold(so.name))
                    )
        
        # Update item quantity based on picked qty
        def update_item_quantity(source, target, source_parent):
            picked_qty = flt(source.picked_qty) / (flt(source.conversion_factor) or 1)
            qty_to_be_picked = flt(source.qty) - max(picked_qty, flt(source.delivered_qty))
            target.qty = qty_to_be_picked
            target.stock_qty = qty_to_be_picked * flt(source.conversion_factor)
        
        def update_packed_item_qty(source, target, source_parent) -> None:
            qty = flt(source.qty)
            for item in source_parent.items:
                if source.parent_detail_docname == item.name:
                    picked_qty = flt(item.picked_qty) / (flt(item.conversion_factor) or 1)
                    pending_percent = (item.qty - max(picked_qty, item.delivered_qty)) / item.qty
                    target.qty = target.stock_qty = qty * pending_percent
                    return
        
        # Validate sales order
        validate_sales_order()
        
        # Create a dictionary to store items zone-wise
        pick_lists_zone_wise = {}
        locations = {}
        # initialize document name in filter line number 498
        names={}
        
        for item in doc.items: 
            # Query to get the zone for the item
            query = (
                frappe.qb.from_(PickingPriority)
                .join(PickingSequenceConfiguration)
                .on(PickingPriority.parent == PickingSequenceConfiguration.name)
                .select(PickingSequenceConfiguration.zone,PickingSequenceConfiguration.name,  PickingPriority.location)
                .where(PickingPriority.item_code == item.get("item_code"))
                
                .where(PickingPriority.uom == item.get("uom"))
            )
            
            zone_data = query.run(as_dict=True)
            # If zone data exists, add item to the zone in the dictionary
            if zone_data:
                zone = zone_data[0].get('zone')
                location = zone_data[0].get('location')
                name = zone_data[0].get('name')
                if item.item_code in names:
                        names[item.item_code].append(name)
                else:
                        names[item.item_code] = [name]
                
                if pick_lists_zone_wise.get(zone):
                    pick_lists_zone_wise[zone].append(item)
                    locations[item.item_code] = location
                else:
                    pick_lists_zone_wise[zone] = [item]
                    locations[item.item_code] = location
        # Function to match items more specifically
        def should_pick_order_item(d):
            for item in items:
                if (
                    d.item_code == item.get("item_code")
                    and d.qty == item.get("qty")
                    and d.warehouse == item.get("warehouse")
                    and d.uom == item.get("uom")
                ):
                    return True
            return False
        if doc.custom_multiple_shipment:
            doc.reload()
            for item in doc.items:
                if item.item_code in locations:
                    item.custom_location = locations[item.item_code]
                else:
                    frappe.throw(_("Location not found for item {0}.<br>Please set the location for {0} in Picking Sequence Configuration.").format(frappe.bold(item.item_code)))
            doc.save()
            doc.submit()
            doc.reload()
            # frappe.msgprint(f"Picklist creation skipped for Sales Order {doc.name} due to custom distribution channel code: {doc.custom_distribution_channel_code}")
        else:
            # Now create a Pick List for each zone
            item_codes=[]
            for zone, items in pick_lists_zone_wise.items():
                i=0
                itemcode=[item.get("item_code") for item in items][i]
                item_codes.append(itemcode)
                occurence=item_codes.count(itemcode)
                name_1=names[itemcode][occurence-1]
                
                
                # Retrieve the picking sequence for the current zone
                picking_sequence = frappe.get_all('Picking Priority',filters={'item_code': ['in', [item.get("item_code") for item in items]], 'parenttype': 'Picking Sequence Configuration','parent': name_1},fields=['item_code', 'idx','uom'])
                i=i+1
                sequence_dict = {d.item_code+d.uom: d.idx for d in picking_sequence}
            

                # Assign priority to items or default to a large number for undefined priority
                for item in items:
                    item.idx = sequence_dict.get(item.get("item_code")+item.get("uom"), 99999)

                # Map the Sales Order to Pick List for each zone
                pick_doc = get_mapped_doc(
                    "Sales Order",
                    doc.name,
                    {
                        "Sales Order": {
                            "doctype": "Pick List",
                            "field_map": {"set_warehouse": "parent_warehouse"},
                            "validation": {"docstatus": ["=", 1]},
                        },
                        "Sales Order Item": {
                            "doctype": "Pick List Item",
                            "field_map": {"parent": "sales_order", "name": "sales_order_item" ,"is_free_item": "custom_is_free_item", "pricing_rules": "custom_pricing_rules"},
                            "postprocess": update_item_quantity,
                            "condition": should_pick_order_item,
                        },
                        "Packed Item": {
                            "doctype": "Pick List Item",
                            "field_map": {
                                "parent": "sales_order",
                                "name": "sales_order_item",
                                "parent_detail_docname": "product_bundle_item",
                            },
                            "field_no_map": ["picked_qty"],
                            "postprocess": update_packed_item_qty,
                        },
                    },
                    target_doc,
                )
                # print(frappe.as_json(pick_doc),"hi this is risht")
                if pick_doc:
                    for locate in pick_doc.locations:
                        locate.idx=sequence_dict.get(locate.get("item_code")+locate.get("uom"),99999)
                    pick_doc.locations = sorted((pick_doc.locations), key=lambda x:(x.idx is None, x.idx))


                    # Set the zone for the pick list
                    pick_doc.custom_zone = zone
                    pick_doc.purpose = "Delivery"
                    pick_doc.set_item_locations()
                    if len(pick_doc.as_dict().get("locations", [])) != 0:
                        for locate in pick_doc.locations:
                            if locations[locate.get("item_code")]:
                                locate.custom_location = locations[locate.get("item_code")]
                            else:
                                pass
                        pick_doc.save()

                        # doc.submit()

                        # Print the created pick list for the zone
                        print(f"Created Pick List for Zone {zone}: {doc.name}")

                        frappe.msgprint("Picklists created zone-wise successfully.")
                    else:
                        frappe.thr(f"No Pick List created")
                else:
                    frappe.msgprint(f"No Pick List created")

            create_consolidated_configuration(doc)
            create_pick_list_queue(doc)
            
# def create_consolidated_configuration(doc):
#     picking_details = frappe.db.sql("""
#         SELECT DISTINCT pli.parent AS pick_list, pl.status
#         FROM `tabPick List Item` pli
#         JOIN `tabPick List` pl ON pli.parent = pl.name
#         WHERE pli.sales_order = %s
#     """, doc.name, as_dict=True)
    
#     picking_consolidated = frappe.new_doc("Consolidated Picking") 
#     picking_consolidated.sales_order = doc.name  
#     picking_consolidated.distribution_channel_code=doc.custom_distribution_channel_code 
    
#     for picking_detail in picking_details: 
#         child_row = picking_consolidated.append('consolidated_picking_child', {})
#         child_row.pick_list = picking_detail.get('pick_list')
#         child_row.status = picking_detail.get('status')
    
#     picking_consolidated.insert() 
#     frappe.msgprint("Consolidated Picking is Created Successfully")

# ////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
# def create_consolidated_configuration(doc):
#     picking_details = frappe.db.sql("""
#         SELECT DISTINCT pli.parent AS pick_list, pl.status
#         FROM `tabPick List Item` pli
#         JOIN `tabPick List` pl ON pli.parent = pl.name
#         WHERE pli.sales_order = %s
#     """, doc.name, as_dict=True)
    
#     # Create a new Consolidated Picking document
#     picking_consolidated = frappe.new_doc("Consolidated Picking")
#     picking_consolidated.sales_order = doc.name
#     picking_consolidated.distribution_channel_code = doc.custom_distribution_channel_code
    
#     # Append Pick Lists to the Consolidated Picking
#     for picking_detail in picking_details:
#         child_row = picking_consolidated.append('consolidated_picking_child', {})
#         child_row.pick_list = picking_detail.get('pick_list')
#         child_row.status = picking_detail.get('status')
    
#     # Insert the Consolidated Picking document
#     picking_consolidated.insert()
    
#     # Get the name of the newly created Consolidated Picking
#     consolidated_picking_name = picking_consolidated.name
    
#     # Update each Pick List to reference the new Consolidated Picking
#     for picking_detail in picking_details:
#         pick_list_name = picking_detail.get('pick_list')
#         if pick_list_name:
#             frappe.db.set_value("Pick List", pick_list_name, "custom_consolidated_picking", consolidated_picking_name)
    
#     # Show success message
#     # frappe.msgprint("Consolidated Picking is Created Successfully and linked to Pick Lists.")
# ///////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

def create_consolidated_configuration(doc):
    # Fetch pick list details associated with the Sales Order, including status
    picking_details = frappe.db.sql("""
        SELECT DISTINCT pli.parent AS pick_list, pl.status
        FROM `tabPick List Item` pli
        JOIN `tabPick List` pl ON pli.parent = pl.name
        WHERE pli.sales_order = %s
    """, doc.name, as_dict=True)

    # Create a new Consolidated Picking document
    picking_consolidated = frappe.new_doc("Consolidated Picking")
    picking_consolidated.sales_order = doc.name
    picking_consolidated.distribution_channel_code = doc.custom_distribution_channel_code

    # Append Pick Lists to the Consolidated Picking
    for picking_detail in picking_details:
        child_row = picking_consolidated.append('consolidated_picking_child', {})
        child_row.pick_list = picking_detail.get('pick_list')
        child_row.status = picking_detail.get('status')


    # Insert the Consolidated Picking document
    picking_consolidated.insert()

    # Get the name of the newly created Consolidated Picking
    consolidated_picking_name = picking_consolidated.name

    # Update each Pick List to reference the new Consolidated Picking
    for picking_detail in picking_details:
        pick_list_name = picking_detail.get('pick_list')
        if pick_list_name:
            frappe.db.set_value("Pick List", pick_list_name, "custom_consolidated_picking", consolidated_picking_name)

            # Fetch the Pick List document
            pick_list_doc = frappe.get_doc("Pick List", pick_list_name)

            # Append Pick List items to the Consolidated Picking's child table
            for item in pick_list_doc.locations:
                picking_consolidated.append('consolidated_picking_items', {
                    'item_code': item.item_code,
                    'picklist': pick_list_doc.name,
                    'uom': item.uom,
                    'qty': item.qty,
                    'picked_qty': item.picked_qty,
                    'reason': item.custom_reason_for_short_picking,
                    'status':pick_list_doc.status,
                    'zone':pick_list_doc.custom_zone

                })

    # Save the updated Consolidated Picking with appended items
    picking_consolidated.save()

    # Show success message
    # frappe.msgprint("Consolidated Picking is Created Successfully, linked to Pick Lists, and items are appended.")

@frappe.whitelist()
def create_pick_list_queue(doc):
    pick_list_records =  picking_details = frappe.db.sql("""
        SELECT DISTINCT pli.parent AS pick_list, pl.custom_zone,pl.name, pli.sales_order as sales_order
        FROM `tabPick List Item` pli
        JOIN `tabPick List` pl ON pli.parent = pl.name
        WHERE pli.sales_order = %s
    """, doc.name, as_dict=True)
    pick_list_queue = frappe.new_doc("PickList Print Queue")
    for pick_list in pick_list_records:
        pick_list_queue.pick_list_id = pick_list.get("name")
        pick_list_queue.sales_order = pick_list.get("sales_order")
        pick_list_queue.zone = pick_list.get("custom_zone")
        pick_list_queue.save(ignore_permissions = True)


@frappe.whitelist()
def create_picklists(items, doc):
    try:
        # Convert items and doc to dicts if not already
        items = frappe.parse_json(items)
        doc = frappe.get_doc("Sales Order", doc)
        source_name = doc.name

        # Dictionary to hold items by zone and locations
        pick_lists_zone_wise = {}
        names = {}

        # This will store Sales Order Item row name and Pick List Item row name mappings
        item_row_mapping = {}

        # Define DocType objects
        PickingPriority = DocType("Picking Priority")
        PickingSequenceConfiguration = DocType("Picking Sequence Configuration")

        # Validate Sales Order
        def validate_sales_order():
            so = doc  # Use doc directly
            for item in so.items:
                if item.stock_reserved_qty > 0:
                    frappe.throw(
                        _("Cannot create a pick list for Sales Order {0} because it has reserved stock. Please unreserve the stock in order to create a pick list.").format(frappe.bold(so.name))
                    )

        # Update item quantity based on picked qty
        def update_item_quantity(source, target, source_parent):
            picked_qty = flt(source.picked_qty) / (flt(source.conversion_factor) or 1)
            qty_to_be_picked = flt(source.qty) - max(picked_qty, flt(source.delivered_qty))
            target.qty = qty_to_be_picked
            target.stock_qty = qty_to_be_picked * flt(source.conversion_factor)

        def update_packed_item_qty(source, target, source_parent) -> None:
            qty = flt(source.qty)
            for item in source_parent.items:
                if source.parent_detail_docname == item.name:
                    picked_qty = flt(item.picked_qty) / (flt(item.conversion_factor) or 1)
                    pending_percent = (item.qty - max(picked_qty, item.delivered_qty)) / item.qty
                    target.qty = target.stock_qty = qty * pending_percent
                    return

        # Validate the Sales Order
        validate_sales_order()

        # Query items and group them by zone
        for item in items:
            for docitem in doc.items:
                if item.get("item_code") == docitem.get("item_code") and item.get("uom") == docitem.get("uom"):
                    item_code = item.get("item_code")
                    uom = item.get("uom")

                    # Query to get the zone, location, and name (sequence) for the item
                    query = (
                        frappe.qb.from_(PickingPriority)
                        .join(PickingSequenceConfiguration)
                        .on(PickingPriority.parent == PickingSequenceConfiguration.name)
                        .select(PickingSequenceConfiguration.zone, PickingSequenceConfiguration.name, PickingPriority.location)
                        .where(PickingPriority.item_code == item_code)
                        .where(PickingPriority.uom == uom)
                    )
                    zone_data = query.run(as_dict=True)

                    if zone_data:
                        zone = zone_data[0].get('zone')
                        location = zone_data[0].get('location')
                        name = zone_data[0].get('name')

                        # Store sequence names for each item
                        if item_code in names:
                            names[item_code].append(name)
                        else:
                            names[item_code] = [name]

                        # Group items zone-wise
                        if zone in pick_lists_zone_wise:
                            pick_lists_zone_wise[zone].append(docitem)
                        else:
                            pick_lists_zone_wise[zone] = [docitem]

        def should_pick_order_item(d):
            for item in items:
                if (
                    d.item_code == item.get("item_code")
                    and d.qty == item.get("qty")
                    and d.warehouse == item.get("warehouse")
                    and d.uom == item.get("uom")
                ):
                    return True
            return False

        # Create Pick Lists for each zone
        item_codes = []
        for zone, items in pick_lists_zone_wise.items():
            i = 0
            # Retrieve the first item code for sequence ordering
            item_code = [item.get("item_code") for item in items][i]
            item_codes.append(item_code)
            occurrence = item_codes.count(item_code)
            name_1 = names[item_code][occurrence - 1]

            # Retrieve the picking sequence for the current zone
            picking_sequence = frappe.get_all(
                'Picking Priority',
                filters={
                    'item_code': ['in', [item.get("item_code") for item in items]],
                    'parenttype': 'Picking Sequence Configuration',
                    'parent': name_1
                },
                fields=['item_code', 'idx', 'uom']
            )
            i += 1
            sequence_dict = {d.item_code+d.uom: d.idx for d in picking_sequence}

            # Assign priority to items or default to a large number for undefined priority
            for item in items:
                item.idx = sequence_dict.get(item.get("item_code")+item.get("uom"), 99999)

            # Map Sales Order to Pick List using Frappe's get_mapped_doc function
            pick_list_doc = get_mapped_doc(
                "Sales Order",
                source_name,
                {
                    "Sales Order": {
                        "doctype": "Pick List",
                        "field_map": {"set_warehouse": "parent_warehouse"},
                        "validation": {"docstatus": ["=", 1]},
                    },
                    "Sales Order Item": {
                        "doctype": "Pick List Item",
                        "field_map": {"parent": "sales_order", "name": "sales_order_item"},
                        "postprocess": update_item_quantity,
                        "condition": should_pick_order_item,
                    },
                    "Packed Item": {
                        "doctype": "Pick List Item",
                        "field_map": {
                            "parent": "sales_order",
                            "name": "sales_order_item",
                            "parent_detail_docname": "product_bundle_item",
                        },
                        "field_no_map": ["picked_qty"],
                        "postprocess": update_packed_item_qty,
                    },
                },
                target_doc=None  # Ensure this is initialized with None
            )

            if pick_list_doc:
                # Set the zone for the pick list
                pick_list_doc.purpose = "Delivery"
                pick_list_doc.custom_zone = zone

                # Apply the sequencing logic to locations
                for locate in pick_list_doc.locations:
                    locate.idx = sequence_dict.get(locate.get("item_code")+locate.get("uom"), 99999)

                # Sort the items by sequence index
                pick_list_doc.locations = sorted(pick_list_doc.locations, key=lambda x: (x.idx is None, x.idx))

                # Save the Pick List
                pick_list_doc.save()

                # Map Sales Order Item row name to Pick List Item row name
                for pick_item in pick_list_doc.locations:
                    for docitem in doc.items:
                        if pick_item.item_code == docitem.item_code:
                            item_row_mapping[docitem.name] = pick_item.name
                            break

                # Optionally, submit the Pick List automatically
                # pick_list_doc.submit()

                print(f"Created Pick List for Zone: {zone}")
            else:
                print(f"No Pick List created for Zone: {zone}")

        return {"response": "Pick Lists created successfully.", "item_row_mapping": item_row_mapping}

    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "Create Picklists Error")
        print(e, "Error")
        return str(e)

@frappe.whitelist()
def check_picking_sequence(item_code, uom=None):
    filters = {'item_code': item_code}
    
    if uom:
        filters['uom'] = uom
    
    picking_sequence = frappe.db.get_value('Picking Priority', filters, 'parent')
    
    return bool(picking_sequence)  # Return True if found, otherwise False

# @frappe.whitelist()
# def get_picklists_by_sales_order(sales_order):
#     """
#     Get Pick Lists associated with a given Sales Order.
    
#     Args:
#         sales_order (str): The name of the Sales Order.

#     Returns:
#         list: A list of Pick Lists and their statuses associated with the Sales Order.
#     """
#     # Validate that sales_order is provided
#     if not sales_order:
#         frappe.throw("Sales Order is required.")

#     # Fetch the Pick List Items associated with the Sales Order
#     pick_list_items = frappe.get_all(
#         'Pick List Item',
#         filters={'sales_order': sales_order},
#         fields=['parent']  # Get the parent Pick List name
#     )

#     if not pick_list_items:
#         return []

#     # Extract unique Pick List names
#     pick_list_names = set(item['parent'] for item in pick_list_items)

#     # Fetch the Pick Lists by names
#     pick_lists = frappe.get_all(
#         'Pick List',
#         filters={'name': ['in', list(pick_list_names)]},
#         fields=['name', 'status']  # Get the Pick List name and status
#     )

#     return pick_lists

@frappe.whitelist()
def get_customer_mode_of_payment(customer_id):
    # Fetch Customer document
    customer = frappe.get_doc("Customer", customer_id)
    
    # Assuming mode_of_payment is the multiselect field name in Customer
    if customer.custom_mode_of_payment:
        mode_of_payments = customer.custom_mode_of_payment
        return mode_of_payments  # Return the mode of payment to client-side
    else:
        frappe.throw(_("Mode of Payment Not found in the customer {}.").format(frappe.bold(customer_id)))

@frappe.whitelist()
def get_reserved_available_qty(row):
    row = json.loads(row)

    # Convert dictionary to an object with attributes (like item_code, warehouse)
    row_obj = SimpleNamespace(**row)

    bin_id = frappe.db.get_value("Reserved Bin", {"item_code": row_obj.item_code, "warehouse": row_obj.warehouse})

    if not bin_id:
        bin_id = create_reserve_bin(row_obj)  # Pass object-like structure

    doc = frappe.get_doc("Reserved Bin", bin_id)

    available_qty = doc.available_qty or 0 
    
    return available_qty  




@frappe.whitelist()
def get_mongodb_url():
    try:
        jaleel_settings = frappe.get_single("Jaleel Settings")
        return {"mongodburl": jaleel_settings.mongodb_url}
    except Exception as e:
        return {"error": str(e)}

@frappe.whitelist()
def validate_zero_rate_items(doc, method):
    zero_rate_items = []

    for item in doc.items:
        if item.rate == 0 and item.is_free_item == 0:
            zero_rate_items.append(item.item_code)

    if zero_rate_items:
        item_names = ", ".join(zero_rate_items)
        frappe.throw(_("The following items have a rate of 0: {0}").format(item_names))
        

@frappe.whitelist()
def get_foc_items(item_code=None, customer=None, customer_group=None, site=None, item_grp=None, brnd=None, item_category=None,
                  apply_on="Item Code", applicable_for="Customer", dc=None, company=None, sales_organization_code=None, customer_hierarchy=None, has_priority=0):
    
    current_date = frappe.utils.nowdate()

    query = """
        SELECT 
            pr.name AS pricing_rule_name, pri.item_code,
            pr.free_qty,
            pr.min_qty,
            pr.free_item,
            pr.priority
        FROM 
            `tabFOC` pr 
        INNER JOIN 
            `tabFOC Item` pri ON pri.parent = pr.name
        LEFT JOIN 
            `tabHierarchy Combination` hc ON hc.parent = pr.name
        WHERE 
            pr.disable = 0 
            AND pr.price_or_product_discount = 'Product' 
            AND %(current_date)s BETWEEN pr.valid_from AND pr.valid_upto
    """

    # Apply conditions based on 'apply_on' field
    if apply_on == "Item Code":
        query += " OR pri.item_code = %(item_code)s"
    elif apply_on == "Item Group":
        query += " OR pri.item_group = %(item_grp)s"
    elif apply_on == "Brand":
        query += " OR pri.brand = %(brnd)s"
    elif apply_on == "Item Category":
        query += " OR pri.item_category = %(item_category)s"

    # Apply conditions based on 'applicable_for' field
    if applicable_for == "Customer":
        query += " OR pr.customer = %(customer)s"
    elif applicable_for == "Customer Group":
        query += " OR pr.customer_group = %(customer_group)s"
    elif applicable_for == "Site":
        query += " OR pr.site = %(site)s"

    # Check Hierarchy Combination fields
    if company:
        query += " AND hc.company_code = %(company)s"
    if sales_organization_code:
        query += " AND hc.sales_organization = %(sales_organization_code)s"
    if dc:
        query += " AND hc.distribution_channel = %(dc)s"
    if site:
        query += " AND hc.site = %(site)s"
    if customer_hierarchy:
        query += " AND hc.customer_hierarchy = %(customer_hierarchy)s"
    if customer_group:
        query += " AND hc.customer_group = %(customer_group)s"

    if int(has_priority) == 1: 
        query += " ORDER BY pr.priority ASC, pr.modified DESC"


    query += " LIMIT 1"

    params = {
        "current_date": current_date,
        "item_code": item_code,
        "item_grp": item_grp,
        "brnd": brnd,
        "item_category": item_category,
        "customer": customer,
        "customer_group": customer_group,
        "site": site,
        "dc": dc,
        "company": company,
        "sales_organization_code": sales_organization_code,
        "customer_hierarchy": customer_hierarchy
    }

    pricing_rules = frappe.db.sql(query, params, as_dict=True)
    return pricing_rules if pricing_rules else None


@frappe.whitelist()
def fetch_foc_for_recursive(item_code, qty, items, custom_foc_reference, customer=None, customer_group=None, site=None, item_grp=None, brnd=None, item_category=None,
                            apply_on="Item Code", applicable_for="Customer", dc=None, company=None, sales_organization_code=None, customer_hierarchy=None, has_priority=0):
    try:
        items = json.loads(items)
        custom_foc_reference = json.loads(custom_foc_reference)
    except json.JSONDecodeError as e:
        frappe.throw(f"Error decoding JSON: {e}")
            
            
    current_date = frappe.utils.nowdate()


    query = """
        SELECT 
            pr.name AS pricing_rule_name,
            pr.recurse_for,
            pr.free_qty,
            pr.min_qty,
            pr.free_item,
            pr.priority
        FROM 
            `tabFOC` pr 
        INNER JOIN 
            `tabFOC Item` pri ON pri.parent = pr.name
        LEFT JOIN 
            `tabHierarchy Combination` hc ON hc.parent = pr.name
        WHERE 
            pr.disable = 0 
            AND pr.price_or_product_discount = 'Product' 
            AND %(current_date)s BETWEEN pr.valid_from AND pr.valid_upto AND pr.is_recursive =  1
    """

    if apply_on == "Item Code":
        query += " OR pri.item_code = %(item_code)s"
    elif apply_on == "Item Group":
        query += " OR pri.item_group = %(item_grp)s"
    elif apply_on == "Brand":
        query += " OR pri.brand = %(brnd)s"
    elif apply_on == "Item Category":
        query += " OR pri.item_category = %(item_category)s"

    # Apply conditions based on 'applicable_for' field
    if applicable_for == "Customer":
        query += " OR pr.customer = %(customer)s"
    elif applicable_for == "Customer Group":
        query += " OR pr.customer_group = %(customer_group)s"
    elif applicable_for == "Site":
        query += " OR pr.site = %(site)s"

    # Check Hierarchy Combination fields
    if company:
        query += " AND hc.company_code = %(company)s"
    if sales_organization_code:
        query += " AND hc.sales_organization = %(sales_organization_code)s"
    if dc:
        query += " AND hc.distribution_channel = %(dc)s"
    if site:
        query += " AND hc.site = %(site)s"
    if customer_hierarchy:
        query += " AND hc.customer_hierarchy = %(customer_hierarchy)s"
    if customer_group:
        query += " AND hc.customer_group = %(customer_group)s"

    if int(has_priority) == 1: 
        query += " ORDER BY pr.priority ASC, pr.modified DESC"


    query += " LIMIT 1"

    params = {
        "current_date":current_date,
        "item_code": item_code,
        "item_grp": item_grp,
        "brnd": brnd,
        "item_category": item_category,
        "customer": customer,
        "customer_group": customer_group,
        "site": site,
        "dc": dc,
        "company": company,
        "sales_organization_code": sales_organization_code,
        "customer_hierarchy": customer_hierarchy
    }

    foc_items = frappe.db.sql(query, params, as_dict=True)
    if foc_items:
        for foc_item in foc_items:
            free_item_code = foc_item["free_item"]
            max_allowed_free_qty = foc_item["free_qty"]
            foc_rule_name = foc_item["pricing_rule_name"]
            recurse_for = foc_item["min_qty"]
            parent_qty = float(qty or 0.0)
            max_allowed = math.floor(parent_qty / recurse_for)

            existing_free_item = next((item for item in items if item["item_code"] == free_item_code and item.get("is_free_item")), None)
            existing_parent_item = next((item for item in custom_foc_reference if item["item_code"] == item_code), None)
        
            if existing_free_item and existing_parent_item:
                existing_free_item["qty"] = max_allowed
            elif parent_qty >= recurse_for:
                items.append({
                    "item_code": free_item_code,
                    "qty": max_allowed,
                    "is_free_item": 1,
                    "pricing_rules": foc_rule_name,
                    "rate": 0.0,
                    "amount": 0.0,
                    "description": f"Free item as per FOC rule {foc_rule_name}",
                    "delivery_date": frappe.utils.nowdate()
                })

                custom_foc_reference.append({
                    "pricing_rule": foc_rule_name,
                    "item_code": item_code,
                    "rule_applied": 1,
                })
    else:
        pass

    return {
        "items": items,
        "custom_foc_reference": custom_foc_reference,
    }

