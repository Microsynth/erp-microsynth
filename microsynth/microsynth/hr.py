import frappe
from frappe.utils import cint

naming_patterns = {
    'Job Opening': {
        'prefix': "JO-",
        'length': 5
    },
    'Job Applicant': {
        'prefix': "JA-",
        'length': 6
    }
}


def get_next_number(self):
    if self.doctype not in ["Job Opening", "Job Applicant"]:
        frappe.throw("Custom autoname is not implemented for this doctype.", "Not implemented")

    last_name = frappe.db.sql("""
        SELECT `name`
        FROM `tab{dt}`
        WHERE `name` LIKE "{prefix}%"
        ORDER BY `name` DESC
        LIMIT 1;""".format(
        dt=self.doctype,
        prefix=naming_patterns[self.doctype]['prefix']),
        as_dict=True)

    if len(last_name) == 0:
        next_number = 1
    else:
        prefix_length = len(naming_patterns[self.doctype]['prefix'])
        last_number = cint((last_name[0]['name'])[prefix_length:])
        next_number = last_number + 1

    next_number_string = get_fixed_length_string(next_number, naming_patterns[self.doctype]['length'])

    return "{prefix}{n}".format(prefix=naming_patterns[self.doctype]['prefix'], n=next_number_string)


def get_fixed_length_string(n, length):
    next_number_string = "{0}{1}".format(
        (length * "0"), n)[((-1)*length):]
    # prevent duplicates on naming series overload
    if n > cint(next_number_string):
        next_number_string = "{0}".format(n)
    return next_number_string


def hr_autoname(self, method):
    if self.doctype not in ["Job Opening", "Job Applicant"]:
        frappe.throw("Custom autoname is not implemented for this doctype.", "Not implemented")

    self.name = get_next_number(self)
    return
