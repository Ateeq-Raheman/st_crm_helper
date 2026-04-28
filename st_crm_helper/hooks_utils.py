import frappe

def inject_scripts(context):
    context.setdefault("head_html", "")
    context["head_html"] += """
<script src="/assets/st_crm_helper/js/department_filter.js"></script>
<script src="/assets/st_crm_helper/js/crm_dashboard_dept.js"></script>
"""
    return context
