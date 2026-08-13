import frappe

def assign_role_to_workspace(role, workspace):
    """
    run
    bench execute microsynth.microsynth.migration.v2025.assign_role_to_workspace --args "['System Manager', 'Home']"
    """
    workspace = frappe.get_doc("Workspace", workspace)
    has_role = False
    for r in workspace.roles:
        if r.role == role:
            has_role = True
            break

    if not has_role:
        print(f"Workspace '{workspace.name}': Assign role '{role}'")
        workspace.append("roles", {"role": role})
        workspace.save()
    else:
        print(f"Workspace '{workspace.name}': Role '{role}' already assigned")

    return


def hide_standard_workspaces():
    """
    Hide standard workspaces from users.

    run
    bench execute microsynth.microsynth.migration.v2025.hide_standard_workspaces
    """
    standard_workspaces = frappe.get_all("Workspace", filters=[
        ['module', '!=', 'Microsynth'],
        ['name', 'not in', ['ERPNext Integrations']]
    ],
    order_by="name asc",
    pluck="name")

    for workspace in standard_workspaces:
        assign_role_to_workspace("System Manager", workspace)

    frappe.db.commit()      # unclear why this is needed
