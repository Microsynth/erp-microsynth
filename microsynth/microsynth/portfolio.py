import frappe
from frappe.utils.data import today, get_first_day, get_last_day, add_months
from datetime import datetime


def get_sales_volume(contact):
    if not contact:
        frappe.throw("Bitte einen Kontakt angeben")
    
    data = [] # 1st entry = first month, second = second month etc...13th entry = year
    query_date = today()
    first_day_past_year = get_first_day(query_date, d_years = -1)
    yearly_volume = 0
    last_month_date = None
    
    for month in range(12):
        start = add_months(first_day_past_year, month)
        end = get_last_day(start)
        last_month_date = end
        sql_query = """
                        SELECT SUM(`base_net_total`) AS `total`
                        FROM `tabSales Order`
                        WHERE `contact_person` = '{contact}'
                        AND `docstatus` = 1
                        AND `transaction_date` BETWEEN '{start}' AND '{end}'
                    """.format(contact=contact, start=start, end=end)
        
        monthly_volume = frappe.db.sql(sql_query, as_dict=True)[0].total or 0
        
        data.append({
            'date': "{0} - {1}".format(start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y")),
            'volume': monthly_volume
        })
        
        yearly_volume += monthly_volume
        
    data.append({
        'date': "{0} - {1}".format(first_day_past_year.strftime("%d.%m.%Y"), last_month_date.strftime("%d.%m.%Y")),
        'volume': yearly_volume
    })
    # ~ print(data)
    return data


def get_yearly_order_sum(contact_id):
    """
    Returns the total amount of all Sales Orders of the given contact_id from the current year
    and the total amount from last year.

    bench execute microsynth.microsynth.portfolio.get_yearly_order_sum --kwargs "{'contact_id': '220951'}"
    """
    if not contact_id or not frappe.db.exists("Contact", contact_id):
        frappe.throw("Please provide a valid Contact ID.")
    # get current year as int
    current_year = datetime.now().year
    yearly_order_sum = []
    for year in range(current_year, current_year-2, -1):
        data = frappe.db.sql(f"""
                        SELECT SUM(`base_net_total`) AS `total`, `currency`
                        FROM `tabSales Order`
                        WHERE `contact_person` = '{contact_id}'
                        AND `docstatus` = 1
                        AND `transaction_date` BETWEEN DATE('{year}-01-01') AND DATE('{year}-12-31')
                        GROUP BY `currency`
                    """, as_dict=True)
        if len(data) > 1:
            frappe.log_error(f"There seem to be {len(data)} different currencies on Sales Orders of Contact '{contact_id}' from {year}.", "portfolio.get_yearly_order_sum")
            yearly_order_sum.append({
                'amount': sum((entry.total or 0) for entry in data),
                'currency': 'different'
            })
        yearly_order_sum.append({
            'amount': data[0].total or 0,
            'currency': data[0].currency
        })
    return yearly_order_sum


def get_sales_qty(contact):
    if not contact:
        frappe.throw("Bitte einen Kontakt angeben")
    
    data = [] # 1st entry = first month, second = second month etc...13th entry = year
    query_date = today()
    first_day_past_year = get_first_day(query_date, d_years = -1)
    yearly_volume = 0
    last_month_date = None
    
    for month in range(12):
        start = add_months(first_day_past_year, month)
        end = get_last_day(start)
        last_month_date = end
        sql_query = """
                        SELECT COUNT(*) AS `total`
                        FROM `tabSales Order`
                        WHERE `contact_person` = '{contact}'
                        AND `docstatus` = 1
                        AND `transaction_date` BETWEEN '{start}' AND '{end}'
                    """.format(contact=contact, start=start, end=end)
        
        monthly_volume = frappe.db.sql(sql_query, as_dict=True)[0].total or 0
        
        data.append({
            'date': "{0} - {1}".format(start.strftime("%d.%m.%Y"), end.strftime("%d.%m.%Y")),
            'quantity': monthly_volume
        })
        
        yearly_volume += monthly_volume
        
    data.append({
        'date': "{0} - {1}".format(first_day_past_year.strftime("%d.%m.%Y"), last_month_date.strftime("%d.%m.%Y")),
        'quantity': yearly_volume
    })
    # ~ print(data)
    return data


def get_product_type(contact):
    if not contact:
        frappe.throw("Bitte einen Kontakt angeben")
    
    data = []
    query_date = today()
    first_day = get_first_day(query_date, d_years = -1)
    last_day_help = add_months(query_date, -1)
    last_day = get_last_day(last_day_help)
    yearly_volume = 0
    sql_query = """
                    SELECT SUM(`base_net_total`) AS `total`,`product_type`, COUNT(`name`) AS `qty`, `currency`
                    FROM `tabSales Order`
                    WHERE `contact_person` = '{contact}'
                    AND `docstatus` = 1
                    AND `transaction_date` BETWEEN '{start}' AND '{end}'
                    GROUP BY `tabSales Order`.`product_type`
                """.format(contact=contact, start=first_day, end=last_day)
                    
    volumes = frappe.db.sql(sql_query, as_dict=True)
    total_volume = 0
    total_qty = 0
    for volume in volumes:
        total_volume += volume.total
        total_qty += volume.qty
        data.append({
            'period': "{0} - {1}".format(first_day.strftime("%d.%m.%Y"), last_day.strftime("%d.%m.%Y")),
            'volume': volume.total,
            'type': volume.product_type,
            'qty': volume.qty,
            'currency': volume.currency
        })
    percent_volume = (100 / total_volume) if total_volume > 0 else 1
    percent_qty = (100 / total_qty) if total_qty > 0 else 1
    for d in data:
        d['percent_volume'] = round((d['volume'] * percent_volume), 2)
        d['percent_qty'] = round((d['qty'] * percent_qty), 2)
        
    # ~ print(data)
    return data


# ~ import frappe
# ~ from frappe.utils import getdate

# ~ def get_sales_volume(contact, from_date, to_date):
	# ~ from_date = datetime.strptime(from_date, '%Y-%m-%d')
	# ~ to_date = datetime.strptime(from_date, '%Y-%m-%d')
	# ~ filters = {
		# ~ "customer_name": customer_name,
		# ~ "docstatus": 1,
		# ~ "transaction_date": [">=", from_date],
		# ~ "transaction_date": ["<=", to_date]
	# ~ }
	# ~ sales_orders = frappe.get_all("Sales Order", filters=filters, fields=["total"])
	# ~ customer_name, from_date, to_date = get_date_year()
	# ~ sql_query = """
                    # ~ SELECT SUM(`total`) AS `total`
                    # ~ FROM `tabSales Order`
                    # ~ WHERE `customer_name` = '{customer_name}'
                    # ~ AND `docstatus` = 1
                    # ~ AND `transaction_date` BETWEEN '{from_date}' AND '{to_date}'
                # ~ """.format(customer_name=customer_name, from_date=from_date, to_date=to_date)
	
	# ~ amount = frappe.db.sql(sql_query, as_dict=True)[0].total or 0
	
	# ~ return amount
	
# ~ def get_date_year():
	# ~ customer = "CHUV"
	# ~ to_date = getdate()
	# ~ from_date = frappe.utils.add_years(to_date, -1)
	
	# ~ return customer, from_date, to_date

# ~ def get_report():
	# ~ result = get_sales_volume(get_date_year)
	
	# ~ print(result)
