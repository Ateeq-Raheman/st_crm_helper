/**
 * ST CRM Helper — CRM Form Guard
 * ================================
 * Injected via doctype_js into all 7 CRM doctypes.
 *
 * On form load, checks whether the record's department is in the
 * current user's allowed department list.
 * If NOT → silently redirects back to the list view.
 *
 * This is the frontend half of Layer 2 enforcement.
 * The server-side has_permission hook is Layer 1 (Python).
 */

(function () {
	"use strict";

	const GUARDED_DOCTYPES = [
		"CRM Lead",
		"CRM Deal",
		"CRM Organization",
		"CRM Task",
		"FCRM Note",
		"CRM Call Log",
	];

	GUARDED_DOCTYPES.forEach((dt) => {
		frappe.ui.form.on(dt, {
			async onload(frm) {
				// Skip brand-new unsaved records
				if (frm.is_new()) return;

				await _guardRecord(frm);
			},
		});
	});

	async function _guardRecord(frm) {
		try {
			// Ensure dept data is loaded (usually already cached from list view)
			const data = await stCrmHelper.fetchDeptData();

			// Bypass users (System Manager / Admin) see everything
			if (data.bypass) return;

			const recordDept = frm.doc.department;

			// Records with no department set (legacy) — allow through
			if (!recordDept) return;

			const allowed = data.departments || [];

			if (!allowed.includes(recordDept)) {
				// Silently redirect — do not show the record at all
				frappe.set_route("List", frm.doctype);
				frappe.show_alert(
					{ message: __("Access restricted to your department."), indicator: "red" },
					4
				);
			}
		} catch (err) {
			console.error("ST CRM Helper: form guard error", err);
		}
	}
})();
