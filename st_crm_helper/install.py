import frappe


def after_install():
	"""Run once when app is installed on a site."""
	_create_default_department()


def after_migrate():
	"""Run after every bench migrate — safe to run repeatedly."""
	pass


def _create_default_department():
	if not frappe.db.exists("CRM Department", "General"):
		doc = frappe.new_doc("CRM Department")
		doc.department_name = "General"
		doc.is_active = 1
		doc.insert(ignore_permissions=True)
		frappe.db.commit()
