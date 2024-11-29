frappe.ui.form.on('Pick List', {
    refresh(frm) {
        if (frm.is_new()) {
            setTimeout(() => {
                frm.page.set_indicator("In Progress", "blue");
            }, 100);
        }
        else
        {
            frm.page.set_indicator(frm.doc.status, "green");
        }
    }
});
frappe.ui.form.on('Pick List Item', {
    picked_qty: function (frm, cdt, cdn) {
        var row = frappe.get_doc(cdt, cdn);
        var sel = 'div.grid-row[data-idx="' + row.idx + '"]';
        $(sel).css('background-color', row.qty > row.picked_qty ? "#FFA500" : (row.qty === row.picked_qty ? "#80FF80" : ""));
    }
});
