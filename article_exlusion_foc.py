@frappe.whitelist()
def article_exclusion_for_foc(row, company,site, dc, date_time, customer=None, region=None):
    try:
        if isinstance(row, str):
            row = json.loads(row)
        item_code = row.get("item_code")
        if not item_code:
            frappe.throw(_("Item code is missing in the row data."))

        query = """
            SELECT 
                aemd.channel,
                aemd.customer,
                aemd.region_code
            FROM
                tabArticle Exclusion ae
            JOIN
                tabArticle Exclusion Multiselect Details aemd ON aemd.parent = ae.name
            WHERE
                ae.company_code = %(company)s
                AND ae.site = %(site)s
                AND ae.item = %(item)s
                AND ae.start_date_time <= %(datetime)s
                AND ae.end_date_time >= %(datetime)s
                AND ae.is_active = 1
                AND (
                    (aemd.channel = %(dc)s AND aemd.customer = %(customer)s AND aemd.region_code = %(region)s) OR
                    (aemd.channel = %(dc)s AND aemd.customer IS NULL AND aemd.region_code  = %(region)s) OR
                    (aemd.channel = %(dc)s AND aemd.customer = %(customer)s AND aemd.region_code IS NULL) OR
                    (aemd.channel = %(dc)s AND aemd.customer IS NULL AND aemd.region_code IS NULL) OR
                    (aemd.channel IS NULL AND aemd.customer = %(customer)s AND aemd.region_code  = %(region)s) OR
                    (aemd.channel IS NULL AND aemd.customer IS NULL AND aemd.region_code  = %(region)s) OR
                    (aemd.channel IS NULL AND aemd.customer IS NULL AND aemd.region_code IS NULL)
                )
            ORDER BY
                (aemd.channel IS NOT NULL) DESC,
                (aemd.region_code IS NOT NULL) DESC,
                (aemd.customer IS NOT NULL) DESC
        """
        filters = {
            "company": company,
            "site": site,
            "item": item_code,
            "datetime": date_time,
            "dc": dc,
            "customer": customer,
            "region": region
        }

        frappe.log_error(message=filters, title="Filters Debug")
        exclusion_data = frappe.db.sql(query, filters, as_dict=True)
        print("Exclusion for FOC",exclusion_data)
        frappe.log_error(message=exclusion_data, title="Exclusion Data Debug")

        if exclusion_data:
            return {
                "excluded": True,
                "item_code": item_code,
                "message": f"The item {item_code} is excluded from sale in this area.",
                "details": exclusion_data
            }

        return {"excluded": False, "item_code": item_code}

    except Exception as e:
        frappe.log_error(message=str(e), title="Error in article_exclusion function")
        frappe.throw(_("An error occurred while checking article exclusion. Please contact your administrator."))
