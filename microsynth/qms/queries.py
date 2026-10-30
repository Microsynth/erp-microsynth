import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def system_user_query(doctype, txt, searchfield, start, page_len, filters):
    filters = filters or {}
    employee_role_users = frappe.get_all(
        "Has Role",
        filters={"role": "Employee"},
        pluck="parent",
    )
    if filters.get("exclude_user"):
        employee_role_users = [
            user_id for user_id in employee_role_users
            if user_id != filters["exclude_user"]
        ]
    if not employee_role_users:
        return []

    user_filters = {
        "enabled": 1,
        "user_type": "System User",
        "name": ["in", employee_role_users],
    }
    return frappe.get_all(
        "User",
        filters=user_filters,
        or_filters={
            "name": ["like", f"%{txt}%"],
            "full_name": ["like", f"%{txt}%"],
        },
        fields=["name", "full_name"],
        order_by="name asc",
        limit_start=start,
        limit_page_length=page_len,
        as_list=True,
    )