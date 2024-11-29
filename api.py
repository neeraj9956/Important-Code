import frappe
import json
from frappe.exceptions import DoesNotExistError, ValidationError, MandatoryError

@frappe.whitelist(allow_guest=True)
def create_purchase_order(data):
    # Parse the JSON data if it is in string format
    if isinstance(data, str):
        data = json.loads(data)
        
    results = []
    
    if not data:
        frappe.local.response['http_status_code'] = 400
        results.append({"message": "No Purchase Order data provided", "status": "error"})
        return results

    for order in data:
        try:
            # Extract the purchase order name if available
            purchase_order_name = order.get("name")
            
            # Check if the purchase order exists
            if purchase_order_name and frappe.db.exists("Purchase Order", purchase_order_name):
                po_doc = frappe.get_doc("Purchase Order", purchase_order_name)
                po_doc.update(order)  # Update the Purchase Order document with the new data
                po_doc.save(ignore_permissions=True)
                action = "updated"
            else:
                # Create a new Purchase Order document
                po_doc = frappe.get_doc({
                    "doctype": "Purchase Order",
                    **order
                })
                po_doc.insert(ignore_permissions=True)
                po_doc.submit()
                action = "created"
            
            results.append({
                "message": f"Purchase Order {action} successfully",
                "purchase_order_id": po_doc.name,
                "status": "success"
            })
            
        except MandatoryError as e:
            frappe.log_error(message=str(e), title="Purchase Order Creation or Update Error")
            frappe.local.response['http_status_code'] = 404
            results.append({
                "message": "Mandatory field missing / Not Found, Value Missing",
                "error": str(e),
                "status": "error"
            })
        
        except DoesNotExistError as e:
            frappe.log_error(message=str(e), title="Purchase Order Creation or Update Error")
            frappe.local.response['http_status_code'] = 400
            results.append({
                "message": "Resource not found",
                "error": str(e),
                "status": "error"
            })
        
        except Exception as e:
            # Log error and append to results if there's an issue
            frappe.log_error(message=str(e), title="Purchase Order Creation or Update Error")
            results.append({
                "message": "Error processing Purchase Order",
                "purchase_order_id": purchase_order_name if purchase_order_name else "New",
                "error": str(e),
                "status": "error"
            })

    return results



import requests
import frappe
import json
from frappe import _
import json
from frappe.utils import cint
STANDARD_USERS = ("Guest", "Administrator")
from frappe.rate_limiter import rate_limit
from frappe.utils.password import get_password_reset_limit
from frappe.utils import (cint,get_formatted_email, nowdate, nowtime, flt, now_datetime)
from erpnext.accounts.utils import get_balance_on
from erpnext.stock.utils import get_stock_balance
from erpnext.stock.stock_ledger import get_previous_sle, get_stock_ledger_entries
from erpnext.selling.doctype.sales_order.sales_order import make_sales_invoice
from frappe.utils import add_to_date, now
from getpos.controllers import frappe_response
from erpnext.selling.doctype.customer.customer import get_customer_outstanding
from frappe.core.doctype.user.user import check_password
from getpos.controllers import frappe_response,handle_exception





@frappe.whitelist( allow_guest=True )
def login(usr, pwd):
    try:
        login_manager = frappe.auth.LoginManager()
        login_manager.authenticate(user=usr, pwd=pwd)
        login_manager.post_login()

        user = frappe.get_doc('User', frappe.session.user)
        
        if user.api_key and user.api_secret:
                user.api_secret = user.get_password('api_secret')
        else:
                api_generate = generate_keys(frappe.session.user)     


        frappe.response["message"] = {
                "success_key":1,
                "message":"success",
                "sid":frappe.session.sid,
                "api_key":user.api_key if user.api_key else api_generate[1],
                "api_secret": user.api_secret if user.api_secret else api_generate[0],
                "username":user.username,
                "email":user.email
        }
    except Exception as e:
        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key":0,
            "message":"Incorrect username or password",
            "error":e
        }
        
        return 


def generate_keys(user):
    user_details = frappe.get_doc('User', user)
    api_secret = frappe.generate_hash(length=15)

    # if not user_details.api_key:
    api_key = frappe.generate_hash(length=15)
    user_details.api_key = api_key

    user_details.api_secret = api_secret
    user_details.save(ignore_permissions=True)

    if frappe.request.method == "GET":
        frappe.db.commit()
    

    return user_details.get_password("api_secret"), user_details.api_key
       


@frappe.whitelist(allow_guest=True)
@rate_limit(key='user', limit=get_password_reset_limit, seconds = 24*60*60, methods=['POST'])
def forgot_password(user):
        if user=="Administrator":
                return 'not allowed'

        try:
                user = frappe.get_doc("User", user)
                if not user.enabled:
                        return 'disabled'

                user.validate_reset_password()
                reset_password(user,send_email=True)

                return  {
                        "success_key":1,
                        "message":"Password reset instructions have been sent to your email"
                        }
                
        except frappe.DoesNotExistError:
                frappe.clear_messages()
                del frappe.local.response["exc_type"]
                frappe.local.response["message"] = {
                        "success_key":0,
                        "message":"User not found"
                        }
from frappe.utils.data import sha256_hash
@frappe.whitelist(allow_guest=True)
def reset_password( user,send_email=False, password_expired=False):
                from frappe.utils import random_string, get_url

                # key = random_string(32)
                key = frappe.generate_hash()
                hashed_key = sha256_hash(key)
                user.db_set("reset_password_key", hashed_key)
                user.db_set("last_reset_password_key_generated_on", now_datetime())

                url = "/update-password?key=" + key
                if password_expired:
                        url = "/update-password?key=" + key + '&password_expired=true'

                link = get_url(url)
                if send_email:
                        password_reset_mail(user,link)
                return link

@frappe.whitelist( allow_guest=True )
def password_reset_mail(user, link):
                send_login_mail_2(user,("Password Reset"),
                        "reset_password", {"link": link}, now=True)

@frappe.whitelist()
def change_password(new_password,re_enter_password,current_password):
    try:
        user=frappe.get_doc("User",frappe.session.user)
        if not new_password ==re_enter_password:
            frappe.clear_messages()
            frappe.local.response["message"] = {
                "success_key": 0,
                "message": "New Password and confirm password are not same"
            }
            frappe.local.response["http_status_code"] = 403    
        elif check_password(user.name,current_password, delete_tracker_cache=False):
            user.new_password = new_password
            user.flags.ignore_password_policy = True
            user.save()
            frappe.clear_messages()
            frappe.local.response["message"] = {
                "success_key": 1,
                "message": "Password changed successfully"
            }
            frappe.local.response["http_status_code"] = 200
    except Exception as e:
        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": "Please enter valid password"
        }
        frappe.local.response["http_status_code"] = 403  

@frappe.whitelist( allow_guest=True )                
def send_login_mail_2(user, subject, template, add_args, now=None):
                """send mail with login details"""
                from frappe.utils.user import get_user_fullname
                from frappe.utils import get_url

                created_by = get_user_fullname(frappe.session['user'])
                if created_by == "Guest":
                        created_by = "Administrator"

                args = {
                        'first_name': user.first_name or user.last_name or "user",
                        'user': user.name,
                        'title': subject,
                        'login_url': get_url(),
                        'created_by': created_by
                }

                args.update(add_args)

                sender = frappe.session.user not in STANDARD_USERS and get_formatted_email(frappe.session.user) or None

                frappe.sendmail(recipients=user.email, sender=sender, subject = subject ,template= template , args = args, delayed=False)


@frappe.whitelist(allow_guest=True)
def get_abbr(string):
    abbr = ''.join(c[0] for c in string.split()).upper()
    return abbr

@frappe.whitelist(allow_guest=True)
def terms_and_conditions():
        terms_and_condition = frappe.db.sql("""
                SELECT terms
                FROM `tabTerms and Conditions`
                WHERE disabled = 0
        """)[0][0]
        return terms_and_condition


@frappe.whitelist(allow_guest=True)
def privacy_policy_and_terms():
        privacy_policy_and_terms = frappe.db.sql("""
                SELECT privacy_policy,terms_and_conditions
                FROM `tabPrivacy Policy and Terms`
                WHERE disabled = 0
        """)
        res = {"success_key":1,
                "message":"success",
                "Privacy_Policy":privacy_policy_and_terms[0][0],
                "Terms_and_Conditions":privacy_policy_and_terms[0][1]}
        if res["Privacy_Policy"]=="" or res["Terms_and_Conditions"]=="":
                return {
            "success_key":0,
            "message":"no value found for privacy policy and terms"
        }
        return res

@frappe.whitelist()
def get_customer_list_by_hubmanager(hub_manager, last_sync = None):
        res = frappe._dict()
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        filters = {'hub_manager': hub_manager, "base_url": base_url}
        conditions = "hub_manager = %(hub_manager)s "
        if last_sync:
                filters['last_sync'] = last_sync
                conditions += "and modified >= %(last_sync)s"
        customer_list = frappe.db.sql("""
                SELECT
                        customer_name, email_id, mobile_no,
                        ward, ward_name, name, creation,
                        modified,disabled,
                        if((image = null or image = ''), null, 
                        if(image LIKE 'http%%', image, concat(%(base_url)s, image))) as image,loyalty_program
                FROM `tabCustomer`
                WHERE {conditions}
                """.format(conditions=conditions), values=filters, as_dict=1)
        if len(customer_list) == 0:
                frappe.clear_messages()
                frappe.local.response["message"] = {
                        "success_key":1,
                        "message":"No values found for this hub manager"
                        }
        else:
                res["success_key"] = 1
                res["message"] = "success"
                res["customer_list"] = customer_list          
                return res 

# Not using for Mobile App
@frappe.whitelist()
def get_item_list_by_hubmanager(hub_manager, last_sync = None):
        res = frappe._dict()
        item_list_based_stock_sync = []
        if last_sync:
                arr =last_sync.split(" ")
                last_sync_date = arr[0]
                if len(arr) < 2:
                        last_sync_time = '00:00:00'
                else:
                        last_sync_time = arr[1]
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        filters = {'hub_manager': hub_manager, "base_url": base_url}
        conditions = "h.hub_manager = %(hub_manager)s "
        item_list = get_item_list(filters, conditions)
        for item in item_list:
                if last_sync:
                        stock_detail = get_item_stock_balance(hub_manager, item.item_code, last_sync_date, last_sync_time)
                        if stock_detail:
                                item_list_based_stock_sync.append(item)
                else:
                        stock_detail = get_item_stock_balance(hub_manager, item.item_code)
                        item.available_qty = stock_detail.get("available_qty")
                        item.stock_modified = str(stock_detail.get("posting_date"))+" "+str(stock_detail.get("posting_time"))
        if last_sync:
                filters['last_sync'] = last_sync
                conditions += "and (i.modified >= %(last_sync)s or p.modified >= %(last_sync)s)"
                item_list_syn_based = get_item_list(filters, conditions)
                for i in item_list_based_stock_sync:
                        if i in item_list_syn_based:
                                item_list_syn_based.remove(i)
                item_list = item_list_based_stock_sync + item_list_syn_based
                for item in item_list:
                        stock_detail = get_item_stock_balance(hub_manager, item.item_code)
                        item.available_qty = stock_detail.get("available_qty")
                        item.stock_modified = str(stock_detail.get("posting_date"))+" "+str(stock_detail.get("posting_time"))
                if len(item_list) == 0:
                        frappe.clear_messages()
                        frappe.local.response["message"] = {
                                "success_key":1,
                                "message":"No values found for this hub manager"
                        }
                else:
                        res["success_key"] = 1
                        res["message"] = "success"
                        res["item_list"] = item_list 
                        return res        
        else:
                if len(item_list) == 0:
                        frappe.clear_messages()
                        frappe.local.response["message"] = {
                                "success_key":1,
                                "message":"No values found for this hub manager"
                        }
                else:
                        res["success_key"] = 1
                        res["message"] = "success"
                        res["item_list"] = item_list
                        return res 

@frappe.whitelist()
def get_item_list(filters, conditions, item_code = None):
        return frappe.db.sql("""
                SELECT 
                        i.item_code, i.item_name, i.item_group, i.description,
                        i.has_variants, i.variant_based_on,
                        if((i.image = null or image = ''), null, 
                        if(i.image LIKE 'http%%', i.image, concat(%(base_url)s, i.image))) as image,
                        p.price_list_rate, i.modified as item_modified, p.modified as price_modified 
                FROM `tabItem` i, `tabHub Manager Detail` h,`tabItem Price` p
                WHERE   h.parent = i.name and h.parenttype = 'Item' 
                        and p.item_code = i.name and p.selling =1
                        and p.price_list_rate > 0 
                        and {conditions}
        """.format(conditions=conditions), values=filters, as_dict=1)
        
        
        
@frappe.whitelist()
def get_details_by_hubmanager(hub_manager):
    try:
        res = frappe._dict()
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        filters = {'hub_manager': hub_manager, "base_url": base_url}
        currency = frappe.get_doc("Global Defaults").default_currency
        currency_symbol=frappe.get_doc("Currency",currency).symbol
        conditions = "email = %(hub_manager)s "
        hub_manager_detail = frappe.db.sql("""
                SELECT
                        u.name, u.full_name,
                        u.email , if(u.mobile_no,u.mobile_no,'') as mobile_no,
                        if(u.user_image, if(u.user_image LIKE 'http%%', u.user_image, concat(%(base_url)s, u.user_image)), '') as image
                FROM `tabUser` u
                WHERE
                {conditions}
                """.format(conditions=conditions), values=filters, as_dict=1)
        cash_balance = get_balance(hub_manager)
        last_txn_date = get_last_transaction_date(hub_manager)
       
        res["success_key"] = 1
        res["message"] = "success"
        res["name"] = hub_manager_detail[0]["name"]
        res["full_name"] = hub_manager_detail[0]["full_name"]
        res["email"] = hub_manager_detail[0]["email"]
        res["mobile_no"] = hub_manager_detail[0]["mobile_no"]
        res["hub_manager"] = hub_manager_detail[0]["name"]
        res["series"] = ""
        res["image"] = hub_manager_detail[0]["image"]
        res["app_currency"] = currency_symbol
        res["balance"] = cash_balance
        res["last_transaction_date"] =  last_txn_date if last_txn_date else ''
        res["wards"] = []
   
        return res
    except Exception as e:
        frappe.clear_messages()
        frappe.local.response["message"] = {
                "success_key":0,
                "message":"No values found for this hub manager"
        }



@frappe.whitelist()
def get_balance(hub_manager):
        account = frappe.db.get_value('Account', {'hub_manager': hub_manager}, 'name')
        account_balance = get_balance_on(account)
        return account_balance if account_balance else 0.0



def add_items_in_order(sales_order, items, order_list):
        sales_taxes = {}
        for item in items:
                item_tax_template = ""
                if item.get('tax'):
                        item_tax_template = item.get('tax')[0].get('item_tax_template')
                        for tax in item.get('tax'):
                                if sales_taxes.get(tax.get('tax_type')):
                                        tax_amount = tax.get('tax_amount') if tax.get('tax_amount') is not None else 0.0
                                        sales_taxes[f"{tax.get('tax_type')}"] = flt(sales_taxes[f"{tax.get('tax_type')}"]) + flt(tax_amount)

                                else:
                                        sales_taxes.update({f"{tax.get('tax_type')}": tax.get('tax_amount')})

                sales_order.append("items", {
                        "item_code": item.get("item_code"),
                        "qty": item.get("qty"),
                        "rate": item.get("rate"), 
                        "discount_percentage":100 if item.get("rate")==0 else 0,  
                        "custom_parent_item":item.get("custom_parent_item"),
                        "custom_is_attribute_item":item.get("custom_is_attribute_item"),
                        "custom_is_combo_item":item.get("custom_is_combo_item"),
                        "allow_zero_evaluation_rate":item.get("allow_zero_evaluation_rate"),                    
                        "item_tax_template": item_tax_template if item_tax_template else "",
                        "custom_ca_id":item.get("custom_ca_id")                
                })
        
        for key,value in sales_taxes.items():
               sales_order.append("taxes", {"charge_type": "Actual", "account_head": key, "tax_amount": value, "description": key, })


        if order_list.get('tax'):
               for tax in order_list.get('tax'):
                        sales_order.append("taxes", {"charge_type": "Actual", "account_head": tax.get('tax_type'), "tax_amount": tax.get('tax_amount'),
                                                      "description": tax.get('tax_type'), "rate": tax.get('tax_rate')})
        
         

        return sales_order


# def add_taxes(doc):
#         all_taxes = frappe.get_all('Account',filters={'account_name':["in",["Output Tax SGST","Output Tax CGST"]]},
#                                 fields=['name','account_name'])
#         if all_taxes:
#                 for tax in all_taxes:
#                         doc.append('taxes',{'charge_type':'On Net Total',
#                                         'account_head': tax.name,
#                                         'rate':0,
#                                         'cost_center':'Main - NP',
#                                         'description': tax.account_name
#                                         })
#         return doc
        
def get_item_tax_template(name):
    filters={'name': name}
    tax = frappe.db.sql("""
    SELECT
        it.item_tax_template
    FROM `tabItem` i , `tabItem Tax` it
    WHERE i.name = it.parent and i.name = %(name)s
    """,values=filters ,  as_dict = True)
    if tax:
        return tax
    else: 
        return []

def get_combo_items(name):
        combo_items = frappe.db.sql(''' Select 
        pi.parent_item,
        pi.item_code , 
        pi.item_name ,
        pi.qty , 
        pi.uom
        from `tabSales Order` so , `tabPacked Item`  pi
        Where 
        so.name = %s and
        so.name = pi.parent
        ''',(name), as_dict = True)
     
        return combo_items
        
@frappe.whitelist()
def get_sales_order_list(hub_manager=None, page_no=1, from_date=None, to_date=None, mobile_no=None,docstatus=None):
        res = frappe._dict()
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        sales_history_count = cint(frappe.db.get_single_value('nbpos Setting', 'sales_history_count'))
        limit = sales_history_count
        conditions = ""

        if mobile_no:
                conditions+=f" and s.contact_mobile LIKE '%{str(mobile_no).strip()}%'"

        if from_date and to_date:
                conditions+=f" and s.transaction_date BETWEEN {frappe.db.escape(from_date)} AND {frappe.db.escape(to_date)}"
        if docstatus:
                 conditions+="and s.docstatus={} ".format(docstatus)


        page_no = cint(page_no) - 1  
        row_no = page_no * limit
        conditions+=(f"ORDER BY s.creation DESC LIMIT {row_no}, {limit}")
       
        order_list = frappe.db.sql(f"""
        SELECT 
                s.name,s.docstatus, s.cost_center, s.transaction_date, 
                TIME_FORMAT(s.transaction_time, '%T') AS transaction_time, 
                s.ward, s.customer, s.customer_name, 
                s.total, s.order_type, s.custom_order_service_type, 
                s.custom_order_request,
                s.custom_table_no, s.total_taxes_and_charges, 
                s.grand_total, s.mode_of_payment, 
                s.mpesa_no, s.contact_display AS contact_name,
                s.contact_phone, s.contact_mobile, s.contact_email,
                s.creation, s.loyalty_points, s.loyalty_amount,
                s.discount_amount, s.additional_discount_percentage AS discount,
                s.custom_redemption_account, s.coupon_code,
                u.full_name AS hub_manager_name,
                IF(c.image IS NULL OR c.image = '', NULL, 
                IF(c.image LIKE 'http%%', c.image, CONCAT('{base_url}', c.image))) AS image
        FROM `tabSales Order` s
        JOIN `tabUser` u ON s.hub_manager = u.name
        JOIN `tabCustomer` c ON s.customer = c.name 
        WHERE s.hub_manager = {frappe.db.escape(hub_manager)}
        {conditions} 
        """, as_dict=True)

        for item in order_list:
                if item.cost_center:
                        item['service_charge'] = frappe.db.get_value("Cost Center", item.cost_center, 'custom_service_charge')
                        service_charge_amount = frappe.db.sql("""
                        SELECT  stc.tax_amount  from `tabSales Order` so ,`tabSales Taxes and Charges` stc WHERE stc.parent=so.name and stc.charge_type="On Previous Row Total" and so.name = '{0}'
                        """.format(item.name),as_dict=1)
                        if service_charge_amount:
                                item['service_charge_amount'] = service_charge_amount[0]['tax_amount']
                status_result = frappe.db.sql(f"""
                SELECT si.status 
                FROM `tabSales Invoice` si 
                JOIN `tabSales Invoice Item` sii ON sii.parent = si.name 
                WHERE sii.sales_order = '{item.name}' 
                ORDER BY si.creation DESC 
                LIMIT 1
                """, as_dict=True)

                item['status'] = status_result[0]['status'] if status_result else "Sales Invoice is not created"

                item_details = frappe.db.sql(f"""
                SELECT
                        so.item_code, so.item_name, so.qty,
                        so.uom, so.rate, so.amount,
                        IF(i.image IS NULL OR i.image = '', NULL, 
                        IF(i.image LIKE 'http%%', i.image, CONCAT(%s, i.image))) AS image
                FROM `tabSales Order Item` so
                JOIN `tabSales Order` s ON so.parent = s.name
                JOIN `tabItem` i ON so.item_code = i.item_code 
                WHERE so.parent = %s 
                AND so.parenttype = 'Sales Order' 
                AND so.item_code != "Service Charge" 
                AND so.associated_item IS NULL
                """, (base_url, item.name), as_dict=True)
                
                associate_items = get_sub_items(item.name)
                new_item_details = []
                if associate_items:
                        for so_item in item_details :
                                so_item['sub_items'] = list(filter( lambda x : x.get("associated_item")== so_item.get("item_code"), associate_items  ) )
                                
                                new_item_details.append(so_item)


                combo_items = get_combo_items(item.name)

                for so_item in item_details:
                        so_item["combo_items"] = [x for x in combo_items if x.get("parent_item") == so_item.item_code]

                        item['items'] = item_details

        if mobile_no:
                number_of_orders = frappe.db.count('Sales Order', filters={
                'hub_manager': hub_manager,
                'contact_mobile': ('like', f'%{str(mobile_no).strip()}%')
                })
        else:
                number_of_orders = get_sales_order_count(hub_manager)

        number_of_orders = len(order_list) if from_date else number_of_orders

        if not order_list and number_of_orders == 0:
                frappe.clear_messages()
                res["message"] = "No values found for this hub manager."
                res["success_key"] = 1
        else:
                res["success_key"] = 1
                res["message"] = "Success"
                res['order_list'] = order_list
                res['number_of_orders'] = number_of_orders

        return res

       



@frappe.whitelist()
def get_sales_order_count(hub_manager):
        number_of_orders = frappe.db.sql("""
                SELECT 
                        count(s.name)
                FROM `tabSales Order` s, `tabUser` u
                WHERE s.hub_manager = u.name and s.hub_manager = %s
                        and s.docstatus = 1 
                        order by s.creation desc
        """, (hub_manager))[0][0]
        return number_of_orders




@frappe.whitelist()
def get_last_transaction_date(hub_manager):
        account = frappe.db.get_value('Account', {'hub_manager': hub_manager, 'disabled': 0}, 'name')
        transaction_date = frappe.db.get_list("GL Entry",
                        filters={
                                'account': account,
                                'voucher_type': ["!=",'Period Closing Voucher'],
                                'is_cancelled': 0
                        },
                        fields= ['posting_date'],
                        order_by = "posting_date desc",
                        as_list = 1
        )
        if transaction_date:
                transaction_date = transaction_date[0][0]
        else:
                transaction_date = None
        return transaction_date

@frappe.whitelist()
def get_item_stock_balance(hub_manager, item_code, last_sync_date=None, last_sync_time="00:00"):
        res = frappe._dict()
        warehouse = frappe.db.get_value('Warehouse', {'hub_manager': hub_manager}, 'name')
        if last_sync_date and last_sync_time:
                args = {
		"item_code": item_code,
		"warehouse":warehouse,
		"posting_date": last_sync_date,
		"posting_time": last_sync_time
                }
                last_entry = get_stock_ledger_entries(args, ">", "desc", "limit 1", for_update=False, check_serial_no=False)
                if last_entry:
                        res['available_qty'] = get_stock_balance(item_code, warehouse, last_entry[0].posting_date, last_entry[0].posting_time)
                        res['posting_date'] = last_entry[0].posting_date
                        res['posting_time'] = last_entry[0].posting_time

        else:
                res['available_qty'] = get_stock_balance(item_code, warehouse)
                args = {
		"item_code": item_code,
		"warehouse":warehouse,
		"posting_date": nowdate(),
		"posting_time": nowtime()
                }
                last_entry = get_previous_sle(args)
                if last_entry:
                        res['posting_date'] = last_entry.get("posting_date")
                        res['posting_time'] = last_entry.get("posting_time")
        
        return res

@frappe.whitelist()
def get_customer(mobile_no=None):
        res=frappe._dict()
        sql = frappe.db.sql(""" SELECT EXISTS(SELECT * FROM `tabCustomer` where mobile_no = '{0}')""".format(mobile_no))
        result = sql[0][0]
        if result == 1:
                customer_detail = frappe.db.sql("""SELECT name,customer_name,customer_primary_contact,
                        mobile_no,email_id,primary_address,hub_manager,loyalty_program FROM `tabCustomer` WHERE 
                        mobile_no = '{0}'""".format(mobile_no),as_dict=True)
                
                loyalty_point_details = frappe._dict(
                frappe.get_all(
                        "Loyalty Point Entry",
                        filters={
                        "customer": customer_detail[0]['name'],
                        "expiry_date": (">=", frappe.utils.getdate()),
                        },
                        group_by="company",
                        fields=["company", "sum(loyalty_points) as loyalty_points"],
                        as_list=1,
                )
                )
                companies = frappe.get_all(
                "Sales Invoice", filters={"docstatus": 1, "customer": customer_detail[0]['name']}, distinct=1, fields=["company"]
                )
                loyalty_points = 0
                for d in companies:
                        if loyalty_point_details:
                                loyalty_points = loyalty_point_details.get(d.company)

                conversion_factor = None
                if customer_detail:
                        conversion_factor = frappe.db.get_value(
                                "Loyalty Program", {"name": customer_detail[0].loyalty_program}, ["conversion_factor"], as_dict=True
                        )

    
                credit_limit = 0
                outstanding_amount = 0
                
                try:
                        customer = frappe.get_doc('Customer', customer_detail[0].name)
                        credit_limit=customer.custom_credit_limit    
                        
                        outstanding_amount =  get_customer_outstanding(
                                        customer_detail[0]['name'], frappe.get_doc("Global Defaults").default_company, ignore_outstanding_sales_order=False
                                )

                except frappe.DoesNotExistError:
                        message = _("Customer not found.")
                except Exception as e:
                        frappe.log_error(frappe.get_traceback(), _("Error fetching credit limit"))
                        message = _("An error occurred while fetching the credit limit.")


                res['success_key'] = 1
                res['message'] = "success"
                res['customer'] = customer_detail
                res['loyalty_points'] = loyalty_points
                res['conversion_factor'] = conversion_factor.conversion_factor if conversion_factor else 0
                res['loyalty_amount'] = loyalty_points * conversion_factor.conversion_factor if conversion_factor else 0
                res['credit_limit'] = credit_limit
                res['outstanding_amount'] = outstanding_amount
                return res
        else:
                res["success_key"] = 0
                res['mobile_no'] = mobile_no
                res["message"] = "Mobile Number/Customer Does Not Exist"
                return res



@frappe.whitelist()
def get_all_customer(search=None, from_date=None,customer_id=None):
    res=frappe._dict()
    customer = frappe.qb.DocType('Customer')
    if search:
        query = """SELECT name, customer_name, mobile_no, email_id
        FROM `tabCustomer`
        WHERE disabled = 0 AND mobile_no LIKE %s"""
        params = ("%"+search+"%",)
    else:
        query = """SELECT name, customer_name, mobile_no, email_id , loyalty_program
        FROM `tabCustomer`
        WHERE disabled = 0 """
        params = ()
    if from_date:
        query += "AND modified >= %s"
        params += (from_date,)
    if customer_id:
        query += "AND name = %s"
        params += (customer_id,)
    customers = frappe.db.sql(query, params, as_dict=1)
    for customer in customers:
        loyalty_point_details = frappe._dict(
                frappe.get_all(
                        "Loyalty Point Entry",
                        filters={
                        "customer": customer.name,
                        "expiry_date": (">=", frappe.utils.getdate()),
                        },
                        group_by="company",
                        fields=["company", "sum(loyalty_points) as loyalty_points"],
                        as_list=1,
                )
                )
        companies = frappe.get_all(
        "Sales Invoice", filters={"docstatus": 1, "customer": customer.name}, distinct=1, fields=["company"]
        )
        loyalty_points = 0
        for d in companies:
                if loyalty_point_details:
                        loyalty_points = loyalty_point_details.get(d.company)
                        customer['loyalty_points'] = loyalty_points

        conversion_factor = None

        conversion_factor = frappe.db.get_value(
                "Loyalty Program", {"name": customer.loyalty_program}, ["conversion_factor"], as_dict=True
        )
        customer['conversion_factor'] = conversion_factor.conversion_factor if conversion_factor else 0
        customer['loyalty_amount'] = loyalty_points * conversion_factor.conversion_factor if conversion_factor else 0

        customer['credit_limit'] = 0
        customer['outstanding_amount'] = 0
        
        try:
                customer['credit_limit']=customer.custom_credit_limit    
                
                customer['outstanding_amount'] =  get_customer_outstanding(
                                customer.name, frappe.get_doc("Global Defaults").default_company, ignore_outstanding_sales_order=False
                        )

        except frappe.DoesNotExistError:
                message = _("Customer not found.")
        except Exception as e:
                frappe.log_error(frappe.get_traceback(), _("Error fetching credit limit"))
                message = _("An error occurred while fetching the credit limit.")
    if customer:
        res['success_key'] = 1
        res['message'] = "success"
        res['customer'] = customers
        return res
    else:
        res["success_key"] = 0
        res["message"] = "No customer found"
        res['customer']= customers
        return res


@frappe.whitelist()
def create_customer():
        customer_detail = frappe.request.data
        customer_detail = json.loads(customer_detail)
        res = frappe._dict()
        try:
                if customer_detail.get("mobile_no") and frappe.db.exists({"doctype":"Customer" , 'mobile_no': customer_detail.get("mobile_no") } ):
                                return frappe_response(400,"Customer already present with this mobile no.")
                                
                else: 
                        customer = frappe.new_doc("Customer")
                        customer.customer_name = customer_detail.get("customer_name")
                        customer.mobile_no = customer_detail.get("mobile_no")
                        customer.email_id = customer_detail.get("email_id")
                        customer.customer_group = 'All Customer Groups'
                        customer.territory = 'All Territories'
                        customer.save(ignore_permissions=True)
                        frappe.db.commit()
                        res['success_key'] = 1
                        res['message'] = "success"
                        res["customer"] ={"name" : customer.name,
                                "customer_name": customer.customer_name,
                                "mobile_no" : customer.mobile_no,
                                "email_id":customer.email_id
                                }
                        return res

        except Exception as e:
                frappe.log_error(frappe.get_traceback(), "Error in create_customer")
                return handle_exception(e)
                
def get_sub_items(name):
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        filters={'name': name ,  'base_url': base_url}
        sub_items = frappe.db.sql("""
                SELECT
                soi.item_code , soi.item_name, soi.qty,soi.uom , soi.rate , 
                soi.amount, soi.associated_item ,
                if((image = NULL or image = ''), "", 
                if(image LIKE 'http%%', image, concat(%(base_url)s, image))) as image
                FROM `tabSales Order` so , `tabSales Order Item` soi
                WHERE so.name = soi.parent and so.name = %(name)s
                """,values=filters ,  as_dict = True)
        if sub_items:
                return sub_items
        else:
                return ""

             
        
                
        

@frappe.whitelist()
def get_promo_code():
        res = frappe._dict() 
        coupon_code = frappe.qb.DocType('Coupon Code') 
        pricing_rule = frappe.qb.DocType('Pricing Rule')
        coupon_code =(
        frappe.qb.from_(coupon_code).inner_join(pricing_rule) .on(coupon_code.pricing_rule == pricing_rule.name) 
        .select(coupon_code.name , coupon_code.coupon_code, coupon_code.pricing_rule,
        coupon_code.maximum_use, coupon_code.used, coupon_code.description, 
        pricing_rule.valid_from , pricing_rule.valid_upto, pricing_rule.apply_on, 
        pricing_rule.price_or_product_discount, pricing_rule.min_qty,
        pricing_rule.max_qty, pricing_rule.min_amt, pricing_rule.max_amt, 
        pricing_rule.rate_or_discount, pricing_rule.apply_discount_on, 
        pricing_rule.discount_amount, pricing_rule.rate, pricing_rule.discount_percentage )
        .where( (pricing_rule.apply_on == 'Transaction') 
        & (pricing_rule.rate_or_discount == 'Discount Percentage') &
        (pricing_rule.apply_discount_on == 'Grand Total') & 
        (pricing_rule.price_or_product_discount == "Price")
        )
        ).run(as_dict=1)
        
        if coupon_code:
                res['success_key'] = 1
                res['message'] = "success"
                res['coupon_code'] = coupon_code
                return res
        else:
                res["success_key"] = 0
                res["message"] = "No Coupon Code in DB"
                res['coupon_code']= coupon_code
                return res



@frappe.whitelist(allow_guest=True)
def get_web_theme_settings():
    theme_settings = frappe.get_doc("Web Theme Settings")
    theme_settings_dict = {}
    theme = frappe.get_meta("Web Theme Settings")
    
    nbpos_setting = frappe.get_doc("nbpos Setting")
    instance_url = nbpos_setting.base_url

    image_fields = [
        "web_logo_image", 
        "web_banner_image", 
        "web_outlet_details_banner_image", 
        "web_footer_logo"
    ]
    
    for field in theme.fields:
        value = theme_settings.get(field.fieldname)
        
        if field.fieldname in image_fields and value:
            if not value.startswith(instance_url):
                value = f"{instance_url.rstrip('/')}/{value.lstrip('/')}"
        
        theme_settings_dict[field.fieldname] = value

    res = {
        "data": theme_settings_dict
    }
    return res
@frappe.whitelist(allow_guest=True)
def get_theme_settings():
    theme_settings = frappe.get_doc("Theme Settings")
    theme_settings_dict = {}
    theme = frappe.get_meta("Theme Settings")
    
    nbpos_setting = frappe.get_doc("nbpos Setting")
    instance_url = nbpos_setting.base_url

    image_fields = [
        "app_background_image", 
        "merchant_background_image", 
        "banner_image"
    ]
    
    for field in theme.fields:
        value = theme_settings.get(field.fieldname)
        
        if field.fieldname in image_fields and value:
            if not value.startswith(instance_url):
                value = f"{instance_url.rstrip('/')}/{value.lstrip('/')}"
        
        theme_settings_dict[field.fieldname] = value

    res = {
        "data": theme_settings_dict
    }
    return res

@frappe.whitelist()
def get_sales_taxes():
        taxes_data = frappe.db.sql("""
                SELECT
        stct.name AS name,stct.title AS title,stct.is_default AS is_default,stct.disabled AS disabled,stct.company AS company,stct.tax_category AS tax_category
                FROM `tabSales Taxes and Charges Template` AS stct 
        
                """, as_dict=1)

        tax = frappe.db.sql("""
        SELECT stct.name as name , stct.name as item_tax_template,
        stc.charge_type AS charge_type , stc.account_head AS tax_type , stc.description AS description , stc.cost_center AS cost_denter ,stc.rate as tax_rate, 
        stc.account_currency as account_currency , stc.tax_amount as tax_amount ,stc.total as total FROM `tabSales Taxes and Charges` AS stc INNER JOIN `tabSales Taxes and Charges Template`
        as stct ON
        stct.name=stc.parent 
        """, as_dict=1)
       
        for i in taxes_data:
                i['tax'] = [j for j in tax if i['name'] == j['name']]
        return taxes_data


@frappe.whitelist()
def review_rating_order():
        review_order = frappe.request.data
        review_order = json.loads(review_order)
        review_order = review_order["review_order"]
        try:
                res = frappe._dict()
                sales_order = frappe.get_doc("Sales Order", review_order.get("name"))
                sales_order.custom_rating = review_order.get("rating")
                sales_order.custom_review = review_order.get("review")
                sales_order.save(ignore_permissions=True)
                sales_order.submit()
                
                res['success_key'] = 1
                res['message'] = "success"
                res["sales_order"] ={
                "name" : sales_order.name,
                "doc_status" : sales_order.docstatus
                }
                if frappe.local.response.get("exc_type"):
                        del frappe.local.response["exc_type"]
                return res

        except Exception as e:
                if frappe.local.response.get("exc_type"):
                        del frappe.local.response["exc_type"]

                frappe.clear_messages()
                frappe.local.response["message"] ={
                "success_key":0,
                "message":e
                        }

@frappe.whitelist()
def update_status(order_status):
        try:
                doc=frappe.get_doc("Kitchen-Kds",{"order_id":order_status.get('name')})
                doc.status= order_status.get('status')
                doc.save(ignore_permissions=True)
                # frappe.db.set_value("Kitchen-Kds", {"order_id":order_status.get('name')}, {'status': order_status.get('status')
                # })
                send_order_ready_email(order_status)
                return {"success_key":1, "message": "success"}

        except Exception as e:
                return {"success_key":0, "message": e}

def send_order_ready_email(order_status):
        order = frappe.get_doc("Sales Order", order_status.get('name'))
        customer = frappe.get_doc("Customer", order.customer)
        cost_center =order.cost_center
        restaurant_name = frappe.db.get_value("Cost Center", cost_center, "cost_center_name")

        subject = "Your Order is Ready for Pickup"
        message = f"""
        Dear {customer.customer_name}, <br><br>

        Good news! Your order from {restaurant_name} is prepared and ready for pickup. <br><br>

        <b>Order ID</b>: {order.name} <br> <br>

        We look forward to serving you. <br> <br>

        Thank you for choosing {restaurant_name}! <br><br><br>

        Best regards, <br> <br>
        The {restaurant_name} Team<br><br>

        <b>Disclaimer</b>:
        Please note that email is auto generated and the inbox is unmonitored. For any cancellation requests or inquiries regarding your order, kindly contact the business directly.
        """
        frappe.sendmail(
                recipients=customer.email_id,
                subject=subject,
                message=message,
                now=True
        )


@frappe.whitelist(allow_guest=True)
def get_all_location_list():
       return frappe.db.sql("""
        SELECT DISTINCT custom_location 
        FROM `tabCost Center` 
        WHERE custom_location IS NOT NULL
        ORDER BY custom_location ASC;
                """,as_dict=True)




@frappe.whitelist(allow_guest=True)
def get_kitchen_kds(status, cost_center=None):
    try:


        end_datetime = now()
        if status.lower() == "completed":
                start_datetime = add_to_date(end_datetime, minutes=-30)
        else:
                start_datetime = add_to_date(end_datetime, hours=-24)


        start_datetime_str = str(start_datetime)
        end_datetime_str = str(end_datetime)

        cost_center_condition = ""
        if cost_center:
            cost_center_condition = "AND cost_center = %s"

        all_order = frappe.db.sql(f"""
            SELECT 
                name, 
                order_id, 
                custom_order_request, 
                status, 
                cost_center,                 
                estimated_time, 
                type, 
                CONCAT(creation1, ' ', time) AS creation1, 
                source
            FROM `tabKitchen-Kds`
            WHERE CONCAT(creation1, ' ', time) BETWEEN %s AND %s
            AND status = %s {cost_center_condition}
            ORDER BY CONCAT(creation1, ' ', time) DESC
        """, (start_datetime_str, end_datetime_str, status) + ((cost_center,) if cost_center else ()), as_dict=True)

        for orders in all_order:
            try:      
                orders['items'] =grouping_combo_attr(orders.order_id)

            except Exception as e:
                return {"message": str(e)}

        # frappe.publish_realtime('realtime_update', message=all_order)

        return all_order

    except Exception as e:
        return {"message": str(e)}

def grouping_combo_attr(order_id):
                query =  """
                                        SELECT 
                                        soi.item_code,
                                        soi.item_name,
                                        soi.custom_ca_id,
                                        soi.rate,
                                        soi.custom_is_combo_item,
                                        soi.custom_is_attribute_item,
                                        soi.custom_parent_item,
                                        soi.qty
                                        FROM 
                                        `tabSales Order Item` soi,`tabSales Order` s
                                        WHERE 
                                        soi.parent=s.name and 
                                        soi.parent = %s
                                        """

                items = frappe.db.sql(query, (order_id,), as_dict=True)
                                
                
                grouped_items = {}

                for item in items:
                        ca_id = item['custom_ca_id']
                        parent_item = item['custom_parent_item']
                        
                        if ca_id not in grouped_items:
                                grouped_items[ca_id] = []

                        if parent_item is None:

                                grouped_items[ca_id].append({
                                "item_code": item["item_code"],
                                "item_name": item["item_name"],
                                "custom_ca_id": item["custom_ca_id"],
                                'price':item['rate'],
                                "custom_is_combo_item": item["custom_is_combo_item"],
                                "custom_is_attribute_item": item["custom_is_attribute_item"],
                                "qty": item["qty"],
                                "child_items": []
                                })
                        
                for item in items:
                        ca_id = item['custom_ca_id']
                        parent_item = item['custom_parent_item']
                        if parent_item is not None:
                                for parent in grouped_items.get(ca_id, []):
                                        if parent["item_code"] == parent_item:
                                                parent["child_items"].append({
                                                "item_code": item["item_code"],
                                                "item_name": item["item_name"],
                                                'price':item['rate'],
                                                "custom_ca_id": item["custom_ca_id"],
                                                "custom_is_combo_item": item["custom_is_combo_item"],
                                                "custom_is_attribute_item": item["custom_is_attribute_item"],
                                                "custom_parent_item": item["custom_parent_item"],
                                                "qty": item["qty"]
                                                })


                output = []

                for items_list in grouped_items.values():
                        output.extend(items_list)
                        
                        
                return output
        
        
        
        
        
def after_request(whitelisted, response):
    try:
        kdsurl = frappe.db.get_single_value("Web Theme Settings", "kdsurl")
        if kdsurl:
            response.headers['Access-Control-Allow-Origin'] = kdsurl
        else:
                pass
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS,DELETE,PUT'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "CORS Middleware Error")
    
    return response               


def get_warehouse_for_cost_center(cost_center):
    warehouse = frappe.db.get_value('Warehouse', {'custom_cost_center': cost_center}, 'name')
    return warehouse


@frappe.whitelist(allow_guest=True)
def create_sales_order_kiosk():
    order_list = frappe.request.data
    order_list = json.loads(order_list)
    order_list = order_list["order_list"]
    
    try:
        # frappe.set_user("Administrator")
        res = frappe._dict()
        if order_list.get('name'):
                sales_order = frappe.get_doc("Sales Order",order_list.get("name"))
                sales_order.items=[]
                sales_order.taxes=[]
                if sales_order.docstatus!=0:
                        return frappe_response(400, "sales order is already submitted")     
        else:
                sales_order = frappe.new_doc("Sales Order")
        sales_order.hub_manager = order_list.get("hub_manager")
        sales_order.custom_source = order_list.get("source")
        sales_order.ward = order_list.get("ward")
        sales_order.custom_order_request = order_list.get("order_request")
        
        if order_list.get("source") == "WEB":
            phone_no = frappe.db.sql("""SELECT phone FROM `tabContact Phone` WHERE phone = %s """, (order_list.get('mobile')))
            if phone_no:
                parent = frappe.db.get_value('Contact Phone', {'phone': order_list.get('mobile')}, 'parent')
                customer = frappe.db.get_value('Dynamic Link', {'parent': parent, 'link_doctype': 'Customer'}, 'link_name')
                if customer:
                    sales_order.customer = customer
            else:
                new_customer = frappe.new_doc("Customer")
                new_customer.customer_name = order_list.get("customer_name")
                new_customer.customer_group = "Individual"
                new_customer.territory = "All Territories"
                new_customer.email_id = order_list.get("email")
                new_customer.mobile_no = order_list.get("mobile")
                new_customer.insert(ignore_permissions=True)
                sales_order.customer = new_customer.name
        else:
            sales_order.customer = order_list.get("customer")
        transaction_date=now()
        arr = transaction_date.split(" ")
        sales_order.transaction_date = arr[0]
        sales_order.transaction_time =arr[1]
        sales_order.delivery_date = order_list.get("delivery_date")
        sales_order = add_items_in_order(sales_order, order_list.get("items"), order_list)
        sales_order.status = order_list.get("status")
        sales_order.mode_of_payment = order_list.get("mode_of_payment")
        sales_order.mpesa_no = order_list.get("mpesa_no")
        sales_order.coupon_code = order_list.get("coupon_code")
        sales_order.custom_order_service_type = order_list.get("order_service_type")
        sales_order.custom_booking_number = order_list.get("booking_number")
        sales_order.custom_table_no = order_list.get("table_no")
        sales_order.disable_rounded_total = 1
        
        # if cost_center:
        #     custom_times = frappe.db.get_value("Cost Center", cost_center, ["custom_opening_time", "custom_closing_time"], as_dict=True)
        #     if custom_times:
                # if not custom_times.get("custom_opening_time") or not custom_times.get("custom_closing_time"):
                #     frappe.throw("Please fill in the custom opening time and custom closing time for the selected cost center.")
                
                # sales_order.custom_opening_time = custom_times.get("custom_opening_time")
                # sales_order.custom_closing_time = custom_times.get("custom_closing_time")

                # Validate transaction time against current time
                # now_time = datetime.now().time()
                # opening_time = (datetime.min + custom_times.get("custom_opening_time")).time()
                # closing_time = (datetime.min + custom_times.get("custom_closing_time")).time()

                # if not (opening_time <= now_time <= closing_time):
                #     frappe.throw("Transaction time is outside the allowed operating hours.")
        
        

        if order_list.get("mode_of_payment") == "Card":
            sales_order.custom_payment_status = "Pending"
        else:
            sales_order.custom_payment_status = "Paid"
        if order_list.get("discount"):
                sales_order.apply_discount_on = "Net Total"
                sales_order.additional_discount_percentage = order_list.get("discount")
        
        sales_order.cost_center = order_list.get("cost_center")
        warehouse = get_warehouse_for_cost_center(order_list.get("cost_center"))
        if warehouse:
            sales_order.set_warehouse = warehouse
        if order_list.get("redeem_loyalty_points") == 1 :
                sales_order.custom_redeem_loyalty_points = 1
                grand_total = sales_order.grand_total or 0 
                loyalty_amount = sales_order.loyalty_amount or 0 
                sales_order.outstanding_amount = grand_total - loyalty_amount
                sales_order.loyalty_points = order_list.get("loyalty_points")
                sales_order.loyalty_amount = order_list.get("loyalty_amount")               
                sales_order.custom_redemption_account = order_list.get("loyalty_redemption_account")   
        if order_list.get("loyalty_program") :
               sales_order.custom_loyalty_program = order_list.get("loyalty_program")        
        if order_list.get("pos_opening_shift") :              
               sales_order.custom_pos_shift=order_list.get("pos_opening_shift")
                        
        try:
                if not order_list.get("name"):
                        sales_order.insert(ignore_permissions=True)
                elif order_list.get("name") and order_list.get("park_order")==1:
                        sales_order.save()
                        return frappe_response(200, "Updated Successfully")
                if order_list.get("service_charge", 0) > 0 and order_list.get("park_order")==0:                  
                        last_row_id = len(sales_order.get("taxes", []))
                        service_account_head = frappe.db.get_single_value("Theme Settings","service_charge_account_head")
                        if not service_account_head:
                                return frappe_response(400, "Please fill the service account head in the Theme Settings")
                        if last_row_id>0:
                                sales_order.append("taxes", {
                                "row_id": last_row_id  ,
                                "charge_type": "On Previous Row Total",
                                "account_head": service_account_head,
                                "rate": order_list.get("service_charge"),
                                "description": "Service Charge"
                                })
                        else:
                                sales_order.append("taxes", {
                                "charge_type": "On Net Total",
                                "account_head": service_account_head,
                                "rate": order_list.get("service_charge"),
                                "description": "Service Charge"
                                })
                                
                        sales_order.save()
                if order_list.get('park_order')==0:
                        sales_order.submit()
        except Exception as e:
                frappe.log_error(frappe.get_traceback(), "sales_order_error")
                frappe.clear_messages()
                frappe.local.response["message"] = {
                "success_key": 0,
                "message": str(e)
                }     
        
        if frappe.local.response.get("exc_type"):
                        del frappe.local.response["exc_type"]
        res['success_key'] = 1
        res['message'] = "success"
        res["sales_order"] = {
                "name": sales_order.name
        }
        
        return res

    except Exception as e:
        if frappe.local.response.get("exc_type"):
            del frappe.local.response["exc_type"]

        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": str(e)
        }

@frappe.whitelist(methods="POST")
def create_web_sales_invoice():
    import json
    data = frappe.request.data
    data = json.loads(data)
    data = data["message"]
    try:
        frappe.set_user("Administrator")
        res = frappe._dict()
        if data.get('status') == "F":
                doc = frappe.get_doc("Sales Order", data.get('order_id'))
                total_time=[]
                sales_order_items = frappe.db.get_all('Sales Order Item', filters={'parent': doc.name}, fields=['item_code'])
                for item in sales_order_items:
                        time = frappe.get_value("Item", {"item_code": item.get('item_code')}, 'custom_estimated_time')
                        total_time.append(time)
                max_time = max(total_time)

                sales_invoice = make_sales_invoice(doc.name)
                sales_invoice.posting_date = doc.transaction_date
                sales_invoice.posting_time = doc.transaction_time
                sales_invoice.due_date = data.get('transaction_date')
                sales_invoice.update_stock = 1
                sales_invoice.save(ignore_permissions=1)
                sales_invoice.submit()

                frappe.get_doc({
                    "doctype": "Kitchen-Kds",
                    "order_id": doc.name,
                    "type": "Takeaway",   
                    "estimated_time": max_time, 
                    "status": "Open",
                    "creation1": now(),
                    "custom_order_request": doc.custom_order_request,
                    "source": "WEB",
                    "cost_center" : doc.cost_center
                }).insert(ignore_permissions=1)

                res['success_key'] = 1
                res['message'] = "success"
                res["sales_order"] = {
                    "name": sales_invoice.name,
                    "doc_status": sales_invoice.docstatus
                }

                if frappe.local.response.get("exc_type"):
                    del frappe.local.response["exc_type"]

                return res
 
    except Exception as e:
        if frappe.local.response.get("exc_type"):
            del frappe.local.response["exc_type"]

        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": str(e)
        }

@frappe.whitelist(allow_guest=True)
def get_sales_order_item_details(order_id=None):
    try:
        if order_id:
                doc = frappe.get_doc("Sales Order", order_id)
                address = frappe.db.sql("""
                SELECT CONCAT(cost_center_name, ", ", custom_address, ", ", custom_location) as address 
                FROM `tabCost Center`
                WHERE name = %s
                """, (doc.cost_center,), as_dict=True)

                item_list = grouping_combo_attr(order_id)
                data = {}
                max_time = []
                for item in doc.items:
                    estimated_time =frappe.db.get_value("Item", {"item_code" : item.item_code}, 'custom_estimated_time')
                    max_time.append(estimated_time)


                data["order_request"] = doc.custom_order_request
                data["item_details"] = item_list
                if address:
                        data['address'] = address[0]['address']
                data["estimated_time"] = max(max_time)
                return data

    except Exception as e:
        if frappe.local.response.get("exc_type"):
            del frappe.local.response["exc_type"]

        frappe.clear_messages()
        frappe.local.response["message"] = {
            "success_key": 0,
            "message": str(e)
        }




                
@frappe.whitelist(methods="POST")
def payment_request(payment_list={}):
        try:
                auth_url = f'{payment_list.get("auth_token_url")}/connect/token'
                post_data = {
                "grant_type": "client_credentials",
                "client_id": payment_list.get("client_id"),
                "client_secret":payment_list.get("client_secret")
                }
                response = requests.post(auth_url, data=post_data)
                o_auth_authentication_response = response.json()

                api_client = requests.Session()
                base_address = payment_list.get("base_payment_url")
                api = "/checkout/v2/isv/orders?merchantid=" 
                merchantId=  payment_list.get("merchant_id")            
                api_client.headers.update({
                "Accept": "application/json",
                "Authorization": f"Bearer {o_auth_authentication_response['access_token']}"
                })


                customer = {
                        "Email":  payment_list.get("customer_email"),
                        "FullName": payment_list.get("customer_name"),
                        "Phone": payment_list.get("customer_phone"),
                        "CountryCode":  payment_list.get("country_code"),
                        "RequestLang":  payment_list.get("request_lang")
                }
                isvamount= payment_list.get("amount") * payment_list.get("isv_percentage") / 100
                request = {
                        "Amount": payment_list.get("amount"),
                        "CustomerTrns": payment_list.get("customer_trans"),
                        "Customer": customer,
                        "PaymentTimeout": 300,
                        "Preauth": False,
                        "AllowRecurring": False,
                        "MaxInstallments": 12,
                        "PaymentNotification": True,
                        "TipAmount": 0,
                        "DisableExactAmount": False,
                        "DisableWallet": True,
                        "SourceCode": payment_list.get("source_code"),
                        "isvamount": isvamount
                }
                post_request_data = json.dumps(request)
                content_data = post_request_data.encode('utf-8')
                headers = {'Content-Type': 'application/json'}

                api_response = api_client.post(f"{base_address}{api}{merchantId}", data=content_data, headers=headers)

                viva_wallet_order_response = api_response.json()
                
                if api_response.status_code == 200:
                        # post_process_payment_request['Order']['OrderCode'] = viva_wallet_order_response['OrderCode']
                        # await _order_service.update_order_async(post_process_payment_request['Order'])
                        redirect_url = f'{payment_list.get("checkout_url")}/web/checkout?ref={viva_wallet_order_response["orderCode"]}'
                return redirect_url
        except Exception as e:
                if frappe.local.response.get("exc_type"):
                        del frappe.local.response["exc_type"]

                frappe.clear_messages()
                
                frappe.local.response["message"] ={
                "success_key":0,
                "message":e
                        }




@frappe.whitelist()
def transaction_status(payment_list={}, transaction_id=None, merchant_id=None):
    try:
        auth_url = f'{payment_list.get("auth_token_url")}/connect/token'
        post_data = {
            "grant_type": "client_credentials",
            "client_id": payment_list.get("client_id"),
            "client_secret": payment_list.get("client_secret")
        }
        
        response = requests.post(auth_url, data=post_data)
        response.raise_for_status() 
        o_auth_authentication_response = response.json()
        api_client = requests.Session()
        base_address = payment_list.get("base_payment_url")
        api_client.headers.update({
            "Accept": "application/json",
            "Authorization": f"Bearer {o_auth_authentication_response['access_token']}"
        })

        api_url = f"{base_address}/checkout/v2/isv/transactions/{transaction_id}?merchantId={merchant_id}"
        
        api_response = api_client.get(api_url)

        if api_response.status_code == 200:
            transaction_response = api_response.json()
            return transaction_response
        else:
            return {
                "success_key": 0,
                "message": f"Failed to retrieve transaction status. Status code: {api_response.status_code}, Response: {api_response.text}"
            }

    except Exception as e:
        return {
            "success_key": 0,
            "message": str(e)
        }


@frappe.whitelist()
def update_payment_status(update_paymentstatus):
        try:
                frappe.db.set_value("Sales Order", {"name":update_paymentstatus.get('order_id')}, {'custom_payment_status': update_paymentstatus.get('paymentstatus')
                })

                return {"success_key":1, "message": "success"}

        except Exception as e:
                return {"success_key":0, "message": e}
        

@frappe.whitelist(allow_guest=True)
def get_filters():
        filters = frappe.db.sql(''' Select 
        it.item_type
        from `tabItem Type` it
        ''', as_dict = True)
     
        return filters



@frappe.whitelist(allow_guest=True)
def get_location():
    body = frappe.local.form_dict
    if body.get("search_location"):
        filter_condition = f'%{body.get("search_location")}%'
        return frappe.db.sql("""
            SELECT DISTINCT custom_location
            FROM `tabCost Center` WHERE custom_location LIKE %s
            ORDER BY custom_location ASC;
            """, (filter_condition,) ,as_dict=1)


    elif (body.get("custom_location")):
        base_url = frappe.db.get_single_value('nbpos Setting', 'base_url')
        return frappe.db.sql("""
                SELECT name,cost_center_name,custom_location, custom_address_line_1,custom_address_line_2,custom_citytown,custom_stateprovince,custom_county,custom_email_address, 
                custom_phone_number,custom_registration_no,
                custom_service_charge as service_charge,
                custom_printer_ip_address,
                custom_bluetooth_printer_name,
                CONCAT(%(base_url)s, custom_attach_image) AS custom_attach_image,
                CONCAT(%(base_url)s, custom_web_outlet_details_banner_image) AS web_outlet_details_banner_image
                FROM `tabCost Center`
                WHERE disabled = 0 AND custom_location = %(custom_location)s
                ORDER BY creation DESC
                """, {
                    'base_url': base_url,
                    'custom_location': body.get("custom_location")
                }, as_dict=1)


    else:
        return frappe.db.sql("""
            SELECT Distinct(custom_location)
            FROM `tabCost Center` WHERE custom_location is NOT NULL
            ORDER BY custom_location ASC;
            """,as_dict=1)



@frappe.whitelist(allow_guest=True)
def get_cost_center_by_pin():  
        body = frappe.local.form_dict
        pin = body.get("custom_pin")
        cost_center = body.get("cost_center")
        
        if not pin or not cost_center:
                missing_param = "custom_pin" if not pin else "cost_center"
                return frappe_response(400, f"{missing_param} is missing")

        custom_pin = frappe.db.get_value("Cost Center",cost_center,'custom_pin')
        if int(custom_pin) == int(pin):
                return frappe_response(200, {"is_verified": True})
        
        else:
                return frappe_response(200, {"is_verified": False})
                

@frappe.whitelist(methods="POST",allow_guest=1)
def return_sales_order(sales_invoice):
    try:
        frappe.set_user("Administrator")
        res = frappe._dict()
        # Fetch the sales invoice number
        sales_order_number = sales_invoice.get("sales_order_number")
        sales_invoice_doc = frappe.db.get_value("Sales Invoice Item",
                                                filters={"sales_order": sales_order_number},
                                                fieldname=["parent"])
        if sales_invoice_doc:
            invoice = frappe.get_doc("Sales Invoice", sales_invoice_doc)
            return_order_items = sales_invoice.get("return_items")
            # Update invoice fields for return
            invoice.is_return = 1
            invoice.update_outstanding_for_self = 1
            invoice.return_against = sales_invoice_doc
            invoice.update_billed_amount_in_delivery_note = 1
            invoice.total_qty = -sales_invoice.get("total_qty")
            invoice.mode_of_payment = ''
            invoice.redeem_loyalty_points = 0
            invoice.loyalty_points = 0
            invoice.loyalty_amount = 0
            invoice.loyalty_program = ''
            invoice.loyalty_redemption_account = ''            
            invoice.coupon_code=''
            invoice.discount_amount=-invoice.discount_amount
            returned_items = []
            # Adjust quantities for returned items
            for item in invoice.items:
                if return_order_items.get(item.item_code, 0) > 0:
                    item.qty = -return_order_items[item.item_code]
                    item.stock_qty = -return_order_items[item.item_code]
                    returned_items.append(item)
            invoice.items = returned_items
            invoice.insert(ignore_permissions=1)
            # Update sales order custom status
        #     frappe.db.sql("""
        #         UPDATE `tabSales Order`
        #         SET `custom_return_order_status` = %s
        #         WHERE name = %s
        #     """, (sales_invoice.get("return_type"), sales_order_number))
            res["success_key"] = 1
            res["message"] = "Success"
            res['invoice'] = invoice.name
            res['amount'] = invoice.grand_total
        #     try:
        #         # Send email to customer with the sales invoice return attached
        #         # send_credit_note_email(invoice)  
        #     except Exception as e:
        #            pass            
            return res
        else:
            res["success_key"] = 0
            res["message"] = "Sales invoice not found for this order."
            res['invoice'] = ""
            res['amount'] = 0
            return res
    except Exception as e:
        frappe.log_error(frappe.get_traceback(), "return_sales_order Error")
        return {"success_key": 0, "message": "An unexpected error occurred. Please try again later.", "invoice": "", "amount": 0}



def send_credit_note_email(invoice):
        customer = frappe.get_doc("Customer", invoice.customer)
        contact_doc = frappe.get_doc("Contact", customer.customer_primary_contact)
        email = contact_doc.email_id
        subject = "Credit Note: {}".format(invoice.name)
        message = "Please find attached the Credit Note {}.".format(invoice.name)
        # Use Frappe's PDF generation tool to create the PDF
        pdf_content = frappe.utils.pdf.get_pdf(frappe.render_template(
            'getpos/templates/pages/credit_note_email.html', {"doc": invoice}
        ))
        attachments = [{
            "fname": "Credit_Note_{}.pdf".format(invoice.name.replace(" ", "_")),
            "fcontent": pdf_content
        }]
        frappe.sendmail(
            recipients=email,
            subject=subject,
            message=message,
            attachments=attachments,
            now=True
        )



@frappe.whitelist()
def coupon_code_details():
    current_date = nowdate()
    def get_details(entity, fields):
        return {field:entity.get(field) for field in fields}
    def fetch_coupon_and_pricing_rule(coupon_code):
        # Fetch details related to the coupon and its associated pricing rule
        coupon = frappe.db.get_value("Coupon Code", {"coupon_code": coupon_code},
                                     ["name", "used", "maximum_use", "valid_from", "valid_upto", "pricing_rule","description"], as_dict=True)
        if not coupon:
            return None, {"status": "error", "message": _("Coupon code does not exist.")}
        pricing_rule = frappe.get_doc("Pricing Rule", coupon.get("pricing_rule"))
        if not pricing_rule:
            return None, {"status": "error", "message": _("Pricing rule associated with coupon not found.")}
        return coupon, pricing_rule
    pricing_rule_fields = [
        # List of fields to fetch from Pricing Rule document
        "name", "title", "apply_on", "price_or_product_discount", "coupon_code_based", "selling", "buying",
        "applicable_for", "customer", "min_qty", "max_qty", "min_amt", "max_amt", "valid_from", "company",
        "currency", "rate_or_discount", "apply_discount_on", "rate", "discount_amount", "discount_percentage",
        "for_price_list", "doctype", "items", "item_groups", "customers", "customer_groups", "territories"
    ]   
    # Fetch all valid coupons based on current date and their respective pricing rules
    coupons = frappe.db.get_all("Coupon Code", filters={"valid_upto": (">=", current_date),"coupon_type": "Promotional"},
                                fields=["name", "coupon_code", "used", "maximum_use", "valid_from", "valid_upto", "pricing_rule","description"])
    valid_coupons = []
    for coupon in coupons:
        pricing_rule = frappe.get_doc("Pricing Rule", coupon.get("pricing_rule"))
        if coupon["description"] :
                coupon["description"]=frappe.utils.strip_html_tags(coupon["description"])
        # Check if the pricing rule is valid, coupon usage is within limit
        if pricing_rule and is_valid_pricing_rule(pricing_rule, current_date) and coupon["used"] < coupon["maximum_use"]:
            valid_coupons.append({
                **get_details(coupon, ["name","coupon_code", "used", "maximum_use", "valid_from", "valid_upto","description"]),
                "pricing_rule": get_details(pricing_rule, pricing_rule_fields)
            })
           
    # Return success status with valid coupons list
    return {"status": "success", "valid_coupons": valid_coupons}



def is_valid_pricing_rule(pricing_rule, current_date):
        from datetime import datetime
        def parse_date(date_str):
                return datetime.strptime(date_str, "%Y-%m-%d").date() if isinstance(date_str, str) else date_str
        # Parse valid_from and valid_upto dates from the pricing rule
        rule_valid_from = parse_date(pricing_rule.get("valid_from"))
        rule_valid_upto = parse_date(pricing_rule.get("valid_upto"))
        # Check if the current date falls within the valid range of the pricing rule
        return (not rule_valid_from or current_date >= rule_valid_from) and (not rule_valid_upto or current_date <= rule_valid_upto)
