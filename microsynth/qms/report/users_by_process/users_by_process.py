# Copyright (c) 2024, Microsynth, libracore and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _


def get_columns(filters):
    return [
        {"label": _("User"), "fieldname": "user_name", "fieldtype": "Link", "options": "User Settings", "width": 250}
    ]


def get_data(filters):
    conditions = ""
    if filters:
        if filters.get('chapter'):
            conditions += f"AND (`tabQM User Process Assignment`.`chapter` = '{filters.get('chapter')}' OR `tabQM User Process Assignment`.`all_chapters` = 1)"
        if filters.get('company'):
            conditions += f"AND `tabQM User Process Assignment`.`company` = '{filters.get('company')}'"

        query = f"""
            SELECT DISTINCT 
                `tabUser Settings`.`name`,
                `tabUser Settings`.`name` as `user_name`,
                `tabQM User Process Assignment`.`company`
            FROM `tabUser Settings`
            LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
            WHERE `tabQM User Process Assignment`.`process_number` = '{filters.get('process_number')}'
                AND `tabQM User Process Assignment`.`subprocess_number` = '{filters.get('subprocess_number')}'
                {conditions}
            """
        return frappe.db.sql(query, as_dict=True)
    else:
        return None


def execute(filters=None):
    columns, data = get_columns(filters), get_data(filters)
    return columns, data


def get_sql_list(list):
    if list:
        return (','.join('"{0}"'.format(e) for e in list))
    else:
        return '""'


@frappe.whitelist()
def get_users(qm_processes, companies=None):
    if not qm_processes and not companies:
        return None

    companies_list = frappe.parse_json(companies)
    if companies and len(companies_list) > 0 and companies_list[0]:
        company_condition = f"`tabQM User Process Assignment`.`company` IN ({get_sql_list(companies_list)})"
    else:
        company_condition = "TRUE"

    qm_processes_list = frappe.parse_json(qm_processes)
    if qm_processes and len(qm_processes_list) > 0:
        qm_process_conditions = "AND (FALSE "
        for qm_process in qm_processes_list:
            qm_process_doc = frappe.get_doc("QM Process", qm_process)
            qm_process_conditions += f" OR (`tabQM User Process Assignment`.`process_number` = '{qm_process_doc.process_number}' AND `tabQM User Process Assignment`.`subprocess_number` = '{qm_process_doc.subprocess_number}'"
            if qm_process_doc.chapter:
                qm_process_conditions += f" AND (`tabQM User Process Assignment`.`chapter` = '{qm_process_doc.chapter}' OR `tabQM User Process Assignment`.`all_chapters` = 1))"
            else:
                qm_process_conditions += ")"
        qm_process_conditions += ")"
    else:
        qm_process_conditions = ""

    query = f"""
        SELECT DISTINCT
            `tabUser Settings`.`name`,
            `tabUser Settings`.`name` as `user_name`
        FROM `tabUser Settings`
        LEFT JOIN `tabQM User Process Assignment` ON `tabQM User Process Assignment`.`parent` = `tabUser Settings`.`name`
        WHERE {company_condition}
            {qm_process_conditions}
        """
    # frappe.log_error(f"{query=}")
    return frappe.db.sql(query, as_dict=True)


def check_and_add_3_37(qm_user_process_assignments):
    """
    Only for Microsynth AG (Balgach):
    All employees from 3.3 to 3.7 belong also to 3.37 (all chapters).
    All employees from 3.37 with chapter 37 belong also to 3.37 (all chapters).
    """
    for process_assignment in qm_user_process_assignments:
        if process_assignment['process_number'] == '3' \
            and process_assignment['subprocess_number'] in ['3', '4', '5', '6', '7', '37'] \
            and process_assignment['company'] == 'Microsynth AG':
            # add a QM User Process Assignment for 3.37 (all chapters)
            qm_user_process_assignments.append({
                'qm_process': "3.37 Genetic Analysis",
                'process_number': 3,
                'subprocess_number': 37,
                'all_chapters': 1,
                'company': 'Microsynth AG'
            })
            return


def import_process_assignments(file_path, expected_line_length=7):
    """
    bench execute microsynth.qms.report.users_by_process.users_by_process.import_process_assignments --kwargs "{'file_path': '/mnt/erp_share/JPe/240807_user_process_assignments.csv'}"
    """
    import csv
    imported_counter = line_counter = 0
    previous_email = ''
    already_inserted_emails = set()  # necessary, since there could be errors and previous_email won't be set
    qm_user_process_assignments = []
    company_mapping = {
        'Balgach': 'Microsynth AG',
        'Göttingen': 'Microsynth Seqlab GmbH',
        'Lyon': 'Microsynth France SAS',
        'Wien': 'Microsynth Austria GmbH'
    }
    with open(file_path) as file:
        print(f"Parsing Process Assignments from '{file_path}' ...")
        csv_reader = csv.reader(file, delimiter=";")
        next(csv_reader)  # skip header
        for line in csv_reader:
            line_counter += 1
            if len(line) != expected_line_length:
                print(f"Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            email = line[1].strip()  # remove leading and trailing whitespaces
            process = line[2].strip()
            subprocess = line[3].strip()
            chapter = line[4].strip()
            all_chapters = line[5].strip()
            company_city = line[6].strip()
            if not frappe.db.exists("User", email):
                print(f"User {email} is not yet in the ERP. Going to continue.")
                continue
            if not (email and process and subprocess and (chapter or all_chapters) and company_city):
                print(f"Please provide at least Email, Process, Subprocess, (Chapter or All Chapters) and Company: {line}. Going to continue.")
                continue
            if (chapter and all_chapters) or (all_chapters and all_chapters != '1'):
                print(f"Please provide either a Chapter or a 1 in the column All Chapters, but got {chapter=} and {all_chapters=}. Going to continue.")
                continue
            company = company_mapping[company_city]
            if email != previous_email and previous_email != '' and previous_email not in already_inserted_emails:  # new email
                check_and_add_3_37(qm_user_process_assignments)
                # create a new User Settings entry for the previous email
                user_settings = frappe.get_doc({
                    'doctype': 'User Settings',
                    'user': previous_email,
                    'qm_process_assignments': qm_user_process_assignments
                })
                user_settings.insert()
                already_inserted_emails.add(previous_email)
                # reset the list of QM User Process Assignments
                qm_user_process_assignments = []
            # Fetch the QM Process
            if chapter:
                qm_processes = frappe.get_all("QM Process", filters=[
                    ['process_number', '=', process],
                    ['subprocess_number', '=', subprocess],
                    ['chapter', '=', chapter]],
                    fields=['name'])
            else:
                qm_processes = frappe.get_all("QM Process", filters=[
                    ['process_number', '=', process],
                    ['subprocess_number', '=', subprocess],
                    ['all_chapters', '=', 1]],
                    fields=['name'])
            if len(qm_processes) != 1:
                print(f"Found {len(qm_processes)} QM Processes: {qm_processes}: {line}. Going to continue.")
                continue
            # Add the current values to the list of QM User Process Assignments
            qm_user_process_assignments.append({
                'qm_process': qm_processes[0]['name'],
                'process_number': process,
                'subprocess_number': subprocess,
                'all_chapters': all_chapters,
                'chapter': chapter,
                'company': company
            })
            previous_email = email
            imported_counter += 1
        if previous_email and len(qm_user_process_assignments) > 0 and previous_email not in already_inserted_emails:
            check_and_add_3_37(qm_user_process_assignments)
            # create a new User Settings entry for the last email
            user_settings = frappe.get_doc({
                'doctype': 'User Settings',
                'user': previous_email,
                'qm_process_assignments': qm_user_process_assignments
            })
            user_settings.insert()
            imported_counter += 1
    print(f"Successfully imported {imported_counter}/{line_counter} User Process Assignments ({round((imported_counter/line_counter)*100, 2)} %).")
