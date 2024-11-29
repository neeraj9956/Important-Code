frappe.ui.form.on('Pick List', {
    scan_barcode: function (frm) {
        frm.doc.locations.map(row => {
            var sel = 'div.grid-row[data-idx="' + row.idx + '"]';
            $(sel).css('background-color', row.qty > row.picked_qty ? "#ffa500" : (row.qty === row.picked_qty ? "#80ff80" : ""));
        });
    },
});
