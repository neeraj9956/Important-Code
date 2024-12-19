
@frappe.whitelist()
def get_foc_items(customer, site, customer_group, item_code=None, item_grp=None, brnd=None, item_category=None,
                   dc=None, company=None, sales_organization_code=None, customer_hierarchy=None, has_priority=0):
    
    current_date = frappe.utils.nowdate()
    
    # Convert input parameters into tuples if they are lists or single items, or handle None cases
    dc = tuple(dc) if isinstance(dc, (list, tuple)) else (dc,) if dc else None
    company = tuple(company) if isinstance(company, (list, tuple)) else (company,) if company else None
    sales_organization_code = tuple(sales_organization_code) if isinstance(sales_organization_code, (list, tuple)) else (sales_organization_code,) if sales_organization_code else None
    customer_group = tuple(customer_group) if isinstance(customer_group, (list, tuple)) else (customer_group,) if customer_group else None
    sites = tuple(site) if isinstance(site, (list, tuple)) else (site,) if site else None
    customer_hierarchy = tuple(customer_hierarchy) if isinstance(customer_hierarchy, (list, tuple)) else (customer_hierarchy,) if customer_hierarchy else None
    item_code = tuple(item_code) if isinstance(item_code, (list, tuple)) else (item_code,) if item_code else None
    item_grp = tuple(item_grp) if isinstance(item_grp, (list, tuple)) else (item_grp,) if item_grp else None
    brnd = tuple(brnd) if isinstance(brnd, (list, tuple)) else (brnd,) if brnd else None
    item_category = tuple(item_category) if isinstance(item_category, (list, tuple)) else (item_category,) if item_category else None

    # Base query
    query = """
        SELECT pr.name AS pricing_rule_name, pri.item_code, pri.brand, pri.item_group, pri.item_category,
            pr.free_qty, pr.min_qty, pr.free_item, pr.priority
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
            AND (
                (pr.applicable_for = 'Customer' AND pr.customer = %(customer)s) OR
                (pr.applicable_for = 'Site' AND pr.site IN %(sites)s) OR
                (pr.applicable_for = 'Customer Group' AND pr.customer_group IN %(customer_group)s)
            )
            AND (
                (pr.apply_on = 'Item Code' AND pri.item_code IN %(item_code)s) OR
                (pr.apply_on = 'Brand' AND pri.brand IN %(brnd)s) OR
                (pr.apply_on = 'Item Group' AND pri.item_group IN %(item_grp)s) OR
                (pr.apply_on = 'Item Category' AND pri.item_category IN %(item_category)s)
            )
            AND (
                hc.company_code IN %(company)s 
                AND hc.sales_organization IN %(sales_organization_code)s
                AND hc.site IN %(sites)s
                AND hc.distribution_channel IN %(dc)s
                AND hc.customer_hierarchy IN %(customer_hierarchy)s
                AND hc.customer_group IN %(customer_group)s
            )
    """

    # Parameters for query
    params = {
        "customer": customer,
        "sites": sites,
        "customer_group": customer_group,
        "current_date": current_date,
        "item_code": item_code if item_code else ('',),
        "brnd": brnd if brnd else ('',),
        "item_grp": item_grp if item_grp else ('',),
        "item_category": item_category if item_category else ('',),
        "company": company if company else ('',),
        "sales_organization_code": sales_organization_code if sales_organization_code else ('',),
        "dc": dc if dc else ('',),
        "customer_hierarchy": customer_hierarchy if customer_hierarchy else ('',)
    }

    # Execute the query and fetch the results
    pricing_rules = frappe.db.sql(query, params, as_dict=True)
    print("FOC Rule -------------------->", pricing_rules)
    
    return pricing_rules
