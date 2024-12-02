
frappe.ready(async () => {
    const currentUser = frappe.session.user;  // Get the current logged-in user

    // Subscribe to the user-specific event
    frappe.realtime.on(`item_selected_${currentUser}`, (data) => {
        console.log(data, "Item selected");

        // Find the table body element
        var tableBody = document.getElementById('custom-items-table-body');

        // Check if item code already exists in the table
        var existingRow = Array.from(tableBody.children).find(row => {
            return row.children[0].textContent === data.item_code;
        });

        if (existingRow) {
            // Update the existing row's quantity
            existingRow.children[1].textContent = data.qty;
        } else {
            // Create a new row
            var row = document.createElement('tr');

            // Create and insert item code cell
            var itemCodeCell = document.createElement('td');
            itemCodeCell.textContent = data.item_code;
            row.appendChild(itemCodeCell);

            // Create and insert quantity cell
            var qtyCell = document.createElement('td');
            qtyCell.textContent = data.qty;
            row.appendChild(qtyCell);

            // Insert other cells (Rate, Amount, Actions) as empty or default values
            var rateCell = document.createElement('td');
            rateCell.textContent = data.rate; // Add default or dynamic value if available
            row.appendChild(rateCell);

            var amountCell = document.createElement('td');
            amountCell.textContent = ''; // Add default or dynamic value if available
            row.appendChild(amountCell);

            var actionsCell = document.createElement('td');
            actionsCell.textContent = ''; // Add default or dynamic value if available
            row.appendChild(actionsCell);

            // Append the new row to the table body
            tableBody.appendChild(row);
        }
    });
});
