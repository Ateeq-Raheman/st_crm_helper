/**
 * ST CRM Helper — Department Filter (Global)
 * ============================================
 * Loaded on every desk page via app_include_js.
 * Fetches the current user's department context once per session
 * and stores it on window.stCrmHelper for use by list/form scripts.
 *
 * Also listens for the custom 'st-crm-dept-changed' event fired by the
 * dept switcher widget so list views can refresh automatically.
 */

window.stCrmHelper = window.stCrmHelper || {};

stCrmHelper.deptData = null;         // { bypass, departments, all_departments }
stCrmHelper.selectedDept = null;     // "all" | "Dept Name"

const ST_CRM_STORAGE_KEY = "st_crm_selected_dept";

/**
 * Fetch user's department context from the server.
 * Returns a Promise that resolves to the dept data object.
 * Cached after the first call — subsequent calls return immediately.
 */
stCrmHelper.fetchDeptData = function () {
	if (stCrmHelper.deptData) {
		return Promise.resolve(stCrmHelper.deptData);
	}

	return frappe
		.call({ method: "st_crm_helper.api.department.get_my_departments", freeze: false })
		.then((r) => {
			stCrmHelper.deptData = r.message;

			// Restore last selected dept from localStorage
			const stored = localStorage.getItem(ST_CRM_STORAGE_KEY) || "all";
			const valid =
				stored === "all" ||
				(stCrmHelper.deptData.all_departments || []).includes(stored);
			stCrmHelper.selectedDept = valid ? stored : "all";

			return stCrmHelper.deptData;
		})
		.catch((err) => {
			console.error("ST CRM Helper: failed to fetch dept data", err);
			stCrmHelper.deptData = { bypass: false, departments: [], all_departments: [] };
			stCrmHelper.selectedDept = "all";
			return stCrmHelper.deptData;
		});
};

/**
 * Returns the list of departments that should be used as the active filter.
 * null  → no filter (admin seeing all)
 * []    → empty — user has no departments, block everything
 * [...] → filter to these departments
 */
stCrmHelper.getActiveDepts = function () {
	const d = stCrmHelper.deptData;
	if (!d) return [];

	if (d.bypass && stCrmHelper.selectedDept === "all") return null; // admin, no filter

	if (stCrmHelper.selectedDept !== "all") return [stCrmHelper.selectedDept];

	return d.departments; // "all" selected by a multi-dept user
};

/**
 * Set the active department and persist to localStorage.
 * Dispatches 'st-crm-dept-changed' so listening list views can refresh.
 */
stCrmHelper.setDept = function (dept) {
	stCrmHelper.selectedDept = dept;
	localStorage.setItem(ST_CRM_STORAGE_KEY, dept);
	window.dispatchEvent(
		new CustomEvent("st-crm-dept-changed", { detail: { department: dept } })
	);
};

// Pre-fetch on desk load so it's ready by the time a list view opens
$(document).ready(function () {
	if (frappe.session && frappe.session.user && frappe.session.user !== "Guest") {
		stCrmHelper.fetchDeptData();
	}
});
