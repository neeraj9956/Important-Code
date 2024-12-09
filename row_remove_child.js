function restrict_foc_for_article_exclusion(frm, row) {
    frappe.call({
        method: "custom_selling.sales_order.article_exclusion_for_foc",
        args: {
            row: JSON.stringify(row),
            company: frm.doc.company,
            customer: frm.doc.customer || null,
            region: frm.doc.custom_region_code || null, 
            site: frm.doc.custom_site,
            dc: frm.doc.custom_distribution_channel_code,
            date_time: frappe.datetime.now_datetime()
        },
        callback: function (response) {
            if (response.message && response.message.excluded) {
                if (row.item_code === response.message.item_code && row.is_free_item) {
                    let index = frm.doc.items.findIndex(item => item.item_code === row.item_code);
                    if (index !== -1) {
                        frm.doc.items.splice(index, 1);
                        frm.refresh_field('items');
                        frm.save();

                    }
                }
                frappe.throw(__(`The item ${row.item_code} is excluded from sale in this area.`));

                
            }
        }
    });
}
