
frappe.ui.form.on("FOC", {
    refresh : frm => {
        (".btn-open-row").hide();
            for_item_code(frm);
    },

    apply_on : frm => {
        if (frm.doc.apply_on === "Item Group") {
            for_item_group(frm);
        }

        else if (frm.doc.apply_on === "Item Category") {
            for_item_category(frm);
        }

        else if (frm.doc.apply_on === "Brand") {
            for_brand(frm);
        }

        else {
            for_item_code(frm);
        }
    }
})

function for_item_code(frm) {
    const apply_on = frm.doc.apply_on;
    let sub_assembly_list_view = {
        "FOC Item": [
            {
                "fieldname": "item_code",
                "columns": 4
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
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
                "columns": 4
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
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
                "columns": 4
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
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
                "columns": 4
            }
        ]
    };
    frappe.model.user_settings.save(frm.doctype, "GridView", sub_assembly_list_view).then((r) => {
        frappe.model.user_settings[frm.doctype] = r.message || r;
        frappe.after_ajax(() => {
            frm.fields_dict.items.grid.reset_grid();
            frm.fields_dict.items.grid.refresh();
            // frm.fields_dict.stock_entry_detail.grid.reset_grid();
        });
        frm.refresh_fields("items")
    });
}
