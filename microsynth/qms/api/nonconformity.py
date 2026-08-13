import frappe
from frappe.utils import get_url_to_form

@frappe.whitelist()
def fetch_nonconformities(nonconformity_ids):
    """
    bench execute microsynth.qms.api.nonconformity.fetch_nonconformities --kwargs "{'nonconformity_ids': ['NC-240011', 'NC-240002']}"
    """
    # for nc in nonconformity_ids:
    #     if not frappe.db.exists("QM Nonconformity", nc):
    #         return {'success': False, 'message': f"At least QM Nonconformity '{nc}' does not exist.", 'nonconformities': None}

    nonconformities = frappe.get_all("QM Nonconformity", filters=[['name', 'IN', nonconformity_ids]], fields=['name', 'title', 'nc_type', 'date', 'description'])

    for n in nonconformities:
        n['url'] = get_url_to_form("QM Nonconformity", n['name'])

    return {'success': True, 'message': 'OK', 'nonconformities': nonconformities}
