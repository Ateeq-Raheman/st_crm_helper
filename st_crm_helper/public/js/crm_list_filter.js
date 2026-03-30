/**
 * ST CRM Helper — CRM List Filter
 * =================================
 * Injected into all 7 CRM doctypes via doctype_list_js in hooks.py.
 * Silently applies the department filter on every list view load.
 * Renders a department switcher dropdown in the list header.
 *
 * Works in both Frappe Desk (standard list) and Frappe CRM Vue SPA
 * (which also uses frappe.call under the hood).
 */

(function () {
	"use strict";

	const DOCTYPES = [
		"CRM Lead",
		"CRM Deal",
		"CRM Organization",
		"CRM Task",
		"FCRM Note",
		"CRM Call Log",
	];

	DOCTYPES.forEach((dt) => {
		frappe.listview_settings[dt] = frappe.listview_settings[dt] || {};

		const original_onload = frappe.listview_settings[dt].onload;

		frappe.listview_settings[dt].onload = async function (listview) {
			// Run original onload if exists
			if (original_onload) original_onload(listview);

			// Ensure dept data is ready
			await stCrmHelper.fetchDeptData();

			// Apply filter silently
			_applyDeptFilter(listview);

			// Inject the switcher widget into list header
			_injectSwitcher(listview);

			// Re-apply when dept changes from widget
			window.addEventListener("st-crm-dept-changed", () => {
				_removeExistingDeptFilters(listview);
				_applyDeptFilter(listview);
				listview.refresh();
			});
		};
	});

	/**
	 * Apply department IN (...) filter to the list view.
	 * Silently — no toast, no banner.
	 */
	function _applyDeptFilter(listview) {
		const depts = stCrmHelper.getActiveDepts();

		if (depts === null) return; // Admin, no filter needed

		_removeExistingDeptFilters(listview);

		if (depts.length === 0) {
			// User has no department — nothing should show
			listview.filter_area.add([
				[listview.doctype, "department", "=", "__NO_ACCESS__"],
			]);
			return;
		}

		if (depts.length === 1) {
			listview.filter_area.add([
				[listview.doctype, "department", "=", depts[0]],
			]);
		} else {
			listview.filter_area.add([
				[listview.doctype, "department", "in", depts.join(",")],
			]);
		}
	}

	/**
	 * Remove any previously injected department filters to avoid stacking.
	 */
	function _removeExistingDeptFilters(listview) {
		try {
			const filters = listview.filter_area.get();
			filters.forEach((f) => {
				if (f[1] === "department") {
					listview.filter_area.remove(f[0], f[1]);
				}
			});
		} catch (e) {
			// Filter area may not expose remove cleanly — silently ignore
		}
	}

	/**
	 * Inject the department switcher dropdown into the list page header.
	 * Shows "All Departments" + individual dept options.
	 * Hidden if user has only 1 dept (filter applied automatically).
	 */
	function _injectSwitcher(listview) {
		const data = stCrmHelper.deptData;
		if (!data) return;

		// Only show widget for bypass users (admin) or users with 2+ depts
		const showWidget = data.bypass || data.departments.length > 1;
		if (!showWidget) return;

		// Remove any stale widget
		$(".st-crm-dept-switcher").remove();

		const depts = data.all_departments || [];
		const current = stCrmHelper.selectedDept || "all";

		// Build <select> options
		const opts = [{ v: "all", l: "🏢 All Departments" }]
			.concat(depts.map((d) => ({ v: d, l: d })))
			.map(
				(o) =>
					`<option value="${_esc(o.v)}" ${current === o.v ? "selected" : ""}>${_esc(o.l)}</option>`
			)
			.join("");

		const $widget = $(`
			<div class="st-crm-dept-switcher" style="
				display:inline-flex;align-items:center;gap:6px;
				margin-right:10px;font-family:'Montserrat',sans-serif;font-size:12px;">
				<span style="color:#434445;font-weight:600;white-space:nowrap;">Department:</span>
				<div style="position:relative;display:inline-flex;align-items:center;">
					<select class="st-dept-select" style="
						appearance:none;-webkit-appearance:none;
						border:1.5px solid #ee1c29;border-radius:6px;
						padding:5px 28px 5px 10px;
						font-family:'Montserrat',sans-serif;font-size:12px;font-weight:500;
						color:#131419;background:#fff;cursor:pointer;outline:none;">
						${opts}
					</select>
					<svg style="position:absolute;right:7px;pointer-events:none;color:#ee1c29;"
						width="11" height="11" viewBox="0 0 24 24" fill="none"
						stroke="currentColor" stroke-width="2.5">
						<polyline points="6 9 12 15 18 9"/>
					</svg>
				</div>
			</div>
		`);

		$widget.find(".st-dept-select").on("change", function () {
			stCrmHelper.setDept(this.value);
		});

		// Mount in the list header actions bar
		const $bar =
			listview.page.$title_area ||
			listview.page.page_actions ||
			$(".page-head .page-actions").first();

		if ($bar && $bar.length) {
			$bar.prepend($widget);
		}
	}

	function _esc(str) {
		return String(str)
			.replace(/&/g, "&amp;")
			.replace(/</g, "&lt;")
			.replace(/>/g, "&gt;")
			.replace(/"/g, "&quot;");
	}
})();
