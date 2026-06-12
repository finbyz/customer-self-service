import frappe
from frappe.auth import LoginManager
from frappe.utils import (
    cstr,
    today,
    getdate,
    flt,
    fmt_money,
    pretty_date,
)
from frappe import _
from bs4 import BeautifulSoup
import json


def gen_response(status, message, data=[]):
    frappe.response["http_status_code"] = status
    if status == 500:
        frappe.response["message"] = BeautifulSoup(str(message)).get_text()
    else:
        frappe.response["message"] = message
    frappe.response["data"] = data


@frappe.whitelist(allow_guest=True)
def login(usr, pwd):
    try:
        login_manager = LoginManager()
        login_manager.authenticate(usr, pwd)
        login_manager.post_login()
        if frappe.response["message"] in ["Logged In", "No App"]:
            get_customer()
            frappe.response["user"] = login_manager.user
            frappe.response["key_details"] = generate_key(login_manager.user)
            frappe.response["message"] = "Logged In"
        gen_response(200, frappe.response["message"])
    except frappe.AuthenticationError:
        gen_response(500, frappe.response["message"])
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


def generate_key(user):
    user_details = frappe.get_doc("User", user)
    api_secret = api_key = ""
    if not user_details.api_key and not user_details.api_secret:
        api_secret = frappe.generate_hash(length=15)
        # if api key is not set generate api key
        api_key = frappe.generate_hash(length=15)
        user_details.api_key = api_key
        user_details.api_secret = api_secret
        user_details.save(ignore_permissions=True)
    else:
        api_secret = user_details.get_password("api_secret")
        api_key = user_details.get("api_key")
    return {"api_secret": api_secret, "api_key": api_key}


def get_customer():
    customer = frappe.db.get_value("Customer", {"user": frappe.session.user}, ["name"])
    if not customer:
        frappe.throw(_("Customer Not Exists with logged in user"))
    portal_login = frappe.db.get_value("Customer", customer, ["allow_portal_login"])
    if not portal_login:
        frappe.throw(_("Portal Login Blocked"))
    if customer:
        return customer
    else:
        frappe.throw(_("Customer Not Exists with logged in user"))


@frappe.whitelist()
def get_invoice_details():
    try:
        customer = get_customer()
        invoice_details = frappe.get_all(
            "Sales Invoice",
            filters={"customer": customer},
            fields=[
                "name",
                "posting_date",
                "due_date",
                "grand_total",
                "status",
                "remarks",
            ],
        )
        return gen_response(200, "Invoice List Get Successfully", invoice_details)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_invoice_attachment(invoice_id):
    try:
        validate_document("Sales Invoice", invoice_id)
        res = frappe.get_doc("Sales Invoice", invoice_id)
        default_print_format = frappe.db.get_value(
            "Customer Self Service Settings",
            "Customer Self Service Settings",
            "default_print_format",
        )
        if not default_print_format:
            default_print_format = (
                frappe.db.get_value(
                    "Property Setter",
                    dict(property="default_print_format", doc_type=res.doctype),
                    "value",
                )
                or "Standard"
            )
        # System Language
        language = frappe.get_system_settings("language")
        # return  frappe.utils.get_url()
        url = f"{ frappe.utils.get_url() }/{ res.doctype }/{ res.name }?format={ default_print_format or 'Standard' }&_lang={ language }&key={ res.get_signature() }"
        # return url
        download_pdf(res.doctype, res.name, default_print_format, res)
        # return gen_response(200, "Invoice Details Successfully",dict(url=url))
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


def validate_document(document_type, document_no):
    customer = get_customer()
    if not frappe.db.exists(document_type, document_no):
        frappe.throw(_("{0} Not Exists".format(document_no)))
    document_customer = frappe.db.get_value(document_type, document_no, "customer")
    if not document_customer == customer:
        frappe.throw(
            _("{0} Customer Not Matched With Logged In Customer.".format(document_no))
        )


@frappe.whitelist()
def download_pdf(doctype, name, format=None, doc=None, no_letterhead=1):
    from frappe.utils.pdf import get_pdf, cleanup

    html = frappe.get_print(
        doctype,
        name,
        format,
        doc=doc,
        letterhead="Nesscale",
    )
    frappe.local.response.filename = "{name}.pdf".format(
        name=name.replace(" ", "-").replace("/", "-")
    )
    frappe.local.response.filecontent = get_pdf(html)
    frappe.local.response.type = "download"


# @frappe.whitelist()
# def get_invoice_details():
#     customer = get_customer()


@frappe.whitelist()
def get_support_tickets():
    try:
        customer = get_customer()
        support_tickets = frappe.get_all(
            "Issue",
            filters={"customer": customer},
            fields=["name", "subject", "status", "opening_date"],
        )
        return gen_response(
            200, "Support tickets List Get Successfully", support_tickets
        )
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_support_ticket_detiail(ticket):
    try:
        customer = get_customer()
        task_dict = frappe.db.get_value(
            "Issue",
            {"name": ticket, "customer": customer},
            ["name", "subject", "status", "description", "opening_date"],
            as_dict=1,
        )
        if task_dict == None:
            return gen_response(500, "Ticket not found")
        fields = ["name", "creation as date", "content as comment", "owner as name"]
        # fields=["*"]

        comments = frappe.get_all(
            "Comment",
            fields=fields,
            filters={"reference_doctype": "Issue", "reference_name": ticket},
            order_by="creation asc",
        )
        # from frappe.utils import , now, add_to_date
        for comment in comments:
            comment.date = pretty_date(comment.date)
        task_dict["comments"] = comments
        return gen_response(200, "Support tickets Get Successfully", task_dict)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def add_comment(data):
    try:
        data = json.loads(data)
        customer = get_customer()
        from frappe.desk.form.utils import add_comment

        add_comment(
            reference_doctype="Issue",
            reference_name=data.get("ticket"),
            content=data.get("comment"),
            comment_email=customer,
            comment_by=customer,
        )
        gen_response(200, "Comment added Successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def new_support_ticket(data):
    try:
        customer = get_customer()
        data = json.loads(data)
        frappe.get_doc(
            dict(
                doctype="Issue",
                subject=data.get("subject"),
                customer=customer,
                description=data.get("description"),
            )
        ).insert(ignore_permissions=True)
        msg = "New Ticket Sent Succussfully"
        gen_response(200, msg)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_quotation_list():
    try:
        customer = get_customer()
        quotation_list = frappe.get_all(
            "Quotation",
            filters={"party_name": customer},
            fields=[
                "name",
                "title",
                "status",
                "transaction_date as date",
                "valid_till",
                "total",
            ],
        )
        return gen_response(200, "Quotation List Get Successfully", quotation_list)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_ledger(from_date=None, to_date=None, download="False"):
    try:
        if not from_date or not to_date:
            frappe.throw(_("Select First from date and to date"))
        settings = get_customer_self_service_settings(internal=True)
        currency = frappe.db.get_single_value("Global Defaults", "default_currency")
        customer = get_customer()
        # return emp_data
        filters_report = {
            "company": settings.get("default_company"),
            "from_date": getdate(from_date),
            "to_date": getdate(to_date),
            "account": [],
            "party_type": "Customer",
            "party": [customer],
            "party_name": customer,
            "group_by": "Group by Party",
            "cost_center": [],
            "project": [],
            "include_dimensions": 1,
        }

        from frappe.desk.query_report import run

        res = run("General Ledger", filters=filters_report)
        balance = 0
        data = []
        for row in res.get("result"):
            if "gl_entry" in row.keys():
                row["credit"] = fmt_money(row.get("credit"), currency=currency)
                row["debit"] = fmt_money(row.get("debit"), currency=currency)
                row["balance"] = fmt_money(row.get("balance"), currency=currency)
                if flt(row.get("balance")) >= 0:
                    row["color"] = "red"
                else:
                    row["color"] = "green"
                data.append(row)

        # return gen_response(200, "Ledger Get Successfully",{"data":data,"html_data":download_ledger(filters_report,res.get("result"))})

        if download == "True":
            from frappe.utils.print_format import report_to_pdf

            filters = frappe._dict(filters_report)
            html = frappe.render_template(
                "customer_self_service/templates/customer_statement.html",
                {"filters": filters, "data": data},
                is_path=True,
            )
            return report_to_pdf(html)
        return gen_response(200, "Ledger Get Successfully", {"data": data})
    except Exception as e:
        # frappe.log_error(message=frappe.get_traceback())
        return frappe.get_traceback()
        gen_response(500, cstr(e))


# @frappe.whitelist()
def download_ledger(data):
    from frappe.desk.query_report import get_script

    # return get_script("General Ledger")
    filters = frappe._dict(
        {
            "party_name": "party_name",
            "party": "party",
            "account": "",
            "tax_id": "tax_id",
            "from_date": "from_date",
            "to_date": "to_date",
            "account": "account",
            "presentation_currency": "INR",
        }
    )
    # data = [{
    # 	"posting_date":"2022-01-01",
    # 	"voucher_type": "Sales Invoice",
    # 	"voucher_no": "voucher no",
    # 	"against":"against",
    # 	"bill_no":"011",
    # 	"remarks":"remarks",
    # 	"account":"account",
    # 	"debit":"0",
    # 	"credit":"0",
    # 	"balance":"0"
    # },{
    # 	"posting_date":"2022-01-01",
    # 	"voucher_type": "Sales Invoice",
    # 	"voucher_no": "voucher no",
    # 	"against":"against",
    # 	"bill_no":"011",
    # 	"remarks":"remarks",
    # 	"account":"account",
    # 	"debit":"0",
    # 	"credit":"0",
    # 	"balance":"0"
    # }]
    return frappe.render_template(
        "customer_self_service/templates/customer_statement.html",
        {"filters": filters, "data": data},
        is_path=True,
    )


# get employee id by user
def get_employee_by_user(user):
    emp_data = frappe.db.get_value(
        "Employee", {"user_id": user}, ["name", "company"], as_dict=1
    )
    return emp_data


@frappe.whitelist()
def get_item_list(start=0, page_length=20, filters=dict()):
    try:
        item_list = frappe.get_all(
            "Item",
            fields=[
                "name",
                "item_name",
                "item_code",
                "image",
                "'55.44' as box_price",
                "'44.00' as m2_price",
                "'300*300' as size",
                "description",
                "item_group",
                "'0' as price",
                "'' as parent_item_group",
            ],
            filters=filters,
            order_by="creation desc",
            limit_start=start,
            limit_page_length=page_length,
        )
        for items in item_list:
            items["image"] = [items["image"]]
            items["price"] = get_item_selling_price(items.get("name"))
            items["parent_item_group"] = frappe.db.get_value(
                "Item Group", items.get("item_group"), "parent_item_group"
            )
        return gen_response(200, "Item List Get Successfully", item_list)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_item_categories():
    try:
        item_groups = frappe.get_all(
            "Item Group", filters={}, fields=["name"]
        )
        return gen_response(200, "Item group get successfully", item_groups)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def new_quotation_request(**kwargs):
    try:
        customer = get_customer()
        data = kwargs
        doc = frappe.get_doc(
            dict(
                doctype="Quotation Requets",
                date=today(),
                customer=customer,
                item_details=data.get("items"),
            )
        ).insert(ignore_permissions=True)
        doc.save(ignore_permissions=True)
        gen_response(200, "Quotation Request added Succussfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_customer_self_service_settings(internal=False):
    try:
        settings_doc = frappe.get_doc(
            "Customer Self Service Settings", "Customer Self Service Settings"
        )
        if internal:
            return settings_doc
        else:
            return gen_response(200, "Portal Settings Get Successfully", settings_doc)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist(allow_guest=True)
def clickpay(cartId="test"):
    try:
        frappe.log_error(cartId)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist(allow_guest=True)
def dummy_invoice():
    doc = frappe.get_doc(
        dict(
            doctype="Sales Order",
            company="Nesscale Solutions Private Limited",
            customer="Nilesh Makwana",
            date=today(),
            due_date=today(),
        )
    )
    # new_doc = frappe.new_doc('Sales Invoice')
    # new_doc.company = "StradaPOS",
    # new_doc.customer = "Nilesh Makwana",
    doc.append("items", dict(item_code="Item Demo", qty=1, rate=150.00))
    # new_doc.date = today()
    # new_doc.due_date = today()
    doc.run_method("set_missing_values")
    doc.run_method("calculate_taxes_and_totals")
    return doc


@frappe.whitelist()
def get_place_order_items():
    try:
        if not validate_ecommerce():
            return gen_response(500, "Invalid Method")
        group_list = frappe.get_all(
            "Item Group",
            filters={"show_in_website": 1},
            fields=["name", "item_group_name", "image"],
        )
        for group in group_list:
            group["items"] = get_item_by_group(group.name)
        return gen_response(200, "Item Group Get Successfully", group_list)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


def get_item_by_group(group):
    item_list = frappe.get_all(
        "Item",
        filters={"item_group": group},
        fields=["name", "item_name", "item_code", "image", "'1' as qty"],
    )
    return item_list


@frappe.whitelist()
def get_customer_information():
    try:
        customer_name = get_customer()
        customer = frappe.db.get_value(
            "Customer",
            customer_name,
            [
                "name as id",
                "customer_name",
                "email_id",
                "mobile_no",
                "website",
                "customer_primary_address",
                "primary_address",
            ],
            as_dict=1,
        )
        return gen_response(200, "Customer Get Successfully", customer)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_customer_address(address_id):
    try:
        customer_name = get_customer()
        fields = [
            "name",
            "address_title",
            "address_type",
            "address_line1",
            "address_line2",
            "city",
            "county",
            "state",
            "country",
            "pincode",
            "email_id",
            "phone",
            "is_primary_address",
            "is_shipping_address",
        ]
        address = frappe.db.get_all(
            "Address",
            filters={
                "link_doctype": "Customer",
                "link_name": customer_name,
                "name": address_id,
            },
            fields=fields,
        )
        if not len(address) > 0:
            return gen_response(500, "Invalid Address")
        return gen_response(200, "Customer Adress Get Successfully", address)
    except Exception as e:
        gen_response(500, cstr(e))


@frappe.whitelist()
def update_customer_information(data):
    try:
        customer_name = get_customer()
        data = json.loads(data)
        doc = frappe.get_doc("Customer", customer_name)
        doc.customer_name = data.get("customer_name")
        doc.pan = data.get("pan")
        doc.website = data.get("website")
        doc.email_id = data.get("email_id")
        doc.mobile_no = data.get("mobile_no")
        doc.save(ignore_permissions=True)
        return gen_response(200, "Customer Updated Successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def update_customer_default_address(data):
    try:
        customer_name = get_customer()
        data = json.loads(data)
        address = frappe.db.get_all(
            "Address",
            filters={
                "link_doctype": "Customer",
                "link_name": customer_name,
                "name": data.get("customer_primary_address"),
            },
        )
        if not len(address) > 0:
            return gen_response(500, "Invalid Address")
        doc = frappe.get_doc("Customer", customer_name)
        doc.customer_primary_address = data.get("customer_primary_address")
        doc.save(ignore_permissions=True)
        return gen_response(200, "Default Address Updated Successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def get_addresses():
    try:
        customer_name = get_customer()
        fields = [
            "name",
            "address_title",
            "address_type",
            "address_line1",
            "address_line2",
            "city",
            "county",
            "state",
            "country",
            "pincode",
            "email_id",
            "phone",
            "is_primary_address",
            "is_shipping_address",
        ]
        address_list = frappe.db.get_all(
            "Address",
            filters={"link_doctype": "Customer", "link_name": customer_name},
            fields=fields,
        )
        return gen_response(200, "Successfully", address_list)
    except Exception as e:
        gen_response(500, cstr(e))


@frappe.whitelist()
def create_address(data):
    try:
        customer_name = get_customer()
        data = json.loads(data)
        doc = frappe.get_doc(
            {
                "doctype": "Address",
                "address_title": data.get("address_title"),
                "address_type": data.get("address_type"),
                "address_line1": data.get("address_line1"),
                "address_line2": data.get("address_line2"),
                "city": data.get("city"),
                "county": data.get("county"),
                "state": data.get("state"),
                "country": data.get("country"),
                "pincode": data.get("pincode"),
                "email_id": data.get("email_id"),
                "phone": data.get("phone"),
                "is_primary_address": data.get("is_primary_address"),
                "is_shipping_address": data.get("is_shipping_address"),
                "links": [{"link_doctype": "Customer", "link_name": customer_name}],
            }
        ).insert(ignore_permissions=True)
        return gen_response(200, "Customer Address Added Successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(e))


@frappe.whitelist()
def update_address(data):
    try:
        customer_name = get_customer()
        data = json.loads(data)
        address = frappe.db.get_all(
            "Address",
            filters={
                "link_doctype": "Customer",
                "link_name": customer_name,
                "name": data.get("name"),
            },
        )
        if not len(address) > 0:
            return gen_response(500, "Invalid Address")
        doc = frappe.get_doc("Address", data.get("name"))
        doc.address_title = data.get("address_title")
        doc.address_type = data.get("address_type")
        doc.address_line1 = data.get("address_line1")
        doc.address_line2 = data.get("address_line2")
        doc.city = data.get("city")
        doc.county = data.get("county")
        doc.state = data.get("state")
        doc.country = data.get("country")
        doc.pincode = data.get("pincode")
        doc.email_id = data.get("email_id")
        doc.phone = data.get("phone")
        doc.is_primary_address = data.get("is_primary_address")
        doc.is_shipping_address = data.get("is_shipping_address")
        doc.save(ignore_permissions=True)
        return gen_response(200, "Customer Address Updated Successfully")
    except Exception as e:
        gen_response(500, cstr(e))


@frappe.whitelist()
def delete_address(data):
    try:
        data = json.loads(data)
        if not frappe.db.exists("Address", data.get("name"), cache=True):
            return gen_response(500, "Address does not exists")
        customer_name = get_customer()
        address = frappe.db.get_all(
            "Address",
            filters={
                "link_doctype": "Customer",
                "link_name": customer_name,
                "name": data.get("name"),
            },
        )
        if not len(address) > 0:
            return gen_response(500, "Invalid Address")
        doc = frappe.get_doc("Address", data.get("name"))
        doc.delete()
        gen_response(200, "You have successfully deleted Address")
    except Exception as exec:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        gen_response(500, cstr(exec))


# @frappe.whitelist()
# def get_dashboard_info():
#     try:
#         dashboard_data = dict(
#             active_tickets=0, closed_tickets=0, active_orders=0, outstanding_balance=0
#         )
#         dashboard_data["ticket_history_items"] = [
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#         ]
#         dashboard_data["order_history_items"] = [
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#         ]
#         dashboard_data["transactions_history_items"] = [
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#             {"id": "1", "date": "04/01/2022", "status": "Declined"},
#         ]

#         return gen_response(200, "Success", dashboard_data)
#     except Exception as e:
#         frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
#         gen_response(500, cstr(e))


@frappe.whitelist()
def validate_ecommerce():
    return frappe.db.get_single_value(
        "Customer Self Service Settings", "enable_ecommerce"
    )


@frappe.whitelist()
def change_password(data):
    from frappe.utils.password import check_password, update_password

    data = json.loads(data)
    user = frappe.session.user
    current_password = data.get("current_password")
    new_password = data.get("new_password")
    try:
        check_password(user, current_password)
        update_password(user, new_password)
        return gen_response(200, "Password updated")
    except frappe.AuthenticationError:
        return gen_response(500, "Incorrect current password")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_dashboard_info():
    try:
        customer = get_customer()
        open_tickets = frappe.db.count(
            "Issue",
            filters=[
                ["Issue", "customer", "=", customer],
                ["Issue", "status", "=", "Open"],
            ],
        )

        closed_tickets = frappe.db.count(
            "Issue",
            filters=[
                ["Issue", "customer", "=", customer],
                ["Issue", "status", "=", "Closed"],
            ],
        )

        active_orders = frappe.db.count(
            "Sales Invoice",
            filters=[
                ["Sales Invoice", "customer", "=", customer],
                ["Sales Invoice", "status", "=", "Paid"],
            ],
        )

        # outstanding_balance = (
        # 	frappe.db.get_value("GL Entry", {"against": customer}, "SUM(debit)") or 0
        # )
        from erpnext.accounts.utils import get_balance_on

        outstanding_balance = fmt_money(
            get_balance_on(party_type="Customer", party=customer, date=today())
        )
        ticket_history_items = frappe.get_all(
            "Issue",
            filters=[["Issue", "customer", "=", customer]],
            fields=["name as id", "status", "opening_date as date"],
            order_by="creation asc",
            limit=5,
        )

        order_history_items = frappe.get_all(
            "Sales Invoice",
            filters=[
                ["Sales Invoice", "customer", "=", customer],
            ],
            fields=["name as id", "posting_date as date", "status"],
            order_by="creation asc",
            limit=5,
        )

        transactions_history_items = frappe.get_all(
            "Payment Entry",
            filters=[["Payment Entry", "party", "=", customer]],
            fields=["name as id", "posting_date as date", "status"],
            order_by="creation asc",
        )

        response = {
            "active_orders": active_orders,
            "active_tickets": open_tickets,
            "closed_tickets": closed_tickets,
            "outstanding_balance": outstanding_balance,
            "ticket_history_items": ticket_history_items,
            "order_history_items": order_history_items,
            "transactions_history_items": transactions_history_items,
        }

        return gen_response(200, "Dashboard Data", response)

    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


@frappe.whitelist()
def get_item(**kwargs):
    try:
        data = kwargs
        if not data.get("id"):
            return gen_response(500, "please add product id")
        if not frappe.db.exists("Item", data.get("id")):
            return gen_response(500, "product does not exists")

        # item = frappe.db.get_value(
        #     "Item",
        #     data.get("id"),
        #     [
        #         "name",
        #         "item_name",
        #         "item_code",
        #         "description",
        #         "image",
        #     ],
        #     as_dict=1,
        # )
        item = frappe.get_doc("Item", data.get("id")).as_dict()
        # item["image"] = [item["image"]]
        images_list = frappe.get_all(
            "Item Images", {"parent": data.get("id")}, pluck="item_image"
        )
        if item["image"]:
            images_list.insert(0, item["image"])
        item["image"] = images_list
        item["price"] = get_item_selling_price(item.get("item_code"))
        item["parent_item_group"] = frappe.db.get_value(
            "Item Group", item.get("item_group"), "parent_item_group"
        )
        # item["size"] = "600*600"
        # item["available_qty"] = "562/SQM"
        item["actual_qty"] = get_item_actual_qty(item.get("item_code"))
        item["projected_qty"] = get_item_projected_qty(item.get("item_code"))
        # item["no_of_boxes"] = "25"
        # item["color"] = "Gold Material"
        # item["porcelain_unit_of_measurement"] = "EA"
        # item["item_per_box"] = "4"
        # item["square_meter_per_box"] = "1"
        # item["finish"] = "High Gloss"
        # item["edge"] = "Rectified"
        # item["variation"] = "No Variation (V0)"
        # item["recommended_grout_color"] = "White"
        # item["length"] = "600m"
        # item["width"] = "600m"
        # item["box_price"] = "55.44"
        # item["m2_price"] = "44.00"
        # item["height"] = "10m"
        return gen_response(200, "product details getting successfully", item)
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))


def get_item_selling_price(item_code):
    currency = frappe.db.get_single_value("Global Defaults", "default_currency")
    price_list = frappe.db.get_value("Customer", get_customer(), "default_price_list")
    if not price_list:
        price_list = frappe.db.get_single_value(
            "Selling Settings", "selling_price_list"
        ) or frappe.db.get_value("Price List", _("Standard Selling"))
    return fmt_money(
        frappe.db.get_value(
            "Item Price",
            {"item_code": item_code, "price_list": price_list},
            "price_list_rate",
        )
        or 0.0,
        currency=currency,
    )


def get_item_projected_qty(item_code):
    return frappe.db.get_value(
        "Bin", {"item_code": item_code}, "sum(projected_qty) as projected_qty"
    )


def get_item_actual_qty(item_code):
    return frappe.db.get_value(
        "Bin", {"item_code": item_code}, "sum(actual_qty) as actual_qty"
    )


# @frappe.whitelist()
# def create_product_inquiry(**kwargs):
#     try:
#         data = kwargs
#         customer = get_customer()
#         existing_product_inquiry = frappe.db.get_value(
#             "Product Inquiry", {"customer": customer, "date": today()}, "name"
#         )
#         if existing_product_inquiry:
#             existing_doc = frappe.get_doc("Product Inquiry", existing_product_inquiry)
#             for item in data.get("items"):
#                 existing_doc.append(
#                     "items", dict(item=item.get("item"), qty=item.get("qty"))
#                 )
#             existing_doc.save()
#         else:
#             doc = frappe.get_doc(
#                 dict(
#                     doctype="Product Inquiry",
#                     customer=customer,
#                     date=today(),
#                     items=data.get("items"),
#                 )
#             )
#             doc.insert()
#         return gen_response(200, "Product Inquiry added successfully")
#     except Exception as e:
#         frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
#         return gen_response(500, cstr(e))


@frappe.whitelist()
def create_product_inquiry(**kwargs):
    try:
        data = kwargs
        customer = get_customer()
        existing_product_inquiry = frappe.db.get_value(
            "Product Inquiry", {"customer": customer, "date": today()}, "name"
        )
        if existing_product_inquiry:
            doc = frappe.get_doc("Product Inquiry", existing_product_inquiry)
        else:
            doc = frappe.get_doc(
                dict(
                    doctype="Product Inquiry",
                    customer=customer,
                    date=today(),
                )
            )
        for item in data.get("items"):
            item_found = False
            for existing_item in doc.items:
                if item.get("item") == existing_item.item:
                    existing_item.qty = int(existing_item.qty) + int(item.get("qty"))
                    item_found = True
                    break
            if not item_found:
                doc.append("items", dict(item=item.get("item"), qty=item.get("qty")))
        doc.save()
        return gen_response(200, "Product Inquiry added successfully")
    except Exception as e:
        frappe.log_error(title="CSS Web Error", message=frappe.get_traceback())
        return gen_response(500, cstr(e))
