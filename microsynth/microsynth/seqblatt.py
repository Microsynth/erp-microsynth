# -*- coding: utf-8 -*-
# Copyright (c) 2022, Microsynth AG, libracore (https://www.libracore.com) and contributors
# For license information, please see license.txt
#
# For more details, refer to https://github.com/Microsynth/erp-microsynth/
#

import requests
import frappe
from frappe import _
from frappe.utils import cint
import json
from datetime import datetime

"""

"""
@frappe.whitelist(allow_guest=True)
def lock_label(input):
    # required: LabelNumber, LabelType

    return


def unlock_labe(allow_guest=True):
    # required: LabelNumber, LabelType

    return 