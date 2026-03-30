"""
st_crm_helper.overrides.department_filter
==========================================
Server-side department-based access control for all CRM doctypes.

Registered in hooks.py via:
  - permission_query_conditions  → filters list views and API calls
  - has_permission               → guards individual record access
  - doc_events.before_insert     → auto-sets department on new records

Rules:
  - System Manager / Administrator  → no filter, sees everything
  - User with departments           → filtered to their department(s)
  - User with no departments        → sees nothing (1=0)
"""

import frappe
from frappe import _

# Roles that bypass all department filtering
BYPASS_ROLES = frozenset({"System Manager", "Administrator"})

# frappe.local attribute prefix for per-request cache
_CACHE_PREFIX = "st_crm_user_depts_"


def _is_bypass_user(user: str) -> bool:
	"""Return True if the user should bypass all department filters."""
	if user in ("Administrator", "Guest"):
		return True
	return bool(set(frappe.get_roles(user)) & BYPASS_ROLES)


def _get_user_departments(user: str) -> list:
	"""
	Return list of active CRM Department names the user belongs to.
	Result is cached on frappe.local for the duration of the request.
	"""
	cache_key = f"{_CACHE_PREFIX}{user}"

	if hasattr(frappe.local, cache_key):
		return getattr(frappe.local, cache_key)

	rows = frappe.get_all(
		"CRM Department User",
		filters={"user": user, "parenttype": "CRM Department"},
		fields=["parent"],
		ignore_permissions=True,
	)

	# Keep only active departments
	active = [
		r.parent
		for r in rows
		if frappe.db.get_value("CRM Department", r.parent, "is_active")
	]

	setattr(frappe.local, cache_key, active)
	return active


# ─── Hook: permission_query_conditions ────────────────────────────────────────

def get_permission_query_conditions(user: str = None) -> str:
	"""
	Injected for all 7 CRM doctypes.
	Returns a SQL WHERE fragment appended to every list/API query.

	Frappe calls this as:  get_permission_query_conditions(user)
	Return "" to apply no extra filter (admin).
	Return "1=0" to return no records (no department assigned).
	"""
	user = user or frappe.session.user

	if _is_bypass_user(user):
		return ""

	departments = _get_user_departments(user)

	if not departments:
		return "1=0"

	# Build safe IN clause
	escaped = ", ".join(frappe.db.escape(d) for d in departments)
	return f"`department` IN ({escaped})"


# ─── Hook: has_permission ─────────────────────────────────────────────────────

def has_permission(doc, ptype: str = "read", user: str = None) -> bool:
	"""
	Record-level access check. Called when a user opens a specific document.
	Returning False causes Frappe to raise PermissionError (shown as Not Permitted).
	The frontend guard redirects silently before this is ever triggered in normal use.
	"""
	user = user or frappe.session.user

	if _is_bypass_user(user):
		return True

	departments = _get_user_departments(user)

	if not departments:
		return False

	record_dept = doc.get("department")

	# Legacy records with no department set — allow access
	if not record_dept:
		return True

	return record_dept in departments


# ─── Hook: doc_events before_insert ───────────────────────────────────────────

def set_department_on_insert(doc, method: str = None) -> None:
	"""
	Automatically sets the department field on new records.
	Uses the creating user's first active department as the default.
	Skipped if the field is already set or if the user is a bypass user.
	"""
	if doc.get("department"):
		return  # Already set manually — respect it

	user = frappe.session.user

	if _is_bypass_user(user):
		return  # Admins set department manually

	departments = _get_user_departments(user)

	if departments:
		doc.department = departments[0]
