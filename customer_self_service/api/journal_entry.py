import frappe
from frappe.utils import cstr
from frappe import _
from customer_self_service.api.portal import gen_response

## Journal Entry Apis ##


@frappe.whitelist()
def make_journal_entry(**kwargs):
    try:
        data = kwargs
        global_default = frappe.get_doc("Global Defaults", "Global Defaults")
        if data.get("name"):
            if not frappe.db.exists("Journal Entry", data.get("name")):
                return gen_response(500, "Journal Entry not exists")
            journal_entry_doc = frappe.get_doc("Journal Entry", data.get("name"))
            journal_entry_doc.update(data)
            journal_entry_doc.save()
            gen_response(200, "Journal Entry Updated Successfully")
        else:
            journal_entry_doc = frappe.get_doc(
                dict(
                    doctype="Journal Entry",
                    company=global_default.get("default_company"),
                )
            )
            journal_entry_doc.update(data)
            journal_entry_doc.save()
            return gen_response(200, "Journal Entry added Successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_mode_of_payment():
    try:
        mode_of_payments = frappe.get_all("Mode of Payment", fields=["name"])
        return gen_response(
            200, "mode of payment getting successfully", mode_of_payments
        )
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_journal_entry_list():
    try:
        journal_entry_list = frappe.get_all(
            "Journal Entry", fields=["name"], order_by="creation desc"
        )
        return gen_response(
            500, "jounral entry getting successfully", journal_entry_list
        )
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_journal_entry_details(**kwargs):
    try:
        data = kwargs
        if not data.get("name"):
            return gen_response(500, "please add journal entry name")
        if not frappe.db.exists("Journal Entry", data.get("name")):
            return gen_response(500, "journal entry not exists")
        journal_entry_doc = frappe.get_doc("Journal Entry", data.get("name"))
        return gen_response(
            200, "journal entry detail getting successfully", journal_entry_doc
        )
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def submit_journal_entry(**kwargs):
    try:
        data = kwargs
        if not data.get("name"):
            return gen_response(500, "please add name")
        if not frappe.db.exists("Journal Entry", data.get("name")):
            return gen_response(500, "Journal entry does not exists")
        journal_entry_doc = frappe.get_doc("Journal Entry", data.get("name"))
        journal_entry_doc.flags.ignore_permissions = True
        journal_entry_doc.submit()
        return gen_response(200, "Journal entry submitted successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def delete_journal_entry(**kwargs):
    try:
        data = kwargs
        if not data.get("name"):
            return gen_response(500, "please add name")
        if not frappe.db.exists("Journal Entry", data.get("name")):
            return gen_response(500, "journal entry does not exists")
        journal_entry_doc = frappe.get_doc("Journal Entry", data.get("name"))
        if journal_entry_doc.docstatus == 1:
            journal_entry_doc.flags.ignore_permissions = True
            journal_entry_doc.cancel()
        frappe.delete_doc(
            "Journal Entry", data.get("name"), force=1, ignore_permissions=True
        )
        return gen_response(200, "Journal Entry deleted successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))
