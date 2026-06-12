// Copyright (c) 2023, Nesscale Solutions Pvt Ltd and contributors
// For license information, please see license.txt

frappe.ui.form.on('Product Inquiry', {
	refresh: function(frm) {
		frm.add_custom_button(__("Create Quotation"), function(){
			frm.events.make_quotation(); 
		})
	},
	make_quotation: function(frm) { 
		frappe.model.open_mapped_doc({
			method: "customer_self_service.customer_self_service.doctype.product_inquiry.product_inquiry.make_quotation",
			frm: cur_frm
		});
	}
});


