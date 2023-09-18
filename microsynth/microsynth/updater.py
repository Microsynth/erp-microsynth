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


def disable_notifications():
    """
    Set Notification.enabled = 0 for all notifications except four old ones missing channel field.
    """
    print("Disabling notifications...")
    notifications = frappe.get_all("Notification", 
        fields=['name', 'enabled']
    )
    for notification in notifications:
        if notification['name'] not in ['Retention Bonus', 'Notification for new fiscal year', 'Training Scheduled', 'Training Feedback']:
            # print(f"Processing notification {notification['name']} ...")
            doc = frappe.get_doc("Notification", notification['name'])
            doc.enabled = 0
            doc.save()
            # print(f"Successfully processed notification {notification['name']} ...")
    frappe.db.commit()


def disable_email_accounts():
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


def disable_hot_config_in_dev():
    """
    run
    bench execute "microsynth.microsynth.updater.disable_hot_config_in_dev"

    or 
    bench migrate
    """

    # check if this is a test or develop instance
    if "erp.microsynth.local" not in (frappe.conf.host_name or ""):
        print("This is a test/develop system: disabling productive values")
        
        disable_email_accounts()

        disable_notifications()

        print("Deactivating hot export path...")
        config = frappe.get_doc("Microsynth Settings", "Microsynth Settings")
        config.pdf_export_path = (config.pdf_export_path or "").replace("/erp_share/", "/erp_share_test/")
        config.ariba_cxml_export_path = (config.ariba_cxml_export_path or "").replace("/erp_share/", "/erp_share_test/")
        config.gep_cxml_export_path = (config.gep_cxml_export_path or "").replace("/erp_share/", "/erp_share_test/")
        config.paynet_export_path = (config.paynet_export_path or "").replace("/erp_share/", "/erp_share_test/")
        config.carlo_erba_export_path = (config.carlo_erba_export_path or "").replace("/erp_share/", "/erp_share_test/")
        config.save()

        seq_config = frappe.get_doc("Sequencing Settings", "Sequencing Settings")
        seq_config.label_export_path = (seq_config.label_export_path or "").replace("/erp_share/", "/erp_share_test/")
        seq_config.save()

        print("Set test webshop...")
        config.url = (config.url or "").replace("srvweb.", "srvweb-test.")
        config.save()

        print("Set Slims test server...")
        slims_config = frappe.get_doc("SLIMS Settings", "SLIMS Settings")
        slims_config.endpoint = (slims_config.endpoint or "").replace(".63",".64")
        slims_config.save()

    return
