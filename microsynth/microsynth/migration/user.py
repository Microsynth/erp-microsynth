import csv

import frappe


def import_test_users(filename):
	"""
	Create or update test users from a semicolon-delimited UTF-8 CSV.

	Run only on a test site: existing test users' login passwords are overwritten.
	Existing roles are preserved, and process owners and signatures are reused.
	User Settings receive missing process/company assignments when both are set.
	Blank or NA validation passwords leave existing signatures unchanged.
	Passwords are preserved verbatim; other values are stripped of whitespace.
	No commit is issued; the caller controls the transaction.

	bench execute microsynth.microsynth.migration.user.import_test_users --kwargs '{"filename": "/mnt/erp_share/Migration/Test_User/261023_Users_ReVal_QMModules_v2025.csv"}'
	"""
	required_headers = {
		"Role", "QM Process", "Company", "Is Process Owner", "Email",
		"Username / Visa", "First name", "Login Password", "Validation Password"
	}
	counters = {"created": 0, "updated": 0, "process_owners_created": 0,
				"signatures_created": 0, "signatures_updated": 0,
				"user_settings_created": 0}

	with open(filename, "r", encoding="utf-8-sig", newline="") as csv_file:
		reader = csv.DictReader(csv_file, delimiter=";")
		headers = [header.strip() for header in (reader.fieldnames or [])]
		missing_headers = required_headers - set(headers)
		if missing_headers:
			raise ValueError("Missing CSV headers: {0}".format(
				", ".join(sorted(missing_headers))))
		if len(headers) != len(set(headers)):
			raise ValueError("CSV contains duplicate headers.")
		reader.fieldnames = headers

		for row_number, row in enumerate(reader, start=2):
			if None in row or any(value is None for value in row.values()):
				raise ValueError("Row {0}: incorrect number of columns.".format(row_number))
			if not any(value.strip() for value in row.values()):
				continue

			email = row["Email"].strip().lower()
			username = row["Username / Visa"].strip()
			first_name = row["First name"].strip()
			login_password = row["Login Password"]
			validation_password = row["Validation Password"]
			roles = [role.strip() for role in row["Role"].split(",") if role.strip()]
			process_owner = row["Is Process Owner"].strip().lower()
			qm_process = row["QM Process"].strip()
			company = row["Company"].strip()

			if not email or not username or not first_name or not roles or not login_password.strip():
				raise ValueError("Row {0}: missing user details, roles or login password.".format(row_number))
			if process_owner not in ("yes", "no"):
				raise ValueError("Row {0}: Is Process Owner must be yes or no.".format(row_number))
			if process_owner == "yes" and (qm_process.upper() in ("", "NA") or company.upper() in ("", "NA")):
				raise ValueError("Row {0}: process owners require QM Process and Company.".format(row_number))

			user_name = frappe.db.exists("User", email)
			user = frappe.get_doc("User", user_name) if user_name else frappe.new_doc("User")
			user.update({
				"email": email,
				"username": username,
				"first_name": first_name,
				"enabled": 1,
				"user_type": "System User",
				"send_welcome_email": 0,
				"new_password": login_password
			})
			user.flags.no_welcome_mail = True
			existing_roles = {entry.role for entry in user.get("roles", [])}
			for role in roles:
				if role not in existing_roles:
					user.append("roles", {"role": role})
					existing_roles.add(role)
			user.save(ignore_permissions=True)
			counters["updated" if user_name else "created"] += 1

			if qm_process.upper() not in ("", "NA") and company.upper() not in ("", "NA"):
				settings_name = frappe.db.exists("User Settings", {"user": user.name})
				settings = (
					frappe.get_doc("User Settings", settings_name)
					if settings_name else frappe.new_doc("User Settings")
				)
				settings.user = user.name
				if not any(
					assignment.qm_process == qm_process and assignment.company == company
					for assignment in settings.get("qm_process_assignments", [])
				):
					settings.append("qm_process_assignments", {
						"qm_process": qm_process,
						"company": company
					})
					settings.save(ignore_permissions=True)
					if not settings_name:
						counters["user_settings_created"] += 1

			if process_owner == "yes":
				owner_values = {
					"qm_process": qm_process,
					"company": company,
					"process_owner": user.name
				}
				if not frappe.db.exists("QM Process Owner", owner_values):
					owner = frappe.new_doc("QM Process Owner")
					owner.update(owner_values)
					owner.insert(ignore_permissions=True)
					counters["process_owners_created"] += 1

			if validation_password.strip().upper() not in ("", "NA"):
				signature_name = frappe.db.exists("Signature", {"user": user.name})
				signature = (
					frappe.get_doc("Signature", signature_name)
					if signature_name else frappe.new_doc("Signature")
				)
				signature.update({
					"user": user.name,
					"full_name": user.full_name,
					"approval_password": validation_password
				})
				signature.save(ignore_permissions=True)
				counters["signatures_updated" if signature_name else "signatures_created"] += 1

	return counters
