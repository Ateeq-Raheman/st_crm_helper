import frappe
from frappe import _
from frappe.model.document import Document


class CRMDepartment(Document):
	# begin: auto-generated types
	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF
		from st_crm_helper.crm_department.doctype.crm_department_user.crm_department_user import (
			CRMDepartmentUser,
		)

		department_name: DF.Data
		is_active: DF.Check
		users: DF.Table[CRMDepartmentUser]
	# end: auto-generated types

	def validate(self):
		self._validate_no_duplicate_users()

	def on_update(self):
		self._clear_user_dept_cache()

	def on_trash(self):
		self._clear_user_dept_cache()

	def _validate_no_duplicate_users(self):
		seen = set()
		for row in self.users:
			if row.user in seen:
				frappe.throw(
					_("User {0} is listed more than once in this department.").format(row.user)
				)
			seen.add(row.user)

	def _clear_user_dept_cache(self):
		"""
		Bust the per-request local cache for every user in this department.
		Called on save/delete so the next request always gets fresh data.
		"""
		cache_prefix = "st_crm_user_depts_"
		for row in self.users:
			attr = f"{cache_prefix}{row.user}"
			if hasattr(frappe.local, attr):
				delattr(frappe.local, attr)
