"""
st_crm_helper.api.department
==============================
Whitelisted API methods consumed by the frontend department switcher widget
and the form guard JS.
"""

import frappe
from frappe import _

from st_crm_helper.overrides.department_filter import (
	_get_user_departments,
	_is_bypass_user,
)


@frappe.whitelist()
def get_my_departments() -> dict:
	"""
	Returns the current user's department context.

	Response:
	{
	    "bypass": true | false,
	    "departments": ["Sales", "Support"],       # user's own depts
	    "all_departments": ["Sales", "Support", …] # all active depts (for bypass users)
	}
	"""
	user = frappe.session.user
	bypass = _is_bypass_user(user)

	all_active = frappe.get_all(
		"CRM Department",
		filters={"is_active": 1},
		fields=["name"],
		order_by="department_name asc",
		ignore_permissions=True,
	)
	all_dept_names = [d.name for d in all_active]

	if bypass:
		return {
			"bypass": True,
			"departments": all_dept_names,
			"all_departments": all_dept_names,
		}

	user_depts = _get_user_departments(user)
	return {
		"bypass": False,
		"departments": user_depts,
		"all_departments": user_depts,
	}


@frappe.whitelist()
def get_all_departments() -> list:
	"""
	Returns all active CRM Departments.
	Used to populate the department field dropdown on records.
	"""
	return frappe.get_all(
		"CRM Department",
		filters={"is_active": 1},
		fields=["name as value", "department_name as label"],
		order_by="department_name asc",
		ignore_permissions=True,
	)


@frappe.whitelist()
def get_department_members(department: str) -> list:
	"""Returns users assigned to a specific department. System Manager only."""
	if not frappe.has_permission("CRM Department", "read", department):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	return frappe.get_all(
		"CRM Department User",
		filters={"parent": department, "parenttype": "CRM Department"},
		fields=["user", "full_name", "is_manager"],
		ignore_permissions=True,
	)
