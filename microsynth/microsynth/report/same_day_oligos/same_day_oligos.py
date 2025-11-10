# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from datetime import datetime


def get_columns():
    return [
        {"label": _("Sales Order"), "fieldname": "name", "fieldtype": "Link", "options": "Sales Order", "width": 125},
        {"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 120},
        {"label": _("Web ID"), "fieldname": "web_order_id", "fieldtype": "Data", "width": 70},
        {"label": _("Customer"), "fieldname": "customer", "fieldtype": "Link", "options": "Customer", "width": 80},
        {"label": _("Customer name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 250},
        {"label": _("Order created"), "fieldname": "creation", "fieldtype": "Date", "width": 130},
        {"label": _("Label printed on"), "fieldname": "label_printed_on", "fieldtype": "Date", "width": 130},
        {"label": _("Same Day fulfilled"), "fieldname": "fulfilled", "fieldtype": "Check", "width": 120}
    ]


def get_holidays():
    """
    Returns a list of public holidays in Balgach from 01.01.2023 till today.

    bench execute microsynth.microsynth.report.same_day_oligos.same_day_oligos.get_holidays
    """
    from erpnextswiss.erpnextswiss.calendar import parse_holidays
    holidays_balgach = []
    parsed_holidays = []
    for y in range(2023, int(datetime.now().year)+1):
        parsed_holidays += parse_holidays("1903", str(y))  # 1903 is the geocode of Balgach: https://feiertagskalender.ch/index.php?geo=1903
        holidays_balgach.append(datetime(y, 11, 1).strftime('%d.%m.%Y'))  # unclear why it is missing
    for parsed_holiday in parsed_holidays:
        holidays_balgach.append(parsed_holiday['date'])
    return holidays_balgach


def is_workday_before_10am(date_time, holidays):
    """
    Returns true if the given date_time is a workday before 10 am (Monday to Friday and no holiday), otherwise false.
    """
    # https://docs.python.org/3/library/datetime.html#datetime.date.weekday
    if date_time.weekday() < 5 and date_time.strftime('%d.%m.%Y') not in holidays:
        if date_time.hour < 10:  # before 10 am
            return True
    return False


def get_data(filters=None):
    """
    bench execute microsynth.microsynth.report.same_day_oligos.same_day_oligos.get_data --kwargs "{'filters': {'from_date': '2024-01-01', 'to_date': '2024-02-29'}}"
    """
    filters = frappe._dict(filters or {})
    holidays = get_holidays()

    # Build base SQL conditions and parameter list
    conditions = [
        "`tabSales Order`.`docstatus` = 1",
        "`tabSales Order`.`status` NOT IN ('Draft', 'Cancelled', 'Closed')",
        "`tabSales Order`.`product_type` = 'Oligos'",
        "`tabSales Order`.`customer` != '8003'",
        "`tabSales Order`.`transaction_date` BETWEEN %(from_date)s AND %(to_date)s"
    ]
    params = {
        "from_date": filters.get("from_date"),
        "to_date": filters.get("to_date"),
    }

    if filters.get("customer"):
        conditions.append("`tabSales Order`.`customer` = %(customer)s")
        params["customer"] = filters.get("customer")

    if filters.get("customer_name"):
        conditions.append("`tabSales Order`.`customer_name` LIKE %(customer_name)s")
        params["customer_name"] = f"%{filters.get('customer_name')}%"

    base_condition_sql = " AND ".join(conditions)

    # Base SQL: pull only the Sales Orders that could possibly qualify
    sql_query = f"""
        SELECT
            `tabSales Order`.`name`,
            `tabSales Order`.`status`,
            `tabSales Order`.`web_order_id`,
            `tabSales Order`.`customer`,
            `tabSales Order`.`customer_name`,
            `tabSales Order`.`creation`,
            `tabSales Order`.`transaction_date`,
            `tabSales Order`.`label_printed_on`,
            SUM(
                CASE WHEN `tabSales Order Item`.`item_code` IN ('0010', '0050', '0100', '1100', '1101', '1102')
                THEN 1 ELSE 0 END
            ) AS `included`,
            SUM(
                CASE WHEN `tabSales Order Item`.`item_code` NOT IN ('0010', '0050', '0100', '1100', '1101', '1102')
                THEN 1 ELSE 0 END
            ) AS `notincluded`
        FROM `tabSales Order`
        LEFT JOIN `tabSales Order Item`
            ON `tabSales Order Item`.`parent` = `tabSales Order`.`name`
        WHERE {base_condition_sql}
        GROUP BY `tabSales Order`.`name`
        HAVING `included` > 0 AND `notincluded` = 0
        ORDER BY `tabSales Order`.`transaction_date`
    """
    query_results = frappe.db.sql(sql_query, values=params, as_dict=True)
    if not query_results:
        return []

    # Bulk fetch relevant Sales Orders
    so_names = [r["name"] for r in query_results]
    sales_orders = {
        so.name: so for so in frappe.get_all(
            "Sales Order",
            filters={"name": ["in", so_names]},
            fields=["name", "creation", "transaction_date", "label_printed_on", "web_order_id"]
        )
    }
    # Bulk fetch all linked Oligos
    oligo_links = frappe.get_all(
        "Oligo Link",
        filters={"parent": ["in", so_names]},
        fields=["parent", "oligo"]
    )
    oligo_names = [o.oligo for o in oligo_links]
    oligos_by_so = {}
    for link in oligo_links:
        oligos_by_so.setdefault(link.parent, []).append(link.oligo)

    # Bulk fetch Oligos and their items
    oligos = {
        o.name: o for o in frappe.get_all(
            "Oligo",
            filters={"name": ["in", oligo_names]},
            fields=["name", "sequence"]
        )
    }
    oligo_items = frappe.get_all(
        "Oligo Item",
        filters={"parent": ["in", oligo_names]},
        fields=["parent", "qty"]
    )
    items_by_oligo = {}
    for item in oligo_items:
        items_by_oligo.setdefault(item.parent, []).append(item)

    same_day_orders = []
    should_be_same_day = is_same_day = 0

    for r in query_results:
        so = sales_orders[r["name"]]
        oligo_names_for_so = oligos_by_so.get(so.name, [])
        # the same day criteria only applies to Sales Orders with less than 20 Oligos
        if len(oligo_names_for_so) >= 20:
            continue

        oligo_too_complicated = False
        for oligo_name in oligo_names_for_so:
            oligo = oligos.get(oligo_name)
            oligo_item_list = items_by_oligo.get(oligo_name, [])
            # exclude Oligos with modifications (more than one item) and Oligos without any items
            if len(oligo_item_list) != 1:
                if len(oligo_item_list) == 0:
                    #print(f"WARNING: {len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to take sequence length instead")
                    if not oligo.sequence or len(oligo.sequence) > 25:  # check if oligo is longer than 25 nt
                        #print(f"Oligo {oligo.name} from Sales Order {sales_order.name} has no items and no sequence. Going to skip this Sales Order.")
                        oligo_too_complicated = True
                        break
                else:
                    oligo_too_complicated = True
                    break
            else:
                #print(f"{len(oligo.items)=} for {sales_order.name}, Web Order ID {sales_order.web_order_id}")
                if oligo_item_list[0].qty > 25:  # check if oligo is longer than 25 nt
                    oligo_too_complicated = True
                    break

        if oligo_too_complicated:
            continue

        creation_date = str(so.creation).split(" ")[0]
        if creation_date != str(so.transaction_date):
            continue

        if not is_workday_before_10am(so.creation, holidays):
            continue

        if not so.label_printed_on:
            #print(f"There is no Label printed on date on {sales_order.name}, Web Order ID {sales_order.web_order_id}. Going to skip this Sales Order.")
            continue

        should_be_same_day += 1
        same_day_fulfilled = (
            so.creation.day == so.label_printed_on.day
            and so.label_printed_on.hour < 18
        )
        if same_day_fulfilled:
            is_same_day += 1
            r["fulfilled"] = "1"

        same_day_orders.append(r)

    # Sort results by Sales Order creation date ascending (before adding summary)
    same_day_orders.sort(key=lambda r: sales_orders[r["name"]].creation if "name" in r else datetime.max)

    if should_be_same_day > 0:  # avoid dividing by zero
        pct = (is_same_day / should_be_same_day) * 100
        same_day_orders.append({
            "web_order_id": "Summary",
            "customer_name": f"{is_same_day}/{should_be_same_day} fulfilled ({pct:.2f} %)"
        })

    return same_day_orders


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    return columns, data
