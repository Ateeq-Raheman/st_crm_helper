"""
st_crm_helper.api.dashboard
============================
Department-aware overrides for crm.api.dashboard.get_dashboard and get_chart.

Filtering strategy:
  - Filter by `department` field on the record itself (not by lead_owner)
  - This means a lead belongs to a dept regardless of who owns it
  - Bypass users (System Manager/Admin) can pick any dept or see all
  - Regular users are always locked to their own department(s)
"""

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count

from st_crm_helper.overrides.department_filter import (
    _get_user_departments,
    _is_bypass_user,
)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _is_dept_manager(user: str) -> bool:
    """
    Returns True if the user is marked as Is Manager in ANY active CRM Department.
    Managers can view all departments on the dashboard (like bypass users)
    but are still restricted on list/form views to their own department.
    """
    rows = frappe.get_all(
        "CRM Department User",
        filters={"user": user, "is_manager": 1, "parenttype": "CRM Department"},
        fields=["parent"],
        ignore_permissions=True,
    )
    # Verify the parent dept is active
    for row in rows:
        if frappe.db.get_value("CRM Department", row.parent, "is_active"):
            return True
    return False


def _resolve_department(requested_dept: str | None) -> str | None:
    """
    Resolve which department to filter by for the current user.

    Returns:
      "__all__"  → no dept filter (admin/manager seeing everything)
      "__none__" → user has no dept, show nothing
      "DeptName" → filter to this specific department
    """
    user = frappe.session.user

    # System Manager / Administrator — full access
    if _is_bypass_user(user):
        return requested_dept or "__all__"

    # Department manager — can pick any dept on dashboard
    if _is_dept_manager(user):
        return requested_dept or "__all__"

    user_depts = _get_user_departments(user)
    if not user_depts:
        return "__none__"

    # If user requested a specific dept they belong to, honour it
    if requested_dept and requested_dept in user_depts:
        return requested_dept

    # Default: first dept
    return user_depts[0]


# ─── Whitelisted context API for the frontend widget ─────────────────────────

@frappe.whitelist()
def get_dashboard_context() -> dict:
    """
    Returns the department context for the dashboard JS widget.
    """
    user = frappe.session.user
    is_bypass = _is_bypass_user(user)
    is_manager = _is_dept_manager(user)

    all_active = frappe.get_all(
        "CRM Department",
        filters={"is_active": 1},
        fields=["name", "department_name"],
        order_by="department_name asc",
        ignore_permissions=True,
    )

    # Bypass users and dept managers both get the full dept switcher
    if is_bypass or is_manager:
        return {
            "bypass": True,  # tells JS to show all-dept switcher
            "is_manager": is_manager and not is_bypass,
            "active_department": "__all__",
            "departments": [{"name": d.name, "label": d.department_name} for d in all_active],
        }

    user_depts = _get_user_departments(user)
    dept_details = [d for d in all_active if d.name in user_depts]

    return {
        "bypass": False,
        "is_manager": False,
        "active_department": user_depts[0] if user_depts else None,
        "departments": [{"name": d.name, "label": d.department_name} for d in dept_details],
    }


def _apply_dept_condition(query, DocTypeRef, resolved_dept: str):
    """
    Apply a department WHERE condition to a frappe QueryBuilder query.
    Returns the modified query.
    """
    if resolved_dept == "__all__":
        return query  # no filter
    return query.where(DocTypeRef.department == resolved_dept)


# ─── Override: get_dashboard ──────────────────────────────────────────────────

@frappe.whitelist()
def get_dashboard(
    from_date: str | None = None,
    to_date: str | None = None,
    user: str | None = None,
    department: str | None = None,
) -> list:
    """
    Department-aware replacement for crm.api.dashboard.get_dashboard.
    Passes department filter into each chart function.
    """
    import json
    import crm.api.dashboard as crm_dash
    from crm.fcrm.doctype.crm_dashboard.crm_dashboard import create_default_manager_dashboard

    resolved_dept = _resolve_department(department)

    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

    # For Sales User role, lock to themselves (original CRM behaviour)
    roles = frappe.get_roles(frappe.session.user)
    is_sales_manager = "Sales Manager" in roles or "System Manager" in roles
    is_sales_user = "Sales User" in roles and not is_sales_manager
    if is_sales_user:
        user = frappe.session.user

    db_dashboard = frappe.db.exists("CRM Dashboard", "Manager Dashboard")
    if not db_dashboard:
        layout = json.loads(create_default_manager_dashboard())
        frappe.db.commit()
    else:
        layout = json.loads(
            frappe.db.get_value("CRM Dashboard", "Manager Dashboard", "layout") or "[]"
        )

    for item in layout:
        method_name = f"get_{item['name']}"
        # Try our dept-aware version first, then fall back to crm's version
        if hasattr(frappe.get_attr("st_crm_helper.api.dashboard"), method_name):
            method = getattr(frappe.get_attr("st_crm_helper.api.dashboard"), method_name)
            item["data"] = method(from_date, to_date, user, resolved_dept)
        elif hasattr(frappe.get_attr("crm.api.dashboard"), method_name):
            method = getattr(frappe.get_attr("crm.api.dashboard"), method_name)
            item["data"] = method(from_date, to_date, user)
        else:
            item["data"] = None

    return layout


@frappe.whitelist()
def get_chart(
    name: str,
    type: str,
    from_date: str | None = None,
    to_date: str | None = None,
    user: str | None = None,
    department: str | None = None,
) -> dict:
    """
    Department-aware replacement for crm.api.dashboard.get_chart.
    """
    resolved_dept = _resolve_department(department)

    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(from_date or frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(to_date or frappe.utils.nowdate())

    roles = frappe.get_roles(frappe.session.user)
    is_sales_manager = "Sales Manager" in roles or "System Manager" in roles
    is_sales_user = "Sales User" in roles and not is_sales_manager
    if is_sales_user:
        user = frappe.session.user

    method_name = f"get_{name}"
    if hasattr(frappe.get_attr("st_crm_helper.api.dashboard"), method_name):
        method = getattr(frappe.get_attr("st_crm_helper.api.dashboard"), method_name)
        return method(from_date, to_date, user, resolved_dept)
    elif hasattr(frappe.get_attr("crm.api.dashboard"), method_name):
        method = getattr(frappe.get_attr("crm.api.dashboard"), method_name)
        return method(from_date, to_date, user)

    return {"error": _("Invalid chart name")}


# ─── Department-aware chart functions ─────────────────────────────────────────
# Each mirrors the original in crm.api.dashboard but adds a dept WHERE clause.

from frappe.query_builder import Case
from frappe.query_builder.functions import Avg, Coalesce, Count, Date, DateFormat, IfNull, Sum
from pypika.functions import Function

class TimestampDiff(Function):
    def __init__(self, unit, start, end, **kwargs):
        super().__init__("TIMESTAMPDIFF", unit, start, end, **kwargs)


def get_total_leads(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Lead = DocType("CRM Lead")
    current_cond = (Lead.creation >= from_date) & (Lead.creation < to_date_plus_one)
    prev_cond = (Lead.creation >= prev_from_date) & (Lead.creation < from_date)
    if user:
        current_cond = current_cond & (Lead.lead_owner == user)
        prev_cond = prev_cond & (Lead.lead_owner == user)

    query = frappe.qb.from_(Lead).select(
        Count(Case().when(current_cond, Lead.name).else_(None)).as_("current"),
        Count(Case().when(prev_cond, Lead.name).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Lead.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    delta = (current - prev) / prev * 100 if prev else 0
    return {"title": _("Total leads"), "tooltip": _("Total number of leads"), "value": current, "delta": delta, "deltaSuffix": "%"}


def get_ongoing_deals(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    current_cond = (Deal.creation >= from_date) & (Deal.creation < to_date_plus_one) & (Status.type.notin(["Won", "Lost"]))
    prev_cond = (Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type.notin(["Won", "Lost"]))
    if user:
        current_cond = current_cond & (Deal.deal_owner == user)
        prev_cond = prev_cond & (Deal.deal_owner == user)

    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Count(Case().when(current_cond, Deal.name).else_(None)).as_("current"),
        Count(Case().when(prev_cond, Deal.name).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    delta = (current - prev) / prev * 100 if prev else 0
    return {"title": _("Ongoing deals"), "tooltip": _("Total number of non won/lost deals"), "value": current, "delta": delta, "deltaSuffix": "%"}


def get_won_deals(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one) & (Status.type == "Won")
    prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date) & (Status.type == "Won")
    if user:
        current_cond = current_cond & (Deal.deal_owner == user)
        prev_cond = prev_cond & (Deal.deal_owner == user)

    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Count(Case().when(current_cond, Deal.name).else_(None)).as_("current"),
        Count(Case().when(prev_cond, Deal.name).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    delta = (current - prev) / prev * 100 if prev else 0
    return {"title": _("Won deals"), "tooltip": _("Total number of won deals based on its closure date"), "value": current, "delta": delta, "deltaSuffix": "%"}


def get_average_won_deal_value(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one) & (Status.type == "Won")
    prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date) & (Status.type == "Won")
    if user:
        current_cond = current_cond & (Deal.deal_owner == user)
        prev_cond = prev_cond & (Deal.deal_owner == user)

    deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)
    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current"),
        Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    return {"title": _("Avg. won deal value"), "tooltip": _("Average deal value of won deals"), "value": current, "delta": current - prev, "prefix": _get_currency()}


def get_average_deal_value(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    current_cond = (Deal.creation >= from_date) & (Deal.creation < to_date_plus_one) & (Status.type != "Lost")
    prev_cond = (Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type != "Lost")
    if user:
        current_cond = current_cond & (Deal.deal_owner == user)
        prev_cond = prev_cond & (Deal.deal_owner == user)

    deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)
    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current"),
        Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    return {"title": _("Avg. deal value"), "tooltip": _("Average deal value of ongoing & won deals"), "value": current, "delta": current - prev, "prefix": _get_currency(), "deltaSuffix": "%"}


def get_average_ongoing_deal_value(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    current_cond = (Deal.creation >= from_date) & (Deal.creation < to_date_plus_one) & (Status.type.notin(["Won", "Lost"]))
    prev_cond = (Deal.creation >= prev_from_date) & (Deal.creation < from_date) & (Status.type.notin(["Won", "Lost"]))
    if user:
        current_cond = current_cond & (Deal.deal_owner == user)
        prev_cond = prev_cond & (Deal.deal_owner == user)

    deal_value_expr = Deal.deal_value * IfNull(Deal.exchange_rate, 1)
    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Avg(Case().when(current_cond, deal_value_expr).else_(None)).as_("current"),
        Avg(Case().when(prev_cond, deal_value_expr).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    return {"title": _("Avg. ongoing deal value"), "tooltip": _("Average deal value of non won/lost deals"), "value": current, "delta": current - prev, "prefix": _get_currency()}


def get_average_time_to_close_a_lead(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    Lead = DocType("CRM Lead")

    base_cond = (Deal.closed_date.isnotnull()) & (Status.type == "Won")
    if user:
        base_cond = base_cond & (Deal.deal_owner == user)
    current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one)
    prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date)
    time_diff = TimestampDiff(frappe.qb.terms.LiteralValue("DAY"), Coalesce(Lead.creation, Deal.creation), Deal.closed_date)

    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).left_join(Lead).on(Deal.lead == Lead.name).where(base_cond).select(
        Avg(Case().when(current_cond, time_diff).else_(None)).as_("current"),
        Avg(Case().when(prev_cond, time_diff).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    return {"title": _("Avg. time to close a lead"), "tooltip": _("Average time from lead creation to deal closure"), "value": current, "suffix": " days", "delta": current - prev, "deltaSuffix": " days", "negativeIsBetter": True}


def get_average_time_to_close_a_deal(from_date=None, to_date=None, user=None, department="__all__"):
    diff = frappe.utils.date_diff(to_date, from_date) or 1
    prev_from_date = frappe.utils.add_days(from_date, -diff)
    to_date_plus_one = frappe.utils.add_days(to_date, 1)

    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")
    Lead = DocType("CRM Lead")

    base_cond = (Deal.closed_date.isnotnull()) & (Status.type == "Won")
    if user:
        base_cond = base_cond & (Deal.deal_owner == user)
    current_cond = (Deal.closed_date >= from_date) & (Deal.closed_date < to_date_plus_one)
    prev_cond = (Deal.closed_date >= prev_from_date) & (Deal.closed_date < from_date)
    time_diff = TimestampDiff(frappe.qb.terms.LiteralValue("DAY"), Deal.creation, Deal.closed_date)

    query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).left_join(Lead).on(Deal.lead == Lead.name).where(base_cond).select(
        Avg(Case().when(current_cond, time_diff).else_(None)).as_("current"),
        Avg(Case().when(prev_cond, time_diff).else_(None)).as_("prev"),
    )
    if department != "__all__":
        query = query.where(Deal.department == department)

    result = query.run(as_dict=True)
    current = result[0].current or 0
    prev = result[0].prev or 0
    return {"title": _("Avg. time to close a deal"), "tooltip": _("Average time from deal creation to closure"), "value": current, "suffix": " days", "delta": current - prev, "deltaSuffix": " days", "negativeIsBetter": True}


def get_sales_trend(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    Lead = DocType("CRM Lead")
    Deal = DocType("CRM Deal")
    Status = DocType("CRM Deal Status")

    leads_query = frappe.qb.from_(Lead).select(
        Date(Lead.creation).as_("date"),
        Count("*").as_("leads"),
        frappe.qb.terms.ValueWrapper(0).as_("deals"),
        frappe.qb.terms.ValueWrapper(0).as_("won_deals"),
    ).where(Date(Lead.creation).between(from_date, to_date))
    if user:
        leads_query = leads_query.where(Lead.lead_owner == user)
    if department != "__all__":
        leads_query = leads_query.where(Lead.department == department)
    leads_query = leads_query.groupby(Date(Lead.creation))

    deals_query = frappe.qb.from_(Deal).join(Status).on(Deal.status == Status.name).select(
        Date(Deal.creation).as_("date"),
        frappe.qb.terms.ValueWrapper(0).as_("leads"),
        Count("*").as_("deals"),
        Sum(Case().when(Status.type == "Won", 1).else_(0)).as_("won_deals"),
    ).where(Date(Deal.creation).between(from_date, to_date))
    if user:
        deals_query = deals_query.where(Deal.deal_owner == user)
    if department != "__all__":
        deals_query = deals_query.where(Deal.department == department)
    deals_query = deals_query.groupby(Date(Deal.creation))

    union_query = leads_query.union_all(deals_query)
    daily = frappe.qb.from_(union_query).select(
        DateFormat(union_query.date, "%Y-%m-%d").as_("date"),
        Sum(union_query.leads).as_("leads"),
        Sum(union_query.deals).as_("deals"),
        Sum(union_query.won_deals).as_("won_deals"),
    ).groupby(union_query.date).orderby(union_query.date)

    result = daily.run(as_dict=True)
    sales_trend = [{"date": frappe.utils.get_datetime(r.date).strftime("%Y-%m-%d"), "leads": r.leads or 0, "deals": r.deals or 0, "won_deals": r.won_deals or 0} for r in result]

    return {"data": sales_trend, "title": _("Sales trend"), "subtitle": _("Daily performance of leads, deals, and wins"),
            "xAxis": {"title": _("Date"), "key": "date", "type": "time", "timeGrain": "day"},
            "yAxis": {"title": _("Count")},
            "series": [{"name": "leads", "type": "line", "showDataPoints": True}, {"name": "deals", "type": "line", "showDataPoints": True}, {"name": "won_deals", "type": "line", "showDataPoints": True}]}


def get_forecasted_revenue(from_date=None, to_date=None, user=None, department="__all__"):
    CRMDeal = DocType("CRM Deal")
    CRMDealStatus = DocType("CRM Deal Status")
    twelve_months_ago = frappe.utils.add_months(frappe.utils.nowdate(), -12)

    forecasted_value = Case().when(CRMDealStatus.type == "Lost", CRMDeal.expected_deal_value * IfNull(CRMDeal.exchange_rate, 1)).else_(CRMDeal.expected_deal_value * IfNull(CRMDeal.probability, 0) / 100 * IfNull(CRMDeal.exchange_rate, 1))
    actual_value = Case().when(CRMDealStatus.type == "Won", CRMDeal.deal_value * IfNull(CRMDeal.exchange_rate, 1)).else_(0)

    query = frappe.qb.from_(CRMDeal).join(CRMDealStatus).on(CRMDeal.status == CRMDealStatus.name).select(
        DateFormat(CRMDeal.expected_closure_date, "%Y-%m").as_("month"),
        Sum(forecasted_value).as_("forecasted"),
        Sum(actual_value).as_("actual"),
    ).where(CRMDeal.expected_closure_date >= twelve_months_ago).groupby(DateFormat(CRMDeal.expected_closure_date, "%Y-%m")).orderby(DateFormat(CRMDeal.expected_closure_date, "%Y-%m"))

    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    for row in result:
        row["month"] = frappe.utils.get_datetime(row["month"]).strftime("%Y-%m-01")
        row["forecasted"] = row["forecasted"] or ""
        row["actual"] = row["actual"] or ""

    return {"data": result or [], "title": _("Forecasted revenue"), "subtitle": _("Projected vs actual revenue based on deal probability"),
            "xAxis": {"title": _("Month"), "key": "month", "type": "time", "timeGrain": "month"},
            "yAxis": {"title": _("Revenue") + f" ({_get_currency()})"},
            "series": [{"name": "forecasted", "type": "line", "showDataPoints": True}, {"name": "actual", "type": "line", "showDataPoints": True}]}


def get_funnel_conversion(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMLead = DocType("CRM Lead")
    query = frappe.qb.from_(CRMLead).select(Count("*").as_("count")).where(Date(CRMLead.creation).between(from_date, to_date))
    if user:
        query = query.where(CRMLead.lead_owner == user)
    if department != "__all__":
        query = query.where(CRMLead.department == department)

    total_leads = query.run(as_dict=True)
    result = [{"stage": "Leads", "count": total_leads[0].count if total_leads else 0}]

    # Deal stage counts — filter by department on the deal
    CRMStatusChangeLog = DocType("CRM Status Change Log")
    CRMDeal = DocType("CRM Deal")
    CurrentStatus = DocType("CRM Deal Status").as_("s")
    TargetStatus = DocType("CRM Deal Status").as_("st")

    stage_query = frappe.qb.from_(CRMStatusChangeLog).join(CRMDeal).on(CRMStatusChangeLog.parent == CRMDeal.name).join(CurrentStatus).on(CRMDeal.status == CurrentStatus.name).join(TargetStatus).on(CRMStatusChangeLog.to == TargetStatus.name).select(
        CRMStatusChangeLog.to.as_("stage"), Count("*").as_("count")
    ).where(
        (CRMStatusChangeLog.to.isnotnull()) & (CRMStatusChangeLog.to != "") & (CurrentStatus.type != "Lost") & (Date(CRMDeal.creation).between(from_date, to_date))
    ).groupby(CRMStatusChangeLog.to, TargetStatus.position).orderby(TargetStatus.position)

    if user:
        stage_query = stage_query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        stage_query = stage_query.where(CRMDeal.department == department)

    result += stage_query.run(as_dict=True) or []

    return {"data": result, "title": _("Funnel conversion"), "subtitle": _("Lead to deal conversion pipeline"),
            "xAxis": {"title": _("Stage"), "key": "stage", "type": "category"},
            "yAxis": {"title": _("Count")}, "swapXY": True,
            "series": [{"name": "count", "type": "bar", "echartOptions": {"colorBy": "data"}}]}


def get_deals_by_stage_donut(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    CRMDealStatus = DocType("CRM Deal Status")
    query = frappe.qb.from_(CRMDeal).join(CRMDealStatus).on(CRMDeal.status == CRMDealStatus.name).select(
        CRMDeal.status.as_("stage"), Count("*").as_("count"), CRMDealStatus.type.as_("status_type")
    ).where(Date(CRMDeal.creation).between(from_date, to_date)).groupby(CRMDeal.status).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Deals by stage"), "subtitle": _("Current pipeline distribution"), "categoryColumn": "stage", "valueColumn": "count"}


def get_deals_by_stage_axis(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    CRMDealStatus = DocType("CRM Deal Status")
    query = frappe.qb.from_(CRMDeal).join(CRMDealStatus).on(CRMDeal.status == CRMDealStatus.name).select(
        CRMDeal.status.as_("stage"), Count("*").as_("count"), CRMDealStatus.type.as_("status_type")
    ).where((Date(CRMDeal.creation).between(from_date, to_date)) & (CRMDealStatus.type.notin(["Lost"]))).groupby(CRMDeal.status).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Deals by ongoing & won stage"),
            "xAxis": {"title": _("Stage"), "key": "stage", "type": "category"}, "yAxis": {"title": _("Count")},
            "series": [{"name": "count", "type": "bar"}]}


def get_lost_deal_reasons(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    CRMDealStatus = DocType("CRM Deal Status")
    query = frappe.qb.from_(CRMDeal).join(CRMDealStatus).on(CRMDeal.status == CRMDealStatus.name).select(
        CRMDeal.lost_reason.as_("reason"), Count("*").as_("count")
    ).where((Date(CRMDeal.creation).between(from_date, to_date)) & (CRMDealStatus.type == "Lost")).groupby(CRMDeal.lost_reason).having(
        (CRMDeal.lost_reason.isnotnull()) & (CRMDeal.lost_reason != "")
    ).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Lost deal reasons"), "subtitle": _("Common reasons for losing deals"),
            "xAxis": {"title": _("Reason"), "key": "reason", "type": "category"}, "yAxis": {"title": _("Count")},
            "series": [{"name": "count", "type": "bar"}]}


def get_leads_by_source(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMLead = DocType("CRM Lead")
    query = frappe.qb.from_(CRMLead).select(
        IfNull(CRMLead.source, "Empty").as_("source"), Count("*").as_("count")
    ).where(Date(CRMLead.creation).between(from_date, to_date)).groupby(CRMLead.source).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMLead.lead_owner == user)
    if department != "__all__":
        query = query.where(CRMLead.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Leads by source"), "subtitle": _("Lead generation channel analysis"), "categoryColumn": "source", "valueColumn": "count"}


def get_deals_by_source(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    query = frappe.qb.from_(CRMDeal).select(
        IfNull(CRMDeal.source, "Empty").as_("source"), Count("*").as_("count")
    ).where(Date(CRMDeal.creation).between(from_date, to_date)).groupby(CRMDeal.source).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Deals by source"), "subtitle": _("Deal generation channel analysis"), "categoryColumn": "source", "valueColumn": "count"}


def get_deals_by_territory(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    query = frappe.qb.from_(CRMDeal).select(
        IfNull(CRMDeal.territory, "Empty").as_("territory"), Count("*").as_("deals"),
        Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)).as_("value"),
    ).where(Date(CRMDeal.creation).between(from_date, to_date)).groupby(CRMDeal.territory).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Deals by territory"), "subtitle": _("Geographic distribution of deals and revenue"),
            "xAxis": {"title": _("Territory"), "key": "territory", "type": "category"}, "yAxis": {"title": _("Number of deals")},
            "y2Axis": {"title": _("Deal value") + f" ({_get_currency()})"},
            "series": [{"name": "deals", "type": "bar"}, {"name": "value", "type": "line", "showDataPoints": True, "axis": "y2"}]}


def get_deals_by_salesperson(from_date=None, to_date=None, user=None, department="__all__"):
    if not from_date or not to_date:
        from_date = frappe.utils.get_first_day(frappe.utils.nowdate())
        to_date = frappe.utils.get_last_day(frappe.utils.nowdate())

    CRMDeal = DocType("CRM Deal")
    User = DocType("User")
    query = frappe.qb.from_(CRMDeal).left_join(User).on(User.name == CRMDeal.deal_owner).select(
        IfNull(User.full_name, CRMDeal.deal_owner).as_("salesperson"), Count("*").as_("deals"),
        Sum(Coalesce(CRMDeal.deal_value, 0) * IfNull(CRMDeal.exchange_rate, 1)).as_("value"),
    ).where(Date(CRMDeal.creation).between(from_date, to_date)).groupby(CRMDeal.deal_owner).orderby(Count("*"), order=frappe.qb.desc)
    if user:
        query = query.where(CRMDeal.deal_owner == user)
    if department != "__all__":
        query = query.where(CRMDeal.department == department)

    result = query.run(as_dict=True)
    return {"data": result or [], "title": _("Deals by salesperson"), "subtitle": _("Number of deals and total value per salesperson"),
            "xAxis": {"title": _("Salesperson"), "key": "salesperson", "type": "category"}, "yAxis": {"title": _("Number of deals")},
            "y2Axis": {"title": _("Deal value") + f" ({_get_currency()})"},
            "series": [{"name": "deals", "type": "bar"}, {"name": "value", "type": "line", "showDataPoints": True, "axis": "y2"}]}


def _get_currency():
    base = frappe.db.get_single_value("FCRM Settings", "currency") or "USD"
    return frappe.db.get_value("Currency", base, "symbol") or ""