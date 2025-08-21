# -*- coding: utf-8 -*-
# Copyright (c) 2025, Microsynth, libracore and contributors and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document
import csv


class QMDevice(Document):
    pass


def convert_price_fields(price_chf, price_eur, price_usd):
    """
    Takes three price strings (CHF, EUR, USD), validates and converts one into (price, currency).

    Returns:
        tuple (currency: str, price: float) if valid
        (None, None) if invalid with printed warning
    """
    prices = {}

    for currency, value in [('CHF', price_chf), ('EUR', price_eur), ('USD', price_usd)]:
        try:
            float_value = float(value)
        except (TypeError, ValueError):
            if value:  # print only if value is non-empty
                print(f"Invalid number for {currency}: {value}")
            float_value = 0.0
        if float_value > 0:
            prices[currency] = float_value

    if len(prices) == 0:
        #print("No valid price > 0 provided.")
        return None, None

    if len(prices) > 1:
        print(f"WARNING: Multiple prices > 0 found: {prices}")
        return None, None

    # prices dict has exactly one item at this point (since checked before)
    # iterating over it and picking the first is safe and efficient
    return next(iter(prices.items()))


def import_qm_devices(input_filepath, company='Microsynth AG', expected_line_length=18):
    """
    bench execute microsynth.qms.doctype.qm_device.qm_device.import_qm_devices --kwargs "{'input_filepath': '/mnt/erp_share/JPe/2025-08-21_Geraeteliste.csv'}"
    """
    group_mapping = {
        '3.1 DNA/RNA Synthese': '3.1 DNA/RNA Synthesis',
        '3.2 Balgach': '3.2 Sequencing',
        '3.2 Lyon': '3.2 Sequencing',
        '3.2 Seqlab': '3.2 Sequencing',
        '3.2 Wien': '3.2 Sequencing',
        '3.2 Sequencing': '3.2 Sequencing',
        '3.3 DNA/RNA Isolation': '3.3 Isolation',
        '3.3 Isolation': '3.3 Isolation',
        '3.4 Genotyping': '3.4 Genotyping',
        '3.5 Real Time PCR': '3.5 PCR',
        '3.5 PCR': '3.5 PCR',
        '3.6 Library Prep': 'TODO',
        '3.6 NGS': '3.6 NGS',
        '3.7 NGS': '3.6 NGS',
        '5.1 Instrumente': '5.1 Instruments',
        '5.1 Instruments': '5.1 Instruments'
    }
    category_mapping = {
        'A': 'A: Complex analytical system',
        'B': 'B: Standard measuring device',
        'C': 'C: Auxiliary non-measuring equipment'
    }
    imported_counter = 0

    with open(input_filepath) as file:
        print(f"INFO: Parsing devices from '{input_filepath}' ...")
        csv_reader = csv.reader((l.replace('\0', '') for l in file), delimiter=";")  # replace NULL bytes (throwing an error)
        next(csv_reader)  # skip header
        for line in csv_reader:
            if len(line) != expected_line_length:
                print(f"ERROR: Line '{line}' has length {len(line)}, but expected length {expected_line_length}. Going to continue.")
                continue
            # parse values
            device_id = line[0].strip()  # remove leading and trailing whitespaces
            device_name = line[1].strip()
            acquisition_date = line[2].strip()
            serial_number = line[3].strip()
            critical_parameters = line[4].strip()
            location = line[5].strip()
            service_instructions = line[6].strip()
            manufacturer = line[7].strip()
            supplier_name = line[8].strip()
            function_control = line[9].strip()
            process = line[10].strip()
            price_chf = line[11].strip()
            price_eur = line[12].strip()
            price_usd = line[13].strip()
            device_classification = line[14].strip()
            requalification_date = line[15].strip()
            quattek_nr = line[16].strip()
            is_archived = line[17].strip()
            # validation
            if not device_id:
                print(f"ERROR: No 'GeräteNr.' in the following line: {line}")
                continue
            if not device_name:
                print(f"ERROR: No 'Gerätename' in the following line: {line}")
                continue
            if not location or len(location) < 2:
                print(f"ERROR: No 'Standort' in the following line: {line}")
                continue
            if not process or len(process) < 2:
                print(f"ERROR: No 'Gruppe' in the following line: {line}")
                continue
            if process not in group_mapping:
                print(f"ERROR: Unknown 'Gruppe' '{process}' in the following line: {line}")
                continue
            if not device_classification:
                print(f"ERROR: No 'ABC_Kundeneinteilung' in the following line: {line}")
                continue
            if device_classification not in category_mapping:
                print(f"ERROR: Unknown 'ABC_Kundeneinteilung' '{device_classification}' in the following line: {line}")
                continue
            if is_archived:
                continue

            if price_eur or price_chf or price_usd:
                pass

            supplier = None
            if supplier_name:
                suppliers = frappe.get_all("Supplier", filters={'supplier_name': supplier_name}, fields=['name'])
                if len(suppliers) > 0:
                    supplier = suppliers[0].get('name')

            name = f"QMDE-{int(device_id):0{5}d}"
            if frappe.db.exists("QM Device", name):
                print(f"ERROR: QM Device {name} already exists, going to skip the following line: {line}")
                continue

            qm_device = frappe.get_doc({
                'doctype': "QM Device",
                'device_name': device_name,
                'category': category_mapping[device_classification],
                'status': 'Unqualified',  # TODO: mandatory, but how to determine?
                'qm_process': group_mapping[process],
                'site': location if location in ['Lyon', 'Göttingen', 'Wien'] else 'Balgach',
                'serial_no': serial_number,
                'service_instructions': service_instructions,
                'manufacturer': manufacturer,
                'supplier': supplier
            })
            qm_device.name = name
            # disable automatic name generation
            qm_device.flags.name_set = True
            qm_device.insert()

            currency, price = convert_price_fields(price_chf, price_eur, price_usd)

            if acquisition_date or price:
                price_str = f" for {price} {currency}." if price else "."
                acq_str = f" on {acquisition_date}" if acquisition_date else ""
                new_comment = frappe.get_doc({
                    'doctype': 'Comment',
                    'comment_type': "Comment",
                    'subject': qm_device.name,
                    'content': f"This device was purchased{acq_str}{price_str}",
                    'reference_doctype': "QM Device",
                    'status': "Linked",
                    'reference_name': qm_device.name
                })
                new_comment.insert(ignore_permissions=True)
            imported_counter += 1

    print(f"Successfully imported {imported_counter} QM Devices.")
