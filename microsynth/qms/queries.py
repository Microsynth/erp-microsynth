import frappe


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def system_user_query(doctype, txt, searchfield, start, page_len, filters):
    filters = filters or {}
    user_filters = {
        "enabled": 1,
        "user_type": "System User",
    }
    if filters.get("exclude_user"):
        user_filters["name"] = ["!=", filters["exclude_user"]]

    return frappe.get_list(
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