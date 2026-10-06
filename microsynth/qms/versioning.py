# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import re

import frappe
from frappe.utils import cint


def split_versioned_name(name):
    match = re.match(r"^(.*?)(?:-(\d{1,2}))?$", name)
    if not match:
        return name, 0

    base_name = match.group(1)
    suffix = int(match.group(2)) if match.group(2) else 0
    return base_name, suffix


def is_cancelled_version(status, docstatus):
    return cint(docstatus) == 2 or status == "Cancelled"


def get_versioned_documents(doctype, current_name):
    base_name, current_suffix = split_versioned_name(current_name)
    candidates = frappe.get_all(
        doctype,
        filters={"name": ["like", "{0}%".format(base_name)]},
        fields=["name", "status", "docstatus"],
    )

    versions = []
    for candidate in candidates:
        candidate_name = candidate.get("name")
        candidate_base, candidate_suffix = split_versioned_name(candidate_name)
        if candidate_base == base_name:
            versions.append((
                candidate_suffix,
                candidate_name,
                candidate.get("status"),
                candidate.get("docstatus"),
            ))

    return base_name, current_suffix, sorted(versions, key=lambda item: item[0])


def get_newer_active_versions(versions, current_suffix):
    return [
        name
        for suffix, name, status, docstatus in versions
        if suffix > current_suffix and not is_cancelled_version(status, docstatus)
    ]


def get_next_suffix(versions, current_suffix=0):
    return max([suffix for suffix, name, status, docstatus in versions], default=current_suffix) + 1
