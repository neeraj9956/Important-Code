import frappe
from erpnext.stock.doctype.pick_list.pick_list import PickList

class CustomPickList(PickList):
    def before_save(self):
        self.update_status()

    def update_status(self, status=None, update_modified=True):
        if not status:
            if self.docstatus == 0:
                status = "Available"
            elif self.docstatus == 1:
                if target_document_exists(self.name, self.purpose):
                    status = "Completed"
                else:
                    status = "Open"
            elif self.docstatus == 2:
                status = "Cancelled"

        if status:
            self.db_set("status", status, update_modified=update_modified)

@frappe.whitelist()
def target_document_exists(pick_list_name, purpose):
    if purpose == "Delivery":
        return frappe.db.exists("Delivery Note", {"pick_list": pick_list_name, "docstatus": 1})

    return stock_entry_exists(pick_list_name)

def stock_entry_exists(pick_list_name):
    return frappe.db.exists("Stock Entry", {"pick_list": pick_list_name})
