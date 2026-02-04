import frappe

def execute():
    print("Check and extend Webshop Service InvoiceByDefaultCompany...")

    frappe.reload_doc("Microsynth", "doctype", "Webshop Service")

    if not frappe.db.exists("Webshop Service", "InvoiceByDefaultCompany"):
        new_service = frappe.get_doc({
            'doctype': "Webshop Service",
            'service_name': "InvoiceByDefaultCompany"
        })
        new_service.insert()

        frappe.db.commit()

    return
