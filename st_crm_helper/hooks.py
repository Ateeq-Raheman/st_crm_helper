app_name = "st_crm_helper"
app_title = "ST CRM Helper"
app_publisher = "StandardTouch e-Solutions"
app_description = "Department-based access control for Frappe CRM"
app_email = "info@standardtouch.com"
app_license = "MIT"
app_version = "0.1.0"

required_apps = ["crm"]

# ─── Fixtures ─────────────────────────────────────────────────────────────────
# Export custom fields belonging to this app via bench export-fixtures
fixtures = [
	{
		"dt": "Custom Field",
		"filters": [["module", "=", "CRM Department"]],
	}
]

# ─── Include JS in Desk (applies globally to all desk pages) ──────────────────
app_include_js = [
	"/assets/st_crm_helper/js/st_crm_helper.min.js",
]

# ─── Override whitelisted methods — dashboard department filtering ─────────────
# These redirect CRM dashboard API calls through our department-aware wrappers.
override_whitelisted_methods = {
	"crm.api.dashboard.get_dashboard": "st_crm_helper.api.dashboard.get_dashboard",
	"crm.api.dashboard.get_chart":     "st_crm_helper.api.dashboard.get_chart",
}

# ─── DocType JS — list views ──────────────────────────────────────────────────
doctype_list_js = {
	"CRM Lead":         "public/js/crm_list_filter.js",
	"CRM Deal":         "public/js/crm_list_filter.js",
	"CRM Organization": "public/js/crm_list_filter.js",
	"CRM Task":         "public/js/crm_list_filter.js",
	"FCRM Note":        "public/js/crm_list_filter.js",
	"CRM Call Log":     "public/js/crm_list_filter.js",
}

# ─── DocType JS — form views ──────────────────────────────────────────────────
doctype_js = {
	"CRM Lead":         "public/js/crm_form_guard.js",
	"CRM Deal":         "public/js/crm_form_guard.js",
	"CRM Organization": "public/js/crm_form_guard.js",
	"CRM Task":         "public/js/crm_form_guard.js",
	"FCRM Note":        "public/js/crm_form_guard.js",
	"CRM Call Log":     "public/js/crm_form_guard.js",
}

# ─── Permission Query Conditions — server-side SQL filter ────────────────────
permission_query_conditions = {
	"CRM Lead":         "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"CRM Deal":         "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"CRM Contacts":     "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"CRM Organization": "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"CRM Task":         "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"FCRM Note":        "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
	"CRM Call Log":     "st_crm_helper.overrides.department_filter.get_permission_query_conditions",
}

# ─── has_permission — record-level access guard ───────────────────────────────
has_permission = {
	"CRM Lead":         "st_crm_helper.overrides.department_filter.has_permission",
	"CRM Deal":         "st_crm_helper.overrides.department_filter.has_permission",
	"CRM Contacts":     "st_crm_helper.overrides.department_filter.has_permission",
	"CRM Organization": "st_crm_helper.overrides.department_filter.has_permission",
	"CRM Task":         "st_crm_helper.overrides.department_filter.has_permission",
	"FCRM Note":        "st_crm_helper.overrides.department_filter.has_permission",
	"CRM Call Log":     "st_crm_helper.overrides.department_filter.has_permission",
}

# ─── Document Events — auto-set department on record creation ─────────────────
doc_events = {
	"CRM Lead":         {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"CRM Deal":         {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"CRM Contacts":     {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"CRM Organization": {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"CRM Task":         {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"FCRM Note":        {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
	"CRM Call Log":     {"before_insert": "st_crm_helper.overrides.department_filter.set_department_on_insert"},
}

# ─── After Install / Migrate ──────────────────────────────────────────────────
after_install = "st_crm_helper.install.after_install"
after_migrate = ["st_crm_helper.install.after_migrate"]