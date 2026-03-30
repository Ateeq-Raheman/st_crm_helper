from frappe.model.document import Document


class CRMDepartmentUser(Document):
	# begin: auto-generated types
	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		full_name: DF.Data | None
		is_manager: DF.Check
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		user: DF.Link
	# end: auto-generated types

	pass
