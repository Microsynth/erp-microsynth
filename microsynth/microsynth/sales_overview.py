import frappe
from frappe.utils.data import today, get_first_day, get_last_day, add_months

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
                        SELECT SUM(`total`) AS `total`
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
