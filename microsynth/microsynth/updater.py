# -*- coding: utf-8 -*-
# Copyright (c) 2023, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt

import frappe
from frappe import _

def cleanup_languages():
    # this function will remove languages after migrate
    print("Removing unnecessary languages...")
    lang = "'it', 'de', 'en-US', 'en', 'fr', 'es'"
    sql_query = """DELETE FROM `tabLanguage` WHERE `language_code` NOT IN ({lang});""".format(lang=lang)
    frappe.db.sql(sql_query, as_dict=1)
    return

def disable_hot_config_in_dev():
    # check if this is a test or develop instance
    if "erp.microsynth.local" not in frappe.conf.host_name:
        print("This is a test/develop system: disabling productive values")
        
        print("Disabling email accounts...")
        email_accounts = frappe.get_all("Email Account", 
            fields=['name', 'enable_incoming', 'enable_outgoing']
        )
        for account in email_accounts:
            doc = frappe.get_doc("Email Account", account['name'])
            doc.enable_incoming = 0
            doc.enable_outgoing = 0
            doc.save()
        frappe.db.commit()
        
        print("Deactivating hot export path...")
        config = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
        config.pdf_export_path = (config.pdf_export_path or "").replace("erp_share", "erp_share_test")
        config.save()
        
    return
