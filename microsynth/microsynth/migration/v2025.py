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

def configure_system_settings():
    """
    Configure system settings for the 2025 migration.

    run
    bench execute microsynth.microsynth.migration.v2025.configure_system_settings
    """
    # To see the field names in the DEV system (in Developer Mode), you can use: [Alt] and hover over the fields.
    # Click it, and the field name will be saved in the clipboard.

    print("Configuring system settings...")
    settings = frappe.get_doc("System Settings")

    settings.enable_onboarding = False
    settings.rounding_method = "Commercial Rounding"
    settings.date_format = "dd.mm.yyyy"
    settings.time_format = "HH:mm:ss"
    settings.backup_limit = 4
    settings.ignore_party_address_validation = True

    settings.save()


def migrate2025():
    """
    Perform the 2025 migration tasks.

    run
    bench execute microsynth.microsynth.migration.v2025.migrate2025
    """
    hide_standard_workspaces()
    configure_system_settings()
