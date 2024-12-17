
frappe.ui.form.on("FOC", {
    valid_from: function (frm)
    {
        let current_date = frappe.datetime.now_date();

        if (frm.doc.valid_from && frm.doc.valid_from < current_date) {
            frm.set_value("valid_from", current_date);
            frappe.throw(__("Valid From date must be a future date. or current_date"));

        }
    },
    valid_upto: function (frm)
    {
        let current_date = frappe.datetime.now_date();

        if (frm.doc.valid_upto && frm.doc.valid_upto < current_date) {
            frm.set_value("valid_upto", current_date);
            frappe.throw(__("Valid From date must be a future date."));

        }
        
    },
    refresh: frm => {
        for_item_code(frm);
    },

    apply_on: frm => {
        (frm.doc.apply_on === "Item Group") ? for_item_group(frm) :(frm.doc.apply_on === "Item Category") ? for_item_category(frm) :
            (frm.doc.apply_on === "Brand") ? for_brand(frm) : for_item_code(frm);
    }
});    

function for_item_code(frm) {
    const apply_on = frm.doc.apply_on;
    let sub_assembly_list_view = {
        "FOC Item": [
            {
                "fieldname": "item_code",
                "columns": 2
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
            hide_edit_section(frm);
            frm.fields_dict.items.grid.reset_grid();
            frm.fields_dict.items.grid.refresh();
            // frm.fields_dict.stock_entry_detail.grid.reset_grid();
        });
        frm.refresh_fields("items")
    });
}

function for_item_group(frm) {
    const apply_on = frm.doc.apply_on;
    let sub_assembly_list_view = {
        "FOC Item": [
            {
                "fieldname": "item_group",
                "columns": 2
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
            hide_edit_section(frm);
            frm.fields_dict.items.grid.reset_grid();
            frm.fields_dict.items.grid.refresh();
            // frm.fields_dict.stock_entry_detail.grid.reset_grid();
        });
        frm.refresh_fields("items")
    });
}

function for_item_category(frm) {
    const apply_on = frm.doc.apply_on;
    let sub_assembly_list_view = {
        "FOC Item": [
            {
                "fieldname": "item_category",
                "columns": 2
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
            hide_edit_section(frm);
            frm.fields_dict.items.grid.reset_grid();
            frm.fields_dict.items.grid.refresh();
            // frm.fields_dict.stock_entry_detail.grid.reset_grid();
        });
        frm.refresh_fields("items")
    });
}

function for_brand(frm) {
    const apply_on = frm.doc.apply_on;
    let sub_assembly_list_view = {
        "FOC Item": [
            {
                "fieldname": "brand",
                "columns": 2
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
            hide_edit_section(frm);
            frm.fields_dict.items.grid.reset_grid();
            frm.fields_dict.items.grid.refresh();
            // frm.fields_dict.stock_entry_detail.grid.reset_grid();
        });
        frm.refresh_fields("items")
    });
}
frappe.ui.form.on("FOC Item",
    {
        items_add(frm, cdt, cdn) {
            hide_edit_section(frm);
            
        }

    },
);

function hide_edit_section(frm)
{
    $(document).ready(function() {
        $('.btn-open-row').hide(); 
        $('.btn-open-row svg.icon').hide(); 
    });
}

