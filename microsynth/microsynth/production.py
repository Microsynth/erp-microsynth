# -*- coding: utf-8 -*-
# Copyright (c) 2022, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

from datetime import datetime
from erpnext.selling.doctype.sales_order.sales_order import (
    make_delivery_note,
    close_or_unclose_sales_orders
)
import frappe
from microsynth.microsynth.labels import print_raw
from microsynth.microsynth.utils import (
    get_export_category,
    validate_sales_order,
    has_items_delivered_by_supplier
)
from microsynth.microsynth.naming_series import get_naming_series


@frappe.whitelist()
def oligo_status_changed(content=None):
    """
    Update the status of a sales order item (Canceled, Completed)

    Testing from console:
    bench execute "microsynth.microsynth.production.oligo_status_changed" --kwargs "{'content':{'oligos':[{'web_id': '84554','production_id': '4567763.2','status': 'Completed'}]}}"
    """
    # check mandatory
    if not content:
        return {'success': False, 'message': "Please provide content", 'reference': None}
    if not 'oligos' in content:
        return {'success': False, 'message': "Please provide oligos", 'reference': None}

    # go through oligos and update status
    affected_sales_orders = set()
    updated_oligos = []
    error_oligos = []
    for oligo in content['oligos']:
        if not 'web_id' in oligo:
            return {'success': False, 'message': "Oligos need to have a web_id", 'reference': None}
        if not 'status' in oligo:
            return {'success': False, 'message': "Oligos need to have a status (Open, Completed, Canceled)", 'reference': None}

        # find oligo
        oligos = frappe.db.sql("""
            SELECT
              `tabOligo`.`name`,
              `tabOligo Link`.`parent` AS `sales_order`
            FROM `tabOligo`
            LEFT JOIN `tabOligo Link` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
              `tabOligo`.`web_id` = "{web_id}"
              AND `tabOligo Link`.`parenttype` = "Sales Order"
            ORDER BY `tabOligo Link`.`creation` DESC;
        """.format(web_id=oligo['web_id']), as_dict=True)

        if len(oligos) > 0:
            if len(oligos) > 1:
                first_oligo_name = oligos[0]['name']
                for o in oligos[1:]:
                    if o['name'] != first_oligo_name:
                        frappe.log_error(f"There are {len(oligos)} Oligos with Web ID {oligo['web_id']} in the ERP. " \
                                         f"At least Oligo '{first_oligo_name}' and Oligo '{o['name']}' have the same Web ID {oligo['web_id']}. " \
                                         f"Going to update the first one.", "Oligo duplicates in production.oligo_status_changed")
            # get oligo to update the status
            oligo_doc = frappe.get_doc("Oligo", oligos[0]['name'])
            if oligo_doc.status != oligo['status']:
                oligo_doc.status = oligo['status']
                if 'production_id' in oligo:
                    oligo_doc.prod_id = oligo['production_id']
                oligo_doc.save(ignore_permissions=True)
                updated_oligos.append(oligos[0]['name'])
            # append sales order (if available and not in list)
            if oligos[0]['sales_order'] and oligos[0]['sales_order'] not in affected_sales_orders:
                affected_sales_orders.add(oligos[0]['sales_order'])
        else:
            #frappe.log_error("Oligo status update: oligo {0} not found.".format(oligo['web_id']), "Production: oligo status update error")
            error_oligos.append(oligo['web_id'])
    frappe.db.commit()
    # check and process sales order (in case all is complete)
    if len(affected_sales_orders) > 0:
        check_sales_order_completion(affected_sales_orders)
    if len(error_oligos) > 0:
        frappe.log_error(f"Oligo status update: The following oligos are not found: {error_oligos}", "Production: oligo status update error")
    return {
        'success': len(error_oligos) == 0,
        'message': 'Processed {0} oligos from {1} orders (Errors: {2}))'.format(
            len(updated_oligos), len(affected_sales_orders), ", ".join(map(str, error_oligos))
        )
    }


def get_customer_from_sales_order(sales_order):
    customer_name = frappe.get_value("Sales Order", sales_order, 'customer')
    customer = frappe.get_doc("Customer", customer_name)
    return customer


def check_sales_order_completion(sales_orders):
    """
    Check if all oligos of the provided orders are completed and generate a delivery note.

    Run
    bench execute "microsynth.microsynth.production.check_sales_order_completion" --kwargs "{'sales_orders':['SO-BAL-23000058', 'SO-BAL-23000051']}"
    """
    settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
    for sales_order in sales_orders:
        #print(f"Processing '{sales_order}' ...")

        if not validate_sales_order(sales_order):
            continue

        # get open items
        so_open_items = frappe.db.sql("""
            SELECT
                `tabOligo Link`.`parent`
            FROM `tabOligo Link`
            LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
                `tabOligo Link`.`parent` = "{sales_order}"
                AND `tabOligo Link`.`parenttype` = "Sales Order"
                AND `tabOligo`.`status` = "Open";
        """.format(sales_order=sales_order), as_dict=True)

        if len(so_open_items) == 0:
            # all items are either complete or cancelled
            if has_items_delivered_by_supplier(sales_order):
                # do not create a DN if any item has the flag delivered_by_supplier set
                continue
            ## create delivery note (leave on draft: submitted by flushbox after processing)
            dn_content = make_delivery_note(sales_order)
            dn = frappe.get_doc(dn_content)
            if not dn:
                #print(f"Delivery Note for '{sales_order}' is None.")
                continue
            if not dn.get('oligos'):
                #print(f"Delivery Note for '{sales_order}' has no Oligos.")
                continue
            company = frappe.get_value("Sales Order", sales_order, "company")
            dn.naming_series = get_naming_series("Delivery Note", company)
            # set export code
            dn.export_category = get_export_category(dn.shipping_address_name)

            # remove oligos that are canceled
            cleaned_oligos = []
            cancelled_oligo_item_qtys = {}
            for oligo in dn.oligos:
                oligo_doc = frappe.get_doc("Oligo", oligo.oligo)
                if oligo_doc.status != "Canceled":
                    cleaned_oligos.append(oligo)
                else:
                    # append items
                    for item in oligo_doc.items:
                        if item.item_code in cancelled_oligo_item_qtys:
                            cancelled_oligo_item_qtys[item.item_code] = cancelled_oligo_item_qtys[item.item_code] + item.qty
                        else:
                            cancelled_oligo_item_qtys[item.item_code] = item.qty

            dn.oligos = cleaned_oligos
            # subtract cancelled items from oligo items
            for item in dn.items:
                if item.item_code in cancelled_oligo_item_qtys:
                    item.qty -= cancelled_oligo_item_qtys[item.item_code]
            # remove items with qty == 0
            keep_items = []
            for item in dn.items:
                if item.qty > 0:
                    keep_items.append(item)

            # if all Oligos are cancelled, there are no items left or only the shipping item -> close the order
            if len(keep_items) == 0 or (len(keep_items) == 1 and keep_items[0].item_group == "Shipping"):
                print(f"No items left in {sales_order}. Cannot create a delivery note. Going to close the Sales Order.")
                close_or_unclose_sales_orders("""["{0}"]""".format(sales_order), "Closed")
                continue

            dn.items = keep_items
            # insert record
            dn.flags.ignore_missing = True
            dn.insert(ignore_permissions=True)
            frappe.db.commit()

            # create PDF for delivery note
            try:
                pdf = frappe.get_print(
                    doctype="Delivery Note",
                    name=dn.name,
                    print_format=settings.dn_print_format,
                    as_pdf=True
                )
                output = open("{0}/{1}.pdf".format(
                    settings.pdf_path,
                    dn.web_order_id), 'wb')
                # convert byte array and write to binray file
                output.write((''.join(chr(i) for i in pdf)).encode('charmap'))
                output.close()
            except Exception as err:
                frappe.log_error( "Error on pdf creation of {0}: {1}".format(dn.name, err),
                    "PDF creation failed (production API)" )
    return


@frappe.whitelist()
def get_orders_for_packaging(destination="CH"):
    """
    Get deliverable units

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = frappe.db.sql("""
        SELECT
            `tabDelivery Note`.`web_order_id` AS `web_order_id`,
            `tabDelivery Note`.`name` AS `delivery_note`,
            `tabAddress`.`country` AS `country`,
            `tabCountry`.`export_code` AS `export_code`
        FROM `tabDelivery Note`
        LEFT JOIN `tabAddress` ON `tabAddress`.`name` = `tabDelivery Note`.`shipping_address_name`
        LEFT JOIN `tabCountry` ON `tabCountry`.`name` = `tabAddress`.`country`
        WHERE `tabDelivery Note`.`docstatus` = 0
          AND `tabCountry`.`export_code` LIKE "{export_code}"
          AND `tabDelivery Note`.`product_type` = "Oligos";
    """.format(export_code=destination), as_dict=True)

    return {'success': True, 'message': 'OK', 'orders': deliveries}


@frappe.whitelist()
def count_orders_for_packaging(destination="CH"):
    """
    Get number of deliverable units

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = get_orders_for_packaging(destination)['orders']

    return {'success': True, 'message': 'OK', 'order_count': len(deliveries)}


@frappe.whitelist()
def get_next_order_for_packaging(destination="CH"):
    """
    Get next order to deliver

    Destination: CH, EU, ROW (see Country:Export Code)
    """
    deliveries = get_orders_for_packaging(destination)['orders']

    if len(deliveries) > 0:
        return {'success': True, 'message': 'OK', 'orders': [deliveries[0]] }
    else:
        return {'success': False, 'message': 'Nothing more to deliver'}


def print_at_administration(doc):
    """
    Print the given document (e.g. Delivery Note) at the administration printer
    """
    import os
    import subprocess
    from frappe.desk.form.load import get_attachments
    from microsynth.microsynth.utils import get_physical_path
    from erpnextswiss.erpnextswiss.attach_pdf import save_and_attach, create_folder

    if not hasattr(doc, 'doctype') or not hasattr(doc, 'name') or not hasattr(doc, 'title'):
        frappe.log_error(f"'{str(doc)}' has no doctype or name or title. Unable to print.", "production.print_at_administration")
        return
    doctype = printformat = doc.doctype
    name = doc.name
    frappe.local.lang = frappe.db.get_value(doctype, doc.name, "language") or 'en'
    doctype_folder = create_folder(doctype, "Home")
    title_folder = create_folder(doc.title, doctype_folder)
    filecontent = frappe.get_print(doctype, name, printformat, doc=None, as_pdf=True, no_letterhead=False)

    save_and_attach(
        content = filecontent,
        to_doctype = doctype,
        to_name = name,
        folder = title_folder,
        hashname = None,
        is_private = True)

    attachments = get_attachments(doctype, doc.name)
    fid = next((a["name"] for a in attachments if a["file_url"].endswith(".pdf")), None)
    if not fid:
        frappe.log_error(f"No PDF attachment found for {doctype} {name}", "print_at_administration")
        return
    frappe.db.commit()

    # print the pdf with cups
    path = get_physical_path(fid)
    PRINTER = frappe.get_value("Microsynth Settings", "Microsynth Settings", "invoice_printer")
    if not PRINTER:
        frappe.log_error("No invoice_printer configured in Microsynth Settings", "print_at_administration")
        return
    if not os.path.exists(path):
        frappe.log_error(f"File not found at path: {path}", "print_at_administration")
        return
    try:
        subprocess.run(["lp", path, "-d", PRINTER], check=True)
    except subprocess.CalledProcessError as e:
        frappe.log_error(f"Printing failed: {str(e)}", "print_at_administration")


@frappe.whitelist()
def oligo_delivery_packaged(delivery_note):
    """
    Mark a delivery as packaged

    bench execute "microsynth.microsynth.production.oligo_delivery_packaged" --kwargs "{'delivery_note': 'DN-BAL-25016266-1'}"
    """
    if frappe.db.exists("Delivery Note", delivery_note):
        dn = frappe.get_doc("Delivery Note", delivery_note)
        if dn.docstatus > 0:
            return {'success': False, 'message': "Delivery Note already completed"}
        try:
            dn.submit()
            frappe.db.commit()
            set_shipping_date(dn)

            # check for Pasteur Paris:
            if "Pasteur" in dn.customer_name:
                city = frappe.get_value("Address", dn.shipping_address_name, "city")
                if city and "Paris" in city:
                    print_at_administration(dn)
            return {'success': True, 'message': 'OK'}
        except Exception as err:
            return {'success': False, 'message': err}
    else:
        return {'success': False, 'message': "Delivery Note not found: {0}".format(delivery_note)}


def set_shipping_date(delivery_note):
    """
    Find Sales Order, find Tracking Code, set Shipping Date

    bench execute "microsynth.microsynth.production.set_shipping_date" --kwargs "{'delivery_note': 'DN-BAL-24057747'}"
    """
    if type(delivery_note) == str:
        delivery_note = frappe.get_doc("Delivery Note", delivery_note)

    sales_orders = set()
    for item in delivery_note.items:
        if item.against_sales_order:
            sales_orders.add(item.against_sales_order)

    if len(sales_orders) != 1:
        msg = f"Found {len(sales_orders)} Sales Orders for Delivery Note {delivery_note.name}."
        frappe.log_error(msg, "production.set_shipping_date")
        return
    [sales_order_id] = sales_orders  # tuple unpacking verifies the assumption that the set contains exactly one element (raising ValueError if it has too many or too few elements)
    tracking_codes = frappe.get_all("Tracking Code", filters={'sales_order': sales_order_id}, fields=['name', 'tracking_code', 'sales_order', 'shipping_date'])
    if len(tracking_codes) != 1:
        if len(tracking_codes) > 1:
            msg = f"Found {len(tracking_codes)} Tracking Codes for Sales Order {sales_order_id}. Going to not set the Shipping Date."
            frappe.log_error(msg, "production.set_shipping_date")
        return
    if tracking_codes[0]['shipping_date']:
        msg = f"Tracking Code '{tracking_codes[0]['tracking_code']=}' has already Shipping Date {tracking_codes[0]['shipping_date']}."
        frappe.log_error(msg, "production.set_shipping_date")
    else:
        tracking_code_doc = frappe.get_doc("Tracking Code", tracking_codes[0]['name'])
        tracking_code_doc.shipping_date = datetime.now()
        tracking_code_doc.save()


@frappe.whitelist()
def oligo_order_packaged(web_order_id):
    """
    Find Delivery Note and mark it as packaged

    bench execute "microsynth.microsynth.production.oligo_order_packaged" --kwargs "{'web_order_id': '4280235'}"
    """
    delivery_notes = frappe.db.sql("""
            SELECT
                `tabDelivery Note`.`name`
            FROM `tabDelivery Note`
            WHERE
                `tabDelivery Note`.`web_order_id` = "{web_order_id}"
            AND `tabDelivery Note`.`docstatus` = 0;
        """.format(web_order_id=web_order_id), as_dict=True)

    if len(delivery_notes) == 0:
        return {'success': False, 'message': "Could not find Delivery Note Draft with web_order_id: {0}".format(web_order_id)}
    elif len(delivery_notes) > 1:
        return {'success': False, 'message': "Multiple Delivery Note Drafts found for web_order_id: {0}".format(web_order_id)}
    else:
        packaged = oligo_delivery_packaged(delivery_notes[0].name)
        return packaged


@frappe.whitelist()
def print_delivery_label(delivery_note):
    """
    Print delivery note address label
    """
    if frappe.db.exists("Delivery Note", delivery_note):
        dn = frappe.get_doc("Delivery Note", delivery_note)
        settings = frappe.get_doc("Flushbox Settings", "Flushbox Settings")
        # render content
        label_content = frappe.render_template("microsynth/templates/labels/oligo_delivery_note_address_label.html", dn.as_dict())
        if settings.label_printer_ip and settings.label_printer_port:
            print_raw(settings.label_printer_ip, settings.label_printer_port, label_content)
        else:
            print(label_content)
            frappe.log_error( "Please define Flusbox Settings: label printer ip/port; cannot print label", "Production:address_label" )
        return {'success': True, 'message': 'OK'}
    else:
        return {'success': False, 'message': "Delivery Note not found"}


def process_internal_order(sales_order):
    from microsynth.microsynth.utils import get_tags
    print("process {0}".format(sales_order))
    sales_order = frappe.get_doc("Sales Order", sales_order)

    tags = get_tags("Sales Order", sales_order.name)

    for tag in tags:
        if "invoice" in tag.lower() or "duplicate invoice" in tag.lower():
            print("invoiced")
            return

    if sales_order.hold_invoice or sales_order.hold_order:
        print("hold")
        return

    if sales_order.status == "Closed":
        print("closed")
        return

    check_sales_order_completion( [sales_order.name] )
    oligo_order_packaged(sales_order.web_order_id)
    frappe.db.commit()
    return


def process_internal_oligos(file):
    """
    run
    bench execute microsynth.microsynth.production.process_internal_oligos --kwargs "{'file': '/mnt/erp_share/internal_oligos.txt'}"
    """
    internal_oligos = []

    with open(file) as file:
        file.readline()    # skip header line
        for line in file:
            if line.strip() != "":
                elements = line.split("\t")
                oligo = {}
                oligo['web_id'] = elements[1].strip()
                oligo['production_id'] = elements[2].split('.')[0]  # only consider root oligo ID
                oligo['status'] = elements[3].strip()
                internal_oligos.append(oligo)

    for oligo in internal_oligos:
        print("oligo {} ({})".format(oligo['production_id'], oligo['web_id']))

        # find oligo
        oligos = frappe.db.sql("""
            SELECT
              `tabOligo`.`name`,
              `tabOligo Link`.`parent` AS `sales_order`
            FROM `tabOligo`
            LEFT JOIN `tabOligo Link` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
              `tabOligo`.`web_id` = "{web_id}"
              AND `tabOligo Link`.`parenttype` = "Sales Order"
            ORDER BY `tabOligo Link`.`creation` DESC;
        """.format(web_id=oligo['web_id']), as_dict=True)

        if len(oligos) > 0:
            # update oligo
            oligo_doc = frappe.get_doc("Oligo", oligos[0]['name'])
            if oligo_doc.status != oligo['status']:
                oligo_doc.status = oligo['status']
                if 'production_id' in oligo:
                    oligo_doc.prod_id = oligo['production_id']
                oligo_doc.save(ignore_permissions=True)

            process_internal_order(oligos[0]['sales_order'])
        else:
            continue


def alternative_validate_sales_order_status(sales_order):
    """
    Checks if the customer is enabled, the sales order is submitted and does not have an invoiced tag

    run
    bench execute microsynth.microsynth.utils.validate_sales_order_status --kwargs "{'sales_order': ''}"
    """
    customer = get_customer_from_sales_order(sales_order)

    so = frappe.get_doc("Sales Order", sales_order)

    if so._user_tags and 'invoiced' in so._user_tags:
        print(f"Sales Order {so.name} has an invoiced tag, going to skip.")
        return False

    if so.docstatus != 1:
        print(f"Sales Order {so.name} is not submitted. Cannot create a Delivery Note.")
        return False

    if customer.disabled:
        print(f"Customer '{customer.name}' of Sales Order '{sales_order}' is disabled. Cannot create a delivery note.")
        return False

    if so.selling_price_list and not frappe.get_value('Price List', so.selling_price_list, 'enabled'):
        print(f"Price List '{so.selling_price_list}' on Sales Order {so.name} is disabled. Cannot create a Delivery Note.")
        return False

    if customer == '8003':
        print(f"Sales Order {so.name} has Customer 8003, going to skip.")
        return False

    return True


def create_delivery_note_for_lost_oligos(sales_orders):
    """
    run
    bench execute microsynth.microsynth.production.create_delivery_note_for_lost_oligos --kwargs "{'sales_orders':['SO-BAL-23000223']}"
    """
    from frappe.desk.tags import add_tag
    from microsynth.microsynth.taxes import find_dated_tax_template

    total = {'EUR': 0.0, 'CHF': 0.0, 'USD': 0.0, 'SEK': 0.0}
    dn_list = []
    so_list = []

    for i, sales_order in enumerate(sales_orders):
        if i % 50 == 0:
            print(f"Current total per currency: {total}")
        print(f"{i+1}/{len(sales_orders)}: Processing '{sales_order}' ...")

        if not alternative_validate_sales_order_status(sales_order):
            continue

        # get open items
        so_open_items = frappe.db.sql("""
            SELECT
                `tabOligo Link`.`parent`
            FROM `tabOligo Link`
            LEFT JOIN `tabOligo` ON `tabOligo Link`.`oligo` = `tabOligo`.`name`
            WHERE
                `tabOligo Link`.`parent` = "{sales_order}"
                AND `tabOligo Link`.`parenttype` = "Sales Order"
                AND `tabOligo`.`status` = "Open";
            """.format(sales_order=sales_order), as_dict=True)

        if len(so_open_items) == 0:
            # all items are either complete or cancelled

            ## create and submit delivery note
            try:
                so = frappe.get_doc("Sales Order", sales_order)
                dn_content = make_delivery_note(sales_order)
                dn = frappe.get_doc(dn_content)
                if not dn:
                    print(f"Delivery Note for '{sales_order}' is None.")
                    continue
                if not dn.get('oligos'):
                    print(f"Delivery Note for '{sales_order}' has no Oligos.")
                    continue
                dn.naming_series = get_naming_series("Delivery Note", so.company)
                # set export code
                dn.export_category = get_export_category(dn.shipping_address_name)

                # remove oligos that are canceled
                oligos_to_deliver = []
                cancelled_oligo_item_qtys = {}

                for oligo in dn.oligos:
                    # SQL query to test that the Oligo is not on a Delivery Note
                    oligos_on_dns = frappe.db.sql(f"""
                        SELECT `tabOligo`.`name` AS `oligo_name`,
                            `tabDelivery Note`.`name` AS `delivery_note`
                        FROM `tabDelivery Note`
                        LEFT JOIN `tabOligo Link` AS `tOL` ON `tabDelivery Note`.`name` = `tOL`.`parent`
                                                            AND `tOL`.`parenttype` = "Delivery Note"
                        LEFT JOIN `tabOligo` ON `tabOligo`.`name` = `tOL`.`oligo`
                        WHERE `tabDelivery Note`.`docstatus` < 2
                            AND `tabDelivery Note`.`status` != 'Closed'
                            AND `tabOligo`.`name` = '{oligo.oligo}'
                        """, as_dict=True)

                    oligo_doc = frappe.get_doc("Oligo", oligo.oligo)

                    # Add oligo to the DN only if it is not Canceled and not already on a Delivery Note
                    # Do not consider the items in this step.
                    if oligo_doc.status != "Canceled" and len(oligos_on_dns) == 0:
                        oligos_to_deliver.append(oligo)

                    # Collect items that will be subtracted from the Delivery Note item quantities.
                    # Do not consider for subtraction the delivered oligos from above (oligos_on_dns)
                    # since the Delivery Note contains only items that were not yet delivered.
                    # Thus the condition "len(oligos_on_dns) == 0" is not used.
                    if oligo_doc.status == "Canceled":
                        # append items
                        for item in oligo_doc.items:
                            if item.item_code in cancelled_oligo_item_qtys:
                                cancelled_oligo_item_qtys[item.item_code] = cancelled_oligo_item_qtys[item.item_code] + item.qty
                            else:
                                cancelled_oligo_item_qtys[item.item_code] = item.qty

                if len(oligos_to_deliver) == 0:
                    msg = f"It seems that all Oligos from {sales_order} are either canceled or already delivered, but not all Items (Sales Order has Status Overdue). Please create a Delivery Note with the missing Items manually or close the Sales Order."
                    print(msg)
                    #frappe.log_error(msg, 'create_delivery_note_for_lost_oligos')
                    continue

                dn.oligos = oligos_to_deliver

                # subtract cancelled items from oligo items
                for item in dn.items:
                    if item.item_code in cancelled_oligo_item_qtys:
                        item.qty -= cancelled_oligo_item_qtys[item.item_code]
                # remove items with qty == 0
                keep_items = []
                for item in dn.items:
                    if item.qty > 0:
                        keep_items.append(item)

                # if there are no items left or only the shipping item, continue
                if len(keep_items) == 0 or (len(keep_items) == 1 and keep_items[0].item_group == "Shipping"):
                    print(f"No items left in {sales_order}. Cannot create a delivery note.")
                    continue

                dn.items = keep_items

                # Check that Items on Oligos on Delivery Note match with Items on Delivery Note
                oligo_item_qty = {}
                check_manually = False
                for oligo_link in dn.oligos:
                    oligo = frappe.get_doc('Oligo', oligo_link.oligo)
                    for item in oligo.items:
                        if item.item_code in oligo_item_qty:
                            oligo_item_qty[item.item_code] += item.qty
                        else:
                            oligo_item_qty[item.item_code] = item.qty
                for item in dn.items:
                    if item.item_code not in oligo_item_qty:
                        print(f"SANITY CHECK 1: {sales_order}: Item {item.item_code} appears {item.qty} x on the new Delivery Note but 0 x on all Oligos on the new Delivery Note.")
                        check_manually = True
                        continue
                    if item.qty != oligo_item_qty[item.item_code]:
                        print(f"SANITY CHECK 2: {sales_order}: Item {item.item_code} appears {item.qty} x on the new Delivery Note but {oligo_item_qty[item.item_code]} x on all Oligos on the new Delivery Note.")
                        check_manually = True
                    oligo_item_qty[item.item_code] = -1
                for item_code, qty in oligo_item_qty.items():
                    if qty != -1:
                        print(f"SANITY CHECK 3: {sales_order}: Item {item_code} appears 0 x on the new Delivery Note but {qty} x on all Oligos on the new Delivery Note.")
                        check_manually = True
                if check_manually:
                    print(f"Won't create a Delivery Note for Sales Order {sales_order} because SANITY CHECK failed. Please process manually.")
                    continue

                # Tag the Sales Order
                add_tag(tag="processed_lost_oligos", dt="Sales Order", dn=sales_order)

                if so.status == 'Closed':
                    # re-open Sales Order
                    so.update_status('To Deliver and Bill')
                    print(f"Re-opened previously closed Sales Order {so.name}.")

                if dn.product_type == "Oligos" or dn.product_type == "Material":
                    category = "Material"
                else:
                    category = "Service"
                if dn.oligos is not None and len(dn.oligos) > 0:
                    category = "Material"

                tax_template = find_dated_tax_template(dn.company, dn.customer, dn.shipping_address_name, category, dn.posting_date)
                dn.taxes_and_charges = tax_template

                # insert record
                dn.flags.ignore_missing = True
                dn.insert(ignore_permissions=True)

                # Tag the Delivery Note
                add_tag(tag="contains_lost_oligos", dt="Delivery Note", dn=dn.name)
                dn.submit()

                print(f"{sales_order}: Created and submitted Delivery Note '{dn.name}' with a total of {dn.total} {dn.currency} for Customer '{dn.customer}' ('{dn.customer_name}').")
                total[dn.currency] += dn.total
                dn_list.append(dn.name)
                so_list.append(sales_order)
                frappe.db.commit()

            except Exception as err:
                print(f"########## Got the following error when processing Sales Order {sales_order}:\n{err}")

        else:
            print(f"{sales_order} contains at least one open Oligo.")

    print(f"Overall total per currency: {total}")
    print(f"Created Delivery Notes for the following {len(so_list)} Sales Orders: {so_list}")
    print(f"Created {len(dn_list)} Delivery Notes: {dn_list}")


def find_lost_oligos_create_dns():
    """
    Finds Sales Orders with potentially "lost" Oligos and calls the function
    create_delivery_note_for_lost_oligos to create Delivery Notes for them.

    bench execute microsynth.microsynth.production.find_lost_oligos_create_dns
    """
    orders = frappe.db.sql(f"""
        SELECT `tabSales Order`.`name`,
            `tabSales Order`.`transaction_date`,
            ROUND(`tabSales Order`.`total`, 2) AS `total`,
            `tabSales Order`.`currency`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`product_type`,
            `tabSales Order`.`company`,
            `tabSales Order`.`status`,
            `tabSales Order`.`_user_tags`
        FROM `tabSales Order`
        WHERE `tabSales Order`.`product_type` = 'Oligos'
            AND `tabSales Order`.`per_delivered` < 100
            AND `tabSales Order`.`docstatus` = 1
            AND `tabSales Order`.`transaction_date` < DATE('2024-02-10')
            AND `tabSales Order`.`customer` != '8003'
        ;""", as_dict=True)  # TODO: The following criteria seems not to work as intended: AND `tabSales Order`.`_user_tags` NOT LIKE '%invoiced%'

    orders_to_process = []
    # count number of Sales Orders for which no or multiple Delivery Notes are found based on the Web Order ID
    reduced_no_counter = no_counter = multiple_counter = 0
    # Sum up differnce of total between Sales Order and Delivery Note for each currency
    total_diff_existing = {'EUR': 0.0, 'CHF': 0.0, 'USD': 0.0, 'SEK': 0.0}
    total_diff_missing = {'EUR': 0.0, 'CHF': 0.0, 'USD': 0.0, 'SEK': 0.0}
    # Record Sales Orders without a Delivery Note
    so_without_dn = []

    for i, sales_order in enumerate(orders):
        if sales_order['_user_tags'] and 'invoiced' in sales_order['_user_tags']:
            continue
        #orders_to_process.append(sales_order['name'])
        #continue
        # Get valid Delivery Note(s) based on Web Order ID
        delivery_notes = frappe.get_all("Delivery Note", filters=[['web_order_id', '=', sales_order['web_order_id']],
                                                                  ['docstatus', '=', '1'],
                                                                  ['status', '!=', 'Closed']],
                                                         fields=['name', 'total'])
        if len(delivery_notes) == 0:
            no_counter += 1
            if not 'SO-BAL-22' in sales_order['name']:
                if sales_order['status'] != 'Closed':
                    print(f"{sales_order['name']} with status {sales_order['status']} from Customer {sales_order['customer']} ({sales_order['customer_name']}) with a total of {sales_order['total']} {sales_order['currency']}: Found no valid Delivery Note with Web Order ID '{sales_order['web_order_id']}'")
                reduced_no_counter += 1
                so_without_dn.append(sales_order['name'])
                total_diff_missing[sales_order['currency']] += float(sales_order['total'])
                #orders_to_process.append(sales_order['name'])
        elif len(delivery_notes) > 1:
            multiple_counter += 1
            print(f"{sales_order['name']}: Found more than one valid Delivery Note with Web Order ID '{sales_order['web_order_id']}': {delivery_notes}")
        else:
            # found exactly one Delivery Note based on the Web Order ID of the Sales Order
            dn_total = float(delivery_notes[0]['total'])
            so_total = float(sales_order['total'])
            diff = so_total - dn_total
            if diff > 0.1:
                total_diff_existing[sales_order['currency']] += diff
                orders_to_process.append(sales_order['name'])
            elif diff < -0.1:
                print(f"########## {sales_order['name']}: Delivery Note Total ({dn_total}) is higher than Sales Order Total ({so_total})")
        if (i+1) % 100 == 0:
            print(f"Already checked {i+1}/{len(orders)} submitted Oligo Sales Orders. Already found {len(orders_to_process)} Sales Orders to process. {total_diff_existing=}, {total_diff_missing=}, {reduced_no_counter=}, {no_counter=}, {multiple_counter=}")

    print(f"Going to process {len(orders_to_process)} Sales Orders. {total_diff_existing=}, {total_diff_missing=}, {reduced_no_counter=}, {no_counter=}, {multiple_counter=}\n{orders_to_process=}\n{so_without_dn=}")

    create_delivery_note_for_lost_oligos(orders_to_process)


@frappe.whitelist(allow_guest=True)
def get_purchasing_item_details(internal_code):
    """
    Get details of a Purchasing Item by its internal code.

    bench execute microsynth.microsynth.production.get_purchasing_item_details" --kwargs "{'internal_code': '7278'}
    """
    if not internal_code:
        return {'success': False, 'message': "Internal code is mandatory.", 'item_details': []}

    item_code = f"P00{internal_code}"

    item_details = frappe.db.sql("""
        SELECT
            `tabItem`.`name`,
            `tabItem`.`item_name`,
            `tabItem`.`item_code`,
            `tabItem`.`description`,
            %s AS `internal_code`,
            `tabItem`.`material_code`,
            `tabItem`.`shelf_life_in_days`
        FROM `tabItem`
        WHERE `tabItem`.`disabled` = 0
            AND `tabItem`.`is_purchase_item` = 1
            AND `tabItem`.`item_group` = "Purchasing"
            AND `tabItem`.`item_code` = %s
    """, (internal_code, item_code), as_dict=True)

    if not item_details:
        return {
            'success': False,
            'message': f"No enabled Purchasing Item with internal code '{internal_code}' found.",
            'item_details': []
        }

    return {
        'success': True,
        'message': 'OK',
        'item_details': item_details
    }


@frappe.whitelist(allow_guest=True)
def get_purchasing_items_with_internal_code():
    """
    Get a list of all enabled Purchasing Items with an internal code (item_code starting with P00).

    bench execute microsynth.microsynth.production.get_purchasing_items_with_internal_code
    """
    items = frappe.db.sql("""
        SELECT
            `tabItem`.`name`,
            `tabItem`.`item_name`,
            `tabItem`.`item_code`,
            RIGHT(`tabItem`.`item_code`, 4) AS `internal_code`,
            `tabItem`.`description`,
            `tabItem`.`material_code`,
            `tabItem`.`shelf_life_in_days`
        FROM `tabItem`
        WHERE `tabItem`.`disabled` = 0
            AND `tabItem`.`is_purchase_item` = 1
            AND `tabItem`.`item_group` = "Purchasing"
            AND `tabItem`.`item_code` LIKE "P00%"
        ORDER BY `tabItem`.`internal_code` ASC;
    """, as_dict=True)

    return {
        'success': True,
        'message': 'OK',
        'items': items
    }
