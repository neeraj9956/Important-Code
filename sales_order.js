
frappe.ui.form.on("Sales Order", {
    setup: frm => {
        frm.set_query('uom', 'items', function (doc, cdt, cdn) {
            let row = locals[cdt][cdn];
            if (row.item_code) {
                return {
                    query: "jaleel_ho.custom_selling.sales_order.get_item_uom",
                    filters: {
                        'item_code': row.item_code
                    }
                }
            }
        })

        frm.set_query('custom_address', 'items', function (doc, cdt, cdn) {
            return {
                filters: {
                    "link_name": frm.doc.customer,
                    "link_doctype": "Customer"
                }
            };
        });
    },
    // shipping_address_name: function(frm) {
    //     if (frm.doc.shipping_address_name) {
    //         frappe.call({
    //             method: "jaleel_ho.custom_selling.customer.get_address_region_code",
    //             args: {
    //                 doc_name: frm.doc.shipping_address_name
    //             },
    //             callback: function (response) {
    //                 if (response.message) {
    //                     frm.set_value('custom_region_code', response.message);
    //                 }
    //                 else {
    //                     frappe.msgprint(__('No region code found for the selected address.'));
    //                 }
    //             }
    //         });
    //     } else {
    //         frm.set_value('custom_region_code', '');
    //     }
    // },
    onload_post_render: frm => {
        frm.toggle_display('custom_pick_list_status', frm.doc.custom_distribution_channel_code != '02');
    },

    onload: frm => {
        if (!frm.doc.delivery_date) {
            frm.set_value('delivery_date', frappe.datetime.nowdate());
        }
        customDeleteionRequest(frm)
        // setPickingStatus(frm);
        if (frm.doc.docstatus === 1 && frm.doc.custom_pick_list_status === 'Completed' && ['11', '13', '07', '15'].includes(frm.doc.custom_distribution_channel_code)) {
            // addCreatePicklistButton(frm);
            let all_delivered = true; 

            
            if(['07', '15'].includes(frm.doc.custom_distribution_channel_code)){
            frm.doc.items.forEach(item => {
                if ( item.picked_qty === 0) {
                    all_delivered = false;
                    return false; 
                }
            });}
            else{
                frm.doc.items.forEach(item => {
                    if (item.delivered_qty === 0 || item.picked_qty === 0) {
                        all_delivered = false;
                        return false; 
                    }
                });
            }

            if (all_delivered) {
                frm.add_custom_button(__('Create Sales Invoice'), function () {
                    frm.call({
                        method : "jaleel_ho.custom_selling.sales_order.from_so_create_sales_invoice",
                        args : {
                            "doc" : frm.doc.name
                        },
                        callback: function(response) {
                            if (response && response.message) {
                                frappe.msgprint(__('Sales Invoice {0} created successfully', [response.message]));
                                frappe.set_route('Form', 'Sales Invoice', response.message);
                                frm.remove_custom_button(__('Create Sales Invoice'));
                                frm.doc.refresh()
                            }
                        }
                    })
                }).addClass('btn-primary');
            }
        }

        const updateItem = (e) => {
            const d = locals[e.target.dataset.doctype][e.target.dataset.name];
            if (d && d.item_code) {
                setTimeout(() => {
                    frappe.call({
                        method: "jaleel_ho.integration.websocket_server.notify_item_selected",
                        args: {
                            "row": JSON.stringify(d)
                        }
                    });
                }, 100);
            }
        };

        frm.fields_dict['items'].grid.wrapper.on('change', 'input[data-fieldname="item_code"]', updateItem);
        frm.fields_dict['items'].grid.wrapper.on('change', 'input[data-fieldname="qty"]', updateItem);

        frm.set_query('custom_distribution_channel_code', function(doc){
            if (doc.customer){
                return{
                    query: "jaleel_ho.custom_selling.sales_order.get_distribution_channel_based_on_customer",
                    filters:{
                        'customer':doc.customer
                    }
                }
            }
            else{
                frappe.msgprint({
                    title: __('Missing Information'),
                    message: __('Please select a customer before fetching Distribution channel.'),
                    indicator: 'red'
                });
                return; 
            }
        })
        if (!frm.doc.customer){
            frm.set_df_property('custom_mode_of_payment_', 'read_only',1 );  
        }

        frm.fields_dict['scan_barcode'].$input.on('paste', function(e) {
            e.preventDefault();
            frappe.msgprint(__('Pasting is not allowed in the Scan Barcode field.'));
        });
    },

    refresh(frm) {
        setTimeout(() => {
            frm.fields_dict.items.grid.add_multiple_rows = false; // Disable the "Add Multiple" button
            frm.fields_dict.items.grid.wrapper.find('.grid-add-multiple-rows').hide();
            frm.fields_dict.items.grid.wrapper.find('.grid-download').hide();
        }, 1000);
        const fieldsToHide = [
            "currency_and_price_list","custom_total_amt_including_vat","set_warehouse","accounting_dimensions_section","custom_customer_no","custom_location_code","custom_offer_trigger",
            "custom_user","custom_transportation_zone_title","custom_reference_code_1","custom_reference_code_1_desc","custom_reference_code_2",
            "custom_reference_code_2_desc","custom_scheme_code","custom_accumulative_loyalty_points","custom_reference_code_3","custom_reference_code_3_desc",
            "po_no","custom_reference_code_4","custom_reference_code_4_desc","custom_debit_to","custom_site" , 'sales_team_section_break' , 'section_break1'  , 'additional_info_section'];
        fieldsToHide.map(field => {
            frm.set_df_property(field, 'hidden', 1);
        });

        const readOnlyFields = ['order_type'];
            readOnlyFields.forEach(field => {
            frm.set_df_property(field, 'read_only', 1);
        });




        if (!frm.doc.delivery_date) {
            frm.set_value('delivery_date', frappe.datetime.nowdate());
        }
        // frm.set_df_property('custom_region_code', 'reqd', 1);
        frm.set_df_property('custom_pick_list_status', 'read_only', 1);
        frm.set_df_property('custom_distribution_channel_code', 'reqd', 1);

        // setPickingStatus(frm);
        if (!frm.doc.custom_site && !frm.doc.custom_location_code && !frm.doc.custom_sales_organization_code) {
            frappe.db.get_doc("Jaleel Settings")
                .then((settings) => {
                    frm.set_value("custom_site", settings.site_code);
                    frm.set_value("custom_location_code", settings.location_code);
                    frm.set_value("custom_sales_organization_code", settings.sales_organization_code);
                });
        }
        // update_custom_total_amt_including_vat(frm);
        if (frm.doc.docstatus === 1) {
            // addCreatePicklistButton(frm);
        }
        if (frm.doc.__islocal) {

            frm.add_custom_button(__('New Tab'), function () {
                frm.opened_new_tab = true;
                window.open(document.location.origin + '/so_details', '_blank');
            });

            frm.add_custom_button(__('New Window'), function () {
                frm.opened_new_window = true;
                window.open(document.location.origin + '/so_details', '_blank', 'width=1200,height=600');
            });
        }
        else {
            frm.page.sidebar.hide();
        }

        const buttonsToRemove = ['Pick List', 'Work Order', 'Material Request', 'Request for Raw Materials', 'Purchase Order',
                                'Project', 'Payment Request', 'Sales Invoice'];
        setTimeout(() => {
            buttonsToRemove.forEach(button => {
                frm.page.remove_inner_button(button, 'Create');
            });
        }, 2000);
        if (
            frm.doc.docstatus === 1 && (frm.doc.custom_distribution_channel_code === "2" || frm.doc.custom_distribution_channel_code === "02")
        ) {
            const childTable = frm.doc.custom_mode_of_payment || [];
            const allRowsWithoutPaymentEntry = childTable.every(row => !row.payment_entry);

            if (allRowsWithoutPaymentEntry) {
                frm.add_custom_button(__('Create Advance Payments & Invoice'), () => {
                    frappe.call({
                        method: "jaleel_ho.custom_selling.sales_order.create_advance_payments_and_invoice",
                        args: { docname: frm.doc.name },
                        callback: function(r) {
                            if (r.message) {
                                frappe.msgprint(r.message);
                                frm.refresh();
                            }
                        },
                        freeze: true,
                        freeze_message: __("Processing...")
                    });
                });
                frm.add_custom_button(__('Edit Payments Table'), () => {
                    // Fetch mode of payment options
                    frappe.call({
                        method: "frappe.client.get_list",
                        args: {
                            doctype: "Mode of Payment",
                            fields: ["name"]
                        },
                        callback: function(response) {
                            const modeOfPaymentOptions = response.message.map(row => row.name);

                            const dialog = new frappe.ui.Dialog({
                                title: __("Edit Payments Table"),
                                fields: [
                                    {
                                        fieldname: "payments_table",
                                        fieldtype: "Table",
                                        label: "Payment Methods",
                                        cannot_add_rows: false,
                                        data: childTable.map(row => ({
                                            mode_of_payment: row.mode_of_payment,
                                            amount: row.amount
                                        })),
                                        fields: [
                                            {
                                                fieldtype: "Select",
                                                fieldname: "mode_of_payment",
                                                label: "Mode of Payment",
                                                in_list_view: true,
                                                options: modeOfPaymentOptions.join('\n')
                                            },
                                            {
                                                fieldtype: "Currency",
                                                fieldname: "amount",
                                                label: "Amount",
                                                in_list_view: true,
                                            }
                                        ]
                                    }
                                ],
                                primary_action_label: __("Update Payments"),
                                primary_action(data) {
                                    // Calculate total amount
                                    const totalAmount = (data.payments_table || []).reduce((sum, row) => sum + (row.amount || 0), 0);

                                    // Validate against custom_advance_total
                                    if (totalAmount !== frm.doc.custom_advance_total) {
                                        frappe.msgprint({
                                            title: __('Validation Error'),
                                            indicator: 'red',
                                            message: __('The total amount must equal the custom advance total ({0}). Current total is {1}.', [frm.doc.custom_advance_total, totalAmount])
                                        });
                                        return;
                                    }

                                    // Clear original child table and update with dialog data
                                    frappe.model.clear_table(frm.doc, "custom_mode_of_payment");

                                    // Loop through dialog data to add to the original child table
                                    (data.payments_table || []).forEach(rowData => {
                                        const newRow = frm.add_child("custom_mode_of_payment");
                                        newRow.mode_of_payment = rowData.mode_of_payment;
                                        newRow.amount = rowData.amount;
                                    });

                                    frm.refresh_field("custom_mode_of_payment");
                                    dialog.hide();
                                    frappe.msgprint(__('Payment table updated. Please click "Update" to save changes.'));
                                }
                            });

                            dialog.show();
                        }
                    });
                }).addClass("btn-secondary");
            }
        }
    },

    // validate(frm) {
        // if (frm.doc.__islocal) {
        // frm.doc.items.map( row => {
        //     frappe.call({
        //         method : "jaleel_ho.custom_selling.sales_order.max_qty",
        //         args : {
        //             "row" : row,
        //             "customer" : frm.doc.customer,
        //             "site" : frm.doc.custom_site,
        //             "dc" : frm.doc.custom_distribution_channel_code,
        //             "date_time" : frm.doc.custom_so_date_time
        //         }
        //     });
        // })
        // }

    custom_get_advances_received: function (frm) {
        // This function is triggered when the button is clicked
        frm.call({
            method: 'set_advances',
            doc: frm.doc, // Pass the current document as context
            callback: function (r) {
                if (r.message) {
                    // Clear the child table before adding new entries
                    frm.clear_table('advances'); // Replace 'advances' with the actual child table field name

                    // Loop through the response and add rows to the child table
                    $.each(r.message, function (i, d) {
                        let row = frm.add_child('advances'); // Add a new row to the child table
                        row.reference_type = d.reference_type;
                        row.reference_name = d.reference_name;
                        row.remarks = d.remarks;
                        row.advance_amount = d.advance_amount;
                        row.allocated_amount = d.allocated_amount;
                        row.ref_exchange_rate = d.ref_exchange_rate;
                        row.account = d.account;
                    });

                    // Refresh the field to show updated data in the child table
                    frm.refresh_field('advances');
                }
            }
        });
    },
    after_cancel: function (frm) {
        frm.doc.items.map(row => {
            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.stock_release_on_order_cancellation",
                args: {
                    "row": row,
                    "manual_cancellation": true
                }
            });
        })
    },
    custom_distribution_channel_code: function (frm) {
        frm.toggle_display('custom_pick_list_status', frm.doc.custom_distribution_channel_code != '02');
        frm.toggle_display('scan_barcode', frm.doc.custom_distribution_channel_code == '02');
        frm.fields_dict['scan_barcode'].$wrapper.find('input').on('copy paste cut', function (e) {
            e.preventDefault();
        });

        if (frm.doc.custom_multiple_shipment != 1 && frm.doc.custom_distribution_channel_code && ["12", "14", "11", "13"].includes(frm.doc.custom_distribution_channel_code)) {
            frm.set_df_property('custom_multiple_shipment', 'hidden', 0);
            frappe.msgprint("Multiple Shipment is unchecked, please ensure this before submission.")

        } else {
            frm.set_df_property('custom_multiple_shipment', 'hidden', 1);
        }
        frm.refresh_field('custom_multiple_shipment');
    },
    after_save: function (frm) {
        frm.doc.items.map(row => {
            set_available_qty_excluded_reservation(frm, row.doctype, row.name);
        });

        // if (frm.doc.custom_multiple_shipment != 1 && frm.doc.custom_distribution_channel_code && ["12", "14", "11", "13"].includes(frm.doc.custom_distribution_channel_code)) {
        //     frappe.msgprint("Multiple Shipment is unchecked, please ensure this before submission.")
        // }
    },
    before_save: function (frm) {
        let total_allocated_amount = 0;
        let total_payment_amount = 0;
        update_custom_total_amt_including_vat(frm)
        // Sum up allocated_amount from custom_advances
        if (frm.doc.custom_advances) {
            frm.doc.custom_advances.forEach(function (row) {
                total_allocated_amount += row.allocated_amount || 0;
            });
        }

        // Sum up amount from custom_mode_of_payment
        if (frm.doc.custom_mode_of_payment) {
            frm.doc.custom_mode_of_payment.forEach(function (row) {
                total_payment_amount += row.amount || 0;
            });
        }

        // Set the calculated total to custom_advance_total field
        frm.set_value('custom_advance_total', total_allocated_amount + total_payment_amount);
    },
    customer: function(frm) {
        // frm.set_df_property('custom_distribution_channel_code', 'hidden', 0);
        if (frm.doc.customer) {
            frappe.call({
                method: 'jaleel_ho.custom_selling.sales_order.get_customer_mode_of_payment', 
                args: {
                    customer_id: frm.doc.customer
                },
                callback: function(r) {
                    if (r.message) {
                        let modeOfPayment = r.message;

                        frm.set_value('custom_mode_of_payment_', modeOfPayment);
                        frm.refresh_field('custom_mode_of_payment_');      

                        let containsOnlyCash = modeOfPayment.every(item => item.mode_of_payment.toLowerCase() === 'cash');

                        frm.set_df_property('custom_mode_of_payment_', 'read_only', containsOnlyCash ? 1 : 0);        
                    }
                }
            });

            // Fetch and set the custom transportation zone code
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Customer',
                    fieldname: 'custom_transportation_zone_code',
                    filters: { name: frm.doc.customer }
                },
                callback: function(response) {
                    if (response.message) {
                        let transportationZoneCode = response.message.custom_transportation_zone_code;
                        frm.set_value('custom_transportation_zone_code', transportationZoneCode);
                    }
                }
            });
            // Fetch and set the custom transportation zone code
            frappe.call({
                method: 'frappe.client.get_value',
                args: {
                    doctype: 'Sales Person',
                    fieldname: 'sales_person_name',
                    filters: { custom_customer: frm.doc.customer }
                },
                callback: function(response) {
                    if (response.message) {
                        let name = response.message.sales_person_name;
                        console.log("nameee" , name)
                        frm.set_value('custom_sales_person', name);
                    }
                }
            });
        }
    }   
});


frappe.ui.form.on("Sales Order Item", {
    
    item_code: function (frm, cdt, cdn) {
        checkPickingSequence(frm, cdt, cdn);
        selective_item(frm, cdt, cdn);
        get_discounted_item_price(frm, cdt, cdn);
        article_exclusion(frm, cdt, cdn);
        item_substitution(frm, cdt, cdn);
        msp_price(frm, cdt, cdn);
        set_actual_ordered_qty(frm, cdt, cdn)
        // fetchItemTaxTemplate(frm, cdt, cdn);
        validate_available_qty(frm, cdt, cdn);
        check_pricing_rule(frm, cdt, cdn);
        
    },

    qty: function (frm, cdt, cdn) {
        fetch_foc_and_append_row(frm, cdt, cdn);
        // se
        max_qty(frm, cdt, cdn);
        update_custom_amount_including_vat(frm, cdt, cdn);
    },

    uom: function (frm, cdt, cdn) {
        get_discounted_item_price(frm, cdt, cdn);
        checkPickingSequence(frm, cdt, cdn);
        item_substitution(frm, cdt, cdn);
    },

    custom_requested_qty: function (frm, cdt, cdn) {
        restrict_qty_increase_for_foc(frm, cdt, cdn);
        set_actual_ordered_qty(frm, cdt, cdn)
        max_qty(frm, cdt, cdn);
        get_discounted_item_price(frm, cdt, cdn);
    },

    rate: function (frm, cdt, cdn) {
        msp_price(frm, cdt, cdn);
    },

    items_remove(frm, cdt, cdn) {
        update_custom_total_amt_including_vat(frm);
        frm.save()
    },
    custom_amount_including_vat: function (frm) {
        update_custom_total_amt_including_vat(frm);
    }
});
let validate_available_qty = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];

    setTimeout(() => {
        if (row && row.item_code && row.warehouse) {

            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.get_reserved_available_qty",
                args: {
                    "row": JSON.stringify(row) 
                },
                callback: function (r) {
                    // Check if available quantity is 0
                if (typeof r.message === 'number' && r.message <= 0) {
                        frappe.model.clear_doc(cdt, cdn);
                        frm.refresh_field('items');

                        frappe.msgprint({
                            title: __('No Stock Available'),
                            message: __('The selected item {0} in warehouse {1} has no available stock.', [row.item_code, row.warehouse]),
                            indicator: 'red'
                        });

                        
                    }
                },
                error: function (err) {
                    console.error("Error fetching reserved available qty:", err);
                    frappe.msgprint(__('Error fetching stock availability.'));
                }
            });
        }
    }, 200)
};

let stock_reserve = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row && (row.item_code || row.qty) && row.warehouse) {
        frm.save().then(() => {
            console.log("Sales Order Saved");
        }).catch((error) => {
            console.error("Error saving Sales Order:", error);
        });
    }
}

let selective_item = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row && (row.item_code || row.qty)) {
        setTimeout(() => {
            frappe.call({
                method: "jaleel_ho.integration.websocket_server.notify_item_selected",
                args: {
                    "row": JSON.stringify(row)
                }
            });
        }, 100);
    }
}

let article_exclusion = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row && row.item_code) {
        setTimeout(() => {
            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.article_exclusion",
                args: {
                    "row": row,
                    "customer": frm.doc.customer,
                    "company": frm.doc.company,
                    "site": frm.doc.custom_site,
                    "dc": frm.doc.custom_distribution_channel_code,
                    "region": frm.doc.custom_region_code,
                    "date_time": frm.doc.custom_so_date_time
                },
                callback: function (r) {
                    if (r.message) {
                        frappe.model.clear_doc(cdt, cdn);
                        refresh_field('items');
                    }
                }
            });
        }, 100);
    }
}

let max_qty = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row && row.qty) {
        frappe.call({
            method: "jaleel_ho.custom_selling.sales_order.max_qty",
            args: {
                "row": row,
                "customer": frm.doc.customer,
                "site": frm.doc.custom_site,
                "dc": frm.doc.custom_distribution_channel_code,
                "date_time": frm.doc.custom_so_date_time,
            }
        });
    }
}


// let get_discounted_item_price = async (frm, cdt, cdn) => {
    // let jaleel_set = await frappe.db.get_doc("Jaleel Settings")
//     let row = locals[cdt][cdn];
//     if (row && row.item_code && jaleel_set.price_discount_mongodb === 1) {
//         // Check if custom_item_number is empty
//         if (!row.custom_item_number) {
//             // Fetch custom_item_number using item_code
//             await frappe.db.get_value("Item", row.item_code, "custom_item_number")
//                 .then(response => {
//                     if (response && response.message["custom_item_number"]) {
//                         row.custom_item_number = response.message["custom_item_number"]; // Set the custom_item_number
//                     } else {
//                         frappe.msgprint("No custom item number found for the provided item code!");
//                         return; // Exit the function if no custom item number found
//                     }
//                 })
//                 .catch(err => {
//                     frappe.msgprint("Error fetching custom item number: " + err.message);
//                     return; // Exit the function on error
//                 });
//         }

//         let doc = {};
//         doc["item_no"] = row.custom_item_number;
//         doc["customer_no"] = frm.doc.customer;

//         if (frm.doc.custom_distribution_channel_code) {
//             doc["distribution_channel_code"] = frm.doc.custom_distribution_channel_code;
//         }
//         if (frm.doc.custom_location_code) {
//             doc["location_code"] = frm.doc.custom_location_code;
//         }
//         if (frm.doc.custom_sales_organization_code) {
//             doc["sales_organization_code"] = frm.doc.custom_sales_organization_code;
//         }
//         if (frm.doc.custom_customer_hierarchy) {
//             doc["customer_hierarchy"] = frm.doc.custom_customer_hierarchy;
//         }

//         // Only call the method if the doc has at least one key-value pair
//         if (Object.keys(doc).length > 0) {
//             frappe.call({
//                 method: "jaleel_ho.custom_selling.sales_order.get_discounted_item_price",
//                 args: {
//                     "doc": doc
//                 },
//                 callback: function (r) {
//                     if (r.message && r.message != "No Price Found For this combination") {
//                         setTimeout(() => {
//                             row.rate = r.message.sales_price;
//                             refresh_field("rate", cdn, "items");
//                             stock_reserve(frm, cdt, cdn);
//                             // set_available_qty_excluded_reservation(frm, cdt, cdn)
//                         }, 1000);
//                     } else {
//                         frappe.model.clear_doc(cdt, cdn);
//                         refresh_field('items');
//                         frappe.msgprint("No Price Found For this combination!")
//                     }
//                 }
//             });
//         }
//     }
// }

let get_discounted_item_price = async (frm, cdt, cdn) => {
    let jaleel_set = await frappe.db.get_single_value("Jaleel Settings", "price_discount_mongodb")
    let row = locals[cdt][cdn];
    if (row && row.item_code && jaleel_set === 1) {
        // Check if custom_item_number is empty
        if (!row.custom_item_number) {
            // Fetch custom_item_number using item_code
            await frappe.db.get_value("Item", row.item_code, "custom_item_number")
                .then(response => {
                    if (response && response.message["custom_item_number"]) {
                        row.custom_item_number = response.message["custom_item_number"]; // Set the custom_item_number
                    } else {
                        frappe.msgprint("No custom item number found for the provided item code!");
                        return; // Exit the function if no custom item number found
                    }
                })
                .catch(err => {
                    frappe.msgprint("Error fetching custom item number: " + err.message);
                    return; // Exit the function on error
                });
        }

        let doc = {
            "item_no": row.custom_item_number,
            "customer_no": frm.doc.customer
        };

        if (frm.doc.custom_distribution_channel_code) {
            doc["distribution_channel_code"] = frm.doc.custom_distribution_channel_code;
        }
        if (frm.doc.custom_location_code) {
            doc["location_code"] = frm.doc.custom_location_code;
        }
        if (frm.doc.custom_sales_organization_code) {
            doc["sales_organization_code"] = frm.doc.custom_sales_organization_code;
        }
        if (frm.doc.custom_customer_hierarchy) {
            doc["customer_hierarchy"] = frm.doc.custom_customer_hierarchy;
        }

        // Only call the method if the doc has at least one key-value pair
        if (Object.keys(doc).length > 0) {
            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.get_discounted_item_price",
                args: {
                    "doc": doc
                },
                callback: function (r) {
                    if (r.message && r.message != "No Price Found For this combination") {
                        setTimeout(() => {
                            row.rate = r.message.sales_price;
                            row.custom_rate_including_vat = r.message.price_with_tax;
                          

                            // Check if tax_percent is present and set the item_tax_template based on tax_rate in the child table
                            if (r.message.tax_percent) {
                                row.custom_tax_percent=r.message.tax_percent
                                frappe.call({
                                    method: "frappe.client.get_list",
                                    args: {
                                        doctype: "Item Tax Template",
                                        filters: [
                                            ["Item Tax Template Detail", "tax_rate", "=", r.message.tax_percent] // Replace 10 with your desired tax_percent value
                                        ],
                                        fields: ["name"],
                                
                                
                                    },
                                    callback: function (res) {
                                        if (res.message && res.message.length > 0) {
                                            const itemTaxTemplateName = res.message[0].name;
                                          
                                            frappe.model.set_value(row.doctype, row.name, 'item_tax_template', itemTaxTemplateName);
                                            refresh_field("items");
                                        }
                                    }
                                });
                                
                            }

                            // Calculate custom_amount_including_vat
                            row.custom_amount_including_vat = row.custom_rate_including_vat * row.qty;

                            // Refresh fields             
                            refresh_field("custom_rate_including_vat", cdn, "items");
                            refresh_field("custom_amount_including_vat", cdn, "items");

                            // Additional functionality
                            
                            setTimeout(() => {
                                stock_reserve(frm, cdt, cdn);
                            }, 100);
                            // set_available_qty_excluded_reservation(frm, cdt, cdn)
                        }, 1000);
                    } else {
                        frappe.model.clear_doc(cdt, cdn);
                        refresh_field('items');
                        frappe.msgprint("No Price Found For this combination!");
                    }
                }
            });
        }
    }
    else if (row && row.item_code) {
        if (!row.custom_item_number) {
            // Fetch custom_item_number using item_code
            await frappe.db.get_value("Item", row.item_code, "custom_item_number")
                .then(response => {
                    if (response && response.message["custom_item_number"]) {
                        row.custom_item_number = response.message["custom_item_number"]; // Set the custom_item_number
                    } else {
                        frappe.msgprint("No custom item number found for the provided item code!");
                        return; // Exit the function if no custom item number found
                    }
                })
                .catch(err => {
                    frappe.msgprint("Error fetching custom item number: " + err.message);
                    return; // Exit the function on error
                });
        }

        // Fetch UOM if not already set
        if (!row.uom) {
            const uomResponse = await frappe.db.get_value("Item", row.item_code, "stock_uom");
            if (uomResponse && uomResponse.message["stock_uom"]) {
                row.uom = uomResponse.message["stock_uom"];
            } else {
                frappe.msgprint("No UOM found for the provided item code!");
                return; // Exit the function if no UOM is found
            }
        }

        let doc = {
            "item_no": row.custom_item_number,
            "customer_no": frm.doc.customer,
            "unit_of_measure_code": row.uom ,
            "qty":row.qty
        };

        if (frm.doc.custom_distribution_channel_code) {
            doc["distribution_channel_code"] = frm.doc.custom_distribution_channel_code;
        }
        if (frm.doc.custom_location_code) {
            doc["location_code"] = frm.doc.custom_location_code;
        }
        if (frm.doc.custom_sales_organization_code) {
            doc["sales_organization_code"] = frm.doc.custom_sales_organization_code;
        }
        if (frm.doc.custom_customer_hierarchy) {
            doc["customer_hierarchy"] = frm.doc.custom_customer_hierarchy;
        }
        if (frm.doc.customer_group) {
            doc["customer_group"] = frm.doc.customer_group;
        }
        if (frm.doc.custom_transportation_zone_code) {
            doc["transportation_zone_code"] = frm.doc.custom_transportation_zone_code;
        }
        

        // Only call the method if the doc has at least one key-value pair
        if (Object.keys(doc).length > 0) {
            frappe.call({
                method: "jaleel_ho.bulk_pricing.doctype.pricing.pricing.fetch_price",
                args: {
                    "doc": doc
                },
                callback: function (r) {
                    if (r.message && r.message != "No Price Found For this combination") {
                        setTimeout(() => {
                            row.rate = r.message.sales_price;
                            row.custom_rate_including_vat = r.message.price_with_tax;
                          

                            // Check if tax_percent is present and set the item_tax_template based on tax_rate in the child table
                            if (r.message.tax_percent) {
                                row.custom_tax_percent=r.message.tax_percent
                                frappe.call({
                                    method: "frappe.client.get_list",
                                    args: {
                                        doctype: "Item Tax Template",
                                        filters: [
                                            ["Item Tax Template Detail", "tax_rate", "=", r.message.tax_percent] // Replace 10 with your desired tax_percent value
                                        ],
                                        fields: ["name"],
                                
                                
                                    },
                                    callback: function (res) {
                                        if (res.message && res.message.length > 0) {
                                            const itemTaxTemplateName = res.message[0].name;
                                          
                                            frappe.model.set_value(row.doctype, row.name, 'item_tax_template', itemTaxTemplateName);
                                            refresh_field("items");
                                        }
                                    }
                                });
                                
                            }

                            // Calculate custom_amount_including_vat
                            row.custom_amount_including_vat = row.custom_rate_including_vat * row.qty;

                            // Refresh fields
                            refresh_field("rate", cdn, "items");
                            refresh_field("custom_rate_including_vat", cdn, "items");
                            refresh_field("custom_amount_including_vat", cdn, "items");


                            stock_reserve(frm, cdt, cdn);
                        }, 1000);  
                    } else {
                        frappe.model.set_value(cdt, cdn, "rate", null);
                        frappe.msgprint("No Price Found For this combination!");
                        setTimeout(() => {
                            stock_reserve(frm, cdt, cdn);
                        }, 500);
                    }
                }
            });
        }
    }
};


let item_substitution = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    setTimeout(() => {
        if (row.uom ) {
            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.items_substitution",
                args: {
                    "row": JSON.stringify(row),
                    "site": frm.doc.custom_site,
                    "date_time": frm.doc.custom_so_date_time
                },
                callback: function (r) {
                    if (r.message && Array.isArray(r.message) && r.message.length > 0) {
                        // r.message.forEach(function(item) {
                        show_item_selection_dialog(frm, cdt, cdn, r.message)
                    }
                }
            })
        }
    }, 1000);
}

let customDeleteionRequest = async (frm) => {

    if (frappe.user.has_role("Store Manager") && frm.doc.custom_distribution_channel_code == '02') {
        frm.doc.items.forEach(function (item) {

            if (item.custom_deletion_request == 1) {

                let cdn = item.name;

                // Select the row in the grid for this item
                frm.get_field('items').grid.grid_rows_by_docname[cdn].select(true);
            }
        });
    }
};

let  = (frm, cdt, cdn, items) => {
    if (!items || items.length === 0) {
        return;
    }

    let dialog = new frappe.ui.Dialog({
        title: "Select Substitute Item",
        fields: [
            {
                label: 'Suggested Items',
                fieldname: 'item_selection',
                fieldtype: 'Table',
                cannot_add_rows: true, // Disable adding new rows in the dialog manually
                in_place_edit: false, // Disable in-place editing in the dialog
                data: items, // Set the data for the table
                get_data: () => {
                    return items;
                },
                fields: [
                    {
                        fieldname: 'substitution_item',
                        label: 'Substitution Item',
                        fieldtype: 'Data',
                        in_list_view: 1,
                    },
                    {
                        fieldname: 'substitution_item_group',
                        label: 'Item Group',
                        fieldtype: 'Data',
                        in_list_view: 1,
                    },
                    {
                        fieldname: 'substitution_item_brand',
                        label: 'Item Brand',
                        fieldtype: 'Data',
                        in_list_view: 1,
                    },
                    {
                        fieldname: 'substitute_item_uom',
                        label: 'UOM',
                        fieldtype: 'Data',
                        in_list_view: 1,
                    }
                ]
            }
        ],
        primary_action_label: 'Select',
        primary_action: function (data) {
            if (data.item_selection && data.item_selection.length > 0) {
                // let selected_item = data.item_selection[0];
                // let selected_items = data.item_selection.filter(item => item.selected);
                data.item_selection.map(selected_item => {
                    if (selected_item.__checked) {
                        let new_row = frappe.model.add_child(frm.doc, 'Sales Order Item', 'items'); // Adjust 'items' to your table fieldname
                        frappe.model.set_value(new_row.doctype, new_row.name, 'item_code', selected_item.substitution_item);
                        // frappe.model.set_value(cdt, cdn, 'item_code', selected_item.substitution_item);
                        frm.refresh_field('items');
                        cur_frm.refresh();
                        dialog.hide();
                    }
                })
            } else {
                frappe.msgprint(__('Please select an item.'));
            }
        }
    });
    dialog.show();
}


let set_actual_ordered_qty = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    if (row.custom_requested_qty <= row.custom_available_qty && row.custom_requested_qty > 0) {
        row.qty = row.custom_requested_qty;
        refresh_field("qty", cdn, "items");
    }
    else {
        if (row.custom_available_qty) {
            row.qty = row.qty + row.custom_available_qty
            row.custom_difference_qty = row.custom_requested_qty - row.qty;
            refresh_field("qty", cdn, "items");
            refresh_field("custom_difference_qty", cdn, "items");
        }
        else if (row.custom_requested_qty > row.qty && row.custom_available_qty == 0){

            refresh_field("qty", cdn, "items");
        }
        else {
            row.qty = row.custom_requested_qty;
            refresh_field("qty", cdn, "items");
            refresh_field("custom_difference_qty", cdn, "items");
        }
    }
    max_qty(frm, cdt, cdn);
}

let set_available_qty_excluded_reservation = async (frm, cdt, cdn) => {
    frm.refresh_field("items");
}

let msp_price = async (frm, cdt, cdn) => {
    let row = locals[cdt][cdn];
    setTimeout(() => {
        if (row.rate < row.custom_msp) {
            frappe.msgprint({
                title: __('Price Alert'),
                message: __('The Selling Rate of {0} {1} is below the Moving Average Price {2}. Please check the pricing.', [row.item_name, row.rate, row.custom_msp]),
                indicator: 'blue'
            });
        }
    }, 2000);
}

function addCreatePicklistButton(frm) {
    frm.add_custom_button(__('Create Picklists'), function () {
        openPicklistDialog(frm);  // Open the dialog when the button is clicked
    }).addClass('btn-primary');
}

function openPicklistDialog(frm) {
    const dialog = new frappe.ui.Dialog({
        title: __('Filter Pending Items by Delivery Date and Address'),
        fields: [
            {
                label: 'From Date',
                fieldname: 'from_date',
                fieldtype: 'Date',
                reqd: 1  // Make the from date mandatory
            },
            {
                label: 'To Date',
                fieldname: 'to_date',
                fieldtype: 'Date',
                reqd: 1  // Make the to date mandatory
            },
            {
                label: 'Address',
                fieldname: 'address',
                fieldtype: 'Link',
                options: 'Address',
                reqd: 1
            },
            {
                fieldtype: 'Section Break'
            },
            {
                label: 'Filtered Items',
                fieldname: 'filtered_items',
                fieldtype: 'Table',
                cannot_add_rows: true,  // Disallow adding rows manually
                data: [],
                fields: [
                    {
                        fieldtype: 'Data',
                        fieldname: 'item_code',
                        label: __('Item Code'),
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: 'Float',
                        fieldname: 'qty',
                        label: __('Qty'),
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: 'Date',
                        fieldname: 'delivery_date',
                        label: __('Delivery Date'),
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: 'Data',
                        fieldname: 'location',
                        label: __('Location'),
                        read_only: 1,
                        in_list_view: 1
                    },
                    {
                        fieldtype: 'Data',
                        fieldname: 'uom',
                        label: __('UOM'),
                        read_only: 1,
                        in_list_view: 1
                    }
                ]
            }
        ],
        primary_action_label: 'Create Picklists',
        primary_action(values) {
            const selectedItems = dialog.fields_dict.filtered_items.grid.get_selected_children();

            if (selectedItems.length > 0) {
                const selectedData = selectedItems.map(row => ({
                    item_code: row.item_code,
                    qty: row.qty,
                    delivery_date: row.delivery_date,
                    name: row.name,
                    location: row.location,
                    uom: row.uom
                }));

                frappe.call({
                    method: 'jaleel_ho.custom_selling.sales_order.create_picklists',
                    args: {
                        items: selectedData,
                        doc: frm.doc.name
                    },
                    callback: function (response) {
                        if (response.message.response === "Pick Lists created successfully.") {
                            const itemRowMapping = response.message.item_row_mapping;

                            // Loop through each Sales Order item
                            frm.doc.items.forEach(function (item) {
                                // Check if the row name of this Sales Order item exists in item_row_mapping
                                if (itemRowMapping[item.name]) {
                                    // Set custom_pick_row_name to the value from item_row_mapping    
                                    frappe.model.set_value(item.doctype, item.name, 'custom_pick_row_name', itemRowMapping[item.name]);
                                }
                            });

                            // Refresh the 'items' field to reflect changes
                            frm.refresh_field('items');

                            // Show success message
                            frappe.msgprint('Picklists created and custom pick row names updated.');
                        } else {
                            frappe.msgprint('Failed to create picklists.');
                        }
                    },
                    error: function (error) {
                        frappe.msgprint("Error occurred while creating picklists.", error);
                        console.error(error);
                    }
                });

                dialog.hide();
            } else {
                frappe.msgprint("No items selected.");
            }
        }
    });

    dialog.show();

    // Event listeners for date filtering
    dialog.fields_dict.from_date.$input.on('change', function () {
        filterPendingItemsByDatesAndAddress(dialog, frm);
    });

    dialog.fields_dict.to_date.$input.on('change', function () {
        filterPendingItemsByDatesAndAddress(dialog, frm);
    });

    dialog.fields_dict.address.$input.on('awesomplete-selectcomplete', function () {
        filterPendingItemsByDatesAndAddress(dialog, frm);
    });
    dialog.fields_dict.address.$input.on('change', function () {
        filterPendingItemsByDatesAndAddress(dialog, frm);
    });
}

function filterPendingItemsByDatesAndAddress(dialog, frm) {
    const fromDate = dialog.get_value('from_date');
    const toDate = dialog.get_value('to_date');
    const address = dialog.get_value('address');

    if (fromDate && toDate) {
        const filteredRows = filterSalesOrderItems(frm, fromDate, toDate, address);

        dialog.fields_dict.filtered_items.df.data = [];
        dialog.fields_dict.filtered_items.grid.refresh();

        if (filteredRows.length > 0) {
            filteredRows.forEach(function (row) {
                dialog.fields_dict.filtered_items.df.data.push({
                    item_code: row.doc.item_code,
                    qty: row.doc.picking_qty,
                    delivery_date: row.doc.delivery_date,
                    name: row.doc.name,
                    location: row.doc.custom_location,
                    uom: row.doc.uom
                });
            });

            dialog.fields_dict.filtered_items.grid.refresh();
        } else {
            frappe.msgprint('No items found for the selected filters.');
        }
    }
}

function filterSalesOrderItems(frm, fromDate, toDate, address) {
    let filteredRows = [];

    frm.fields_dict.items.grid.grid_rows.forEach(function (row) {
        const deliveryDate = row.doc.delivery_date;
        const itemAddress = row.doc.custom_address;
        const itemStatus = row.doc.custom_status;

        // Filter by date range (mandatory) and address (if provided)
        if (itemStatus !== 'Completed') {
            if (deliveryDate >= fromDate && deliveryDate <= toDate) {
                if (!address || itemAddress === address) {
                    filteredRows.push(row);
                }
            }
        }
    });

    return filteredRows;
}



function checkPickingSequence(frm, cdt, cdn) {
    var item = locals[cdt][cdn];

    frappe.call({
        method: "jaleel_ho.custom_selling.sales_order.check_picking_sequence",
        args: {
            item_code: item.item_code,
            uom: item.uom
        },
        callback: function (r) {
            if (!r.message) {
                frappe.msgprint(__('Picking Sequence Configuration not found for this item.'));
                frappe.model.set_value(cdt, cdn, "item_code", null);  // Clears the item field if no configuration found
            }
        }
    });
}

function update_custom_total_amt_including_vat(frm) {
    let total = 0;

    frm.doc.items.forEach(item => {
        // Use custom amount if available, otherwise fallback to regular amount
        total += item.custom_amount_including_vat || item.amount;
    });

    frm.set_value('custom_total_amt_including_vat', total);
}







frappe.ui.form.on("Payment Method", {
    make_payment_2: function (frm, cdt, cdn) {
        console.log(frm, locals[cdt][cdn].idx);
        let payment_row = frappe.get_doc(cdt, cdn);

        if (payment_row.mode_of_payment == "Cash") {
            frappe.msgprint("Not allowed to make cash payment by machine");
        } else if (payment_row.payment_entry != undefined && payment_row.payment_entry != "") {
            frappe.msgprint("Payment entry " + payment_row.payment_entry + " already attached");
        } else {
            get_card_authorization(frm.doc.name, payment_row.amount).then(payment_status => {
                if (payment_status == "success") {
                    frappe.call({
                        method: "jaleel_ho.custom_selling.sales_order.create_and_submit_payment_entry",
                        args: { docname: frm.doc.name, row: locals[cdt][cdn].idx },
                        callback: function (r) {
                            if (r.message) {
                                frappe.msgprint(r.message);
                                frm.refresh();
                            }
                        },
                        freeze: true,
                        freeze_message: __("Processing...")
                    });
                }
            });
        }
    }
});

async function get_card_authorization(name, amount) {
    frappe.dom.freeze(__('Processing payment... Please wait.'));

    try {
        let response = await frappe.call({
            method: 'frappe.client.get_value',
            args: {
                doctype: 'Magnati Settings',
                fieldname: 'terminal_id'
            }
        });

        if (!response.message) {
            frappe.throw(__('No Terminal ID found in Magnati Settings'));
            return;
        }

        const terminalId = response.message.terminal_id;
        const urlencoded = new URLSearchParams();
        urlencoded.append("Amount", amount);
        urlencoded.append("TerminalId", terminalId);
        urlencoded.append("TransType", "1");
        urlencoded.append("TxnComplitionAmount", "0");
        urlencoded.append("TIPAmount", "0");
        urlencoded.append("OrgionalRcptNum", "");
        urlencoded.append("ECRRcptNum", name);
        urlencoded.append("RetRefNo", name);

        response = await fetch('http://localhost/FABECRWeb/ECRWebService.asmx/Web_VFI_GetAuth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded'
            },
            body: urlencoded,
            redirect: 'follow'
        });

        const result = await response.text();
        const parser = new DOMParser();
        const xmlDoc = parser.parseFromString(result, 'text/xml');

        const resultElement = xmlDoc.getElementsByTagName('Result')[0];
        const responseCodeElement = xmlDoc.getElementsByTagName('VFI_RespCode')[0];
        const approvalCodeElement = xmlDoc.getElementsByTagName('VFI_ApprovalCode')[0];

        if (resultElement) {
            const isSuccess = resultElement.textContent.toLowerCase() === 'true';
            const responseCode = responseCodeElement ? responseCodeElement.textContent : 'N/A';
            const approvalCode = approvalCodeElement ? approvalCodeElement.textContent : 'N/A';

            let titl, msg;

            if (isSuccess) {
                titl = 'Payment Successful';
                msg = `Response Code: ${responseCode}<br>Approval Code: ${approvalCode}<br>Amount: ${amount}<br>`;
                frappe.msgprint({
                    title: __(titl),
                    message: __(msg),
                    indicator: 'green'
                });
                make_payment_log(titl, name, msg);
                return "success";
            } else {
                titl = 'Authorization Failed';
                msg = `Response Code: ${responseCode}`;
                frappe.msgprint({
                    title: __(titl),
                    message: __(msg),
                    indicator: 'red'
                });
                make_payment_log(titl, name, msg);
                return "failed";
            }
        } else {
            let titl = 'Authorization Error';
            let msg = 'Could not process card authorization';
            frappe.msgprint({
                title: __(titl),
                message: __(msg),
                indicator: 'red'
            });
            make_payment_log(titl, name, msg);
            return "failed";
        }
    } catch (error) {
        console.error('POST request error:', error);
        let titl = 'Network Error';
        let msg = 'Failed to connect to payment gateway';

        frappe.msgprint({
            title: __(titl),
            message: __(msg),
            indicator: 'red'
        });
        make_payment_log(titl, name, msg);
        return "failed";
    } finally {
        frappe.dom.unfreeze();
    }
}

function make_payment_log(title, doc_name, msg) {
    frappe.call({
        method: "frappe.client.insert",
        args: {
            doc: {
                doctype: "Payment Log",
                title: title,
                reference_doc: doc_name,
                message: msg
            }
        },
        callback: function (response) {
            if (!response.exc) {
                frappe.msgprint(__('Payment log created successfully: ' + response.message.name));
            } else {
                frappe.msgprint(__('Error: ' + response.exc));
            }
        }
    });
}

function restrict_qty_increase_for_foc(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let new_qty = row.custom_requested_qty;
    const previous_qty = row.qty;
    if (row.is_free_item && new_qty > previous_qty) {
        frappe.model.set_value(cdt, cdn, "custom_requested_qty", previous_qty);
        frappe.throw(__('You cannot increase the quantity for free items.'));
    }
}

function check_pricing_rule(frm, cdt, cdn) {
    let row = locals[cdt][cdn];
    let item_code = row.item_code;
    let item_group = row.item_group;
    let brand = row.brand;
    let qty = row.custom_requested_qty;
    let customer = frm.doc.customer;
    let customer_group = frm.doc.customer_group;
    let site_info = frm.doc.custom_site;
    let dc = frm.doc.custom_distribution_channel_code;
    let company = frm.doc.company;
    let sales_organization_code = frm.doc.custom_sales_organization_code;
    let customer_hierarchy = frm.doc.custom_customer_hierarchy;

        frappe.call({
            method: "jaleel_ho.custom_selling.sales_order.get_foc_items",
            args: {
                row: row,
                item_code: item_code,
                qty: qty,
                customer: customer,
                customer_group: customer_group,
                site: site_info,
                item_grp: item_group,
                brnd: brand,
                dc: dc,
                company: company,
                sales_organization_code: sales_organization_code,
                customer_hierarchy :customer_hierarchy

            },
            callback: function (response) {
                if (response.message && response.message.length > 0) {
                    let dialog_content = `<p>Below are the details of the free items available based on the current item and quantity:</p>`;
                    dialog_content += `<table class="table table-bordered">
                        <thead>
                            <tr>
                                <th>Item Code</th>
                                <th>Free Item</th>
                                <th>Free Quantity</th>
                                <th>Required Quantity</th>
                                <th>Message</th>
                            </tr>
                        </thead>
                        <tbody>`;
    
                    response.message.forEach(rule => {
                        let free_qty = rule.free_qty;
                        let free_item = rule.free_item;
                        let min_qty = rule.min_qty;
                        let required_qty = min_qty - qty;
    
                        let message = required_qty > 0
                            ? `Buy ${required_qty} more to get ${free_qty} of free item (${free_item}).`
                            : `You qualify for ${free_qty} of free item (${free_item})!`;
    
                        dialog_content += `
                            <tr>
                                <td>${item_code}</td>
                                <td>${free_item}</td>
                                <td>${free_qty}</td>
                                <td>${required_qty > 0 ? required_qty : 0}</td>
                                <td>${message}</td>
                            </tr>`;
                    });
    
                    dialog_content += `</tbody></table>`;
    
                    let dialog = new frappe.ui.Dialog({
                        title: __('Free Item Details'),
                        fields: [
                            {
                                fieldtype: 'HTML',
                                fieldname: 'details',
                                options: dialog_content
                            }
                        ],
                        primary_action_label: __('Close'),
                        primary_action: function () {
                            dialog.hide();
                        }
                    });
    
                    dialog.show();
                }
            }
        });

    }


function fetch_foc_and_append_row(frm, cdt, cdn) {
    let row = frappe.get_doc(cdt, cdn);
    let item_code = row.item_code;
    let item_group = row.item_group;
    let brand = row.brand;
    let qty = row.custom_requested_qty;
    let customer = frm.doc.customer;
    let customer_group = frm.doc.customer_group;
    let site_info = frm.doc.custom_site;
    let dc = frm.doc.custom_distribution_channel_code;
    let company = frm.doc.company;
    let sales_organization_code = frm.doc.custom_sales_organization_code;
    let customer_hierarchy = frm.doc.custom_customer_hierarchy;
    let items_child = frm.doc.items;
    let pricing_details = frm.doc.custom_foc_reference;
    
        if (row.custom_requested_qty > 0) {
            frappe.call({
                method: "jaleel_ho.custom_selling.sales_order.fetch_foc_for_recursive",
                args: {
                    item_code: row.item_code,
                    qty: row.custom_requested_qty,
                    items: items_child,
                    custom_foc_reference: pricing_details,
                    row: row,
                    item_code: item_code,
                    qty: qty,
                    customer: customer,
                    customer_group: customer_group,
                    site: site_info,
                    item_grp: item_group,
                    brnd: brand,
                    dc: dc,
                    company: company,
                    sales_organization_code: sales_organization_code,
                    customer_hierarchy: customer_hierarchy
                },
                callback: function (r) {
                    if (r.message) {
                    frm.set_value("items", r.message.items);
                    frm.set_value("custom_foc_reference", r.message.custom_foc_reference);

                    frm.refresh_field("items");
                    frm.refresh_field("custom_foc_reference");
                    }
                }
            });
        }
    }
    
