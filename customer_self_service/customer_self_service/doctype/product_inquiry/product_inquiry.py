# Copyright (c) 2023, Nesscale Solutions Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.model.mapper import get_mapped_doc
from frappe.utils import cstr


class ProductInquiry(Document):
    pass


@frappe.whitelist()
def make_quotation(source_name, target_doc=None):
    try:

        def set_missing_value(source, target):
            quotation = frappe.get_doc(target)
            quotation.run_method("set_missing_values")

        doclist = get_mapped_doc(
            "Product Inquiry",
            source_name,
            {
                "Product Inquiry": {
                    "doctype": "Quotation",
                    "field_map": {"customer": "party_name"},
                },
                "Product Inquiry Item Details": {
                    "doctype": "Quotation Item",
                    "field_map": {
                        "item": "item_code",
                        "qty": "qty",
                    },
                },
            },
            target_doc,
            set_missing_value,
        )
        return doclist
    except Exception as e:
        frappe.log_error(
            title="CSS Make Quotation Error", message=frappe.get_traceback()
        )
        return cstr(e)
