import frappe

def get_context(context):
    # Inject our JS files into the CRM SPA page
    context.head_html = context.get("head_html", "") + """
<script src="/assets/st_crm_helper/js/department_filter.js"></script>
<script src="/assets/st_crm_helper/js/crm_dashboard_dept.js"></script>
"""
    return context
