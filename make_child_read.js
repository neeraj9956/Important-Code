
            frm.fields_dict['locations'].grid.grid_rows.forEach(row => {
                // Check if the condition is met for the current row
                const is_picking_completed = row.doc.custom_picking_status === "Picking Completed";
        
                // Iterate over each field in the child table and toggle enable/disable for the row
                frappe.meta.get_docfields("Pick List Item").forEach(field => {
                    frm.fields_dict['locations'].grid.toggle_enable(field.fieldname, !is_picking_completed, row.doc.idx);
                });
        
                // Additional handling for the else case to make the row editable
                if (!is_picking_completed) {
                    frappe.meta.get_docfields("Pick List Item").forEach(field => {
                        frm.fields_dict['locations'].grid.toggle_enable(field.fieldname, true, row.doc.idx);
                    });
                }
            });
