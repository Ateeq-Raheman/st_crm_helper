# ST CRM Helper

**Department-based access control for Frappe CRM**
*Built by StandardTouch e-Solutions*

---

## Overview

`st_crm_helper` is a Frappe v15 custom app that adds department-level access control
across all Frappe CRM records — without modifying any core CRM files.

### What it does

| Feature | Detail |
|---|---|
| Department field on all CRM records | Leads, Deals, Contacts, Organizations, Tasks, Notes, Call Logs |
| Auto-set on creation | New records inherit the creating user's first department |
| Silently hidden records | Records outside a user's dept never appear in lists |
| Direct URL guard | Frontend redirect + server `has_permission` block |
| Multi-dept switcher | Dropdown widget in list headers for users in 2+ depts |
| Admin bypass | System Manager / Administrator sees everything unfiltered |
| Any user can reassign dept | No restriction on changing a record's department field |
| Admin-managed memberships | Admin assigns users to departments via CRM Department doctype |

---

## Installation

```bash
# From your frappe-bench directory
bench get-app https://github.com/standardtouch/st_crm_helper

# Install on your site
bench --site your-site.localhost install-app st_crm_helper

# Run migrations (also imports fixtures / custom fields)
bench --site your-site.localhost migrate
```

> **Requires:** Frappe v15 + Frappe CRM (`crm`) already installed.

---

## Quick Setup

### 1. Create a Department

- Go to **Frappe Desk → CRM Department → New**
- Enter department name (e.g. `Sales`, `Support`, `Marketing`)
- Toggle **Is Active** on
- Add users in the **Department Members** table
- Save

A user can appear in multiple departments — just add them to each one.

### 2. Done

Users logging into Frappe CRM will now only see records tagged to their department(s).

- Single-dept users → filter applied silently, no widget shown
- Multi-dept users → see a **Department** dropdown in list headers
- System Manager / Admin → see everything, widget shows all departments

---

## Architecture

### Two-Layer Enforcement

#### Layer 1 — Python (Server-side)

`overrides/department_filter.py` provides three hook functions registered in `hooks.py`:

| Hook | Function | Effect |
|---|---|---|
| `permission_query_conditions` | `get_permission_query_conditions` | Injects `WHERE department IN (...)` on every list/API query |
| `has_permission` | `has_permission` | Blocks direct document access if dept doesn't match |
| `doc_events.before_insert` | `set_department_on_insert` | Auto-sets dept on new records |

#### Layer 2 — JavaScript (Frontend)

| File | Loaded via | Purpose |
|---|---|---|
| `public/js/department_filter.js` | `app_include_js` | Pre-fetches dept context on desk load, stores in `window.stCrmHelper` |
| `public/js/crm_list_filter.js` | `doctype_list_js` | Applies filter + renders dept switcher widget in list views |
| `public/js/crm_form_guard.js` | `doctype_js` | Redirects silently if form's dept is outside user's access |

### DocTypes

| DocType | Module | Purpose |
|---|---|---|
| `CRM Department` | CRM Department | Department name, active flag, members child table |
| `CRM Department User` | CRM Department | Child table — user ↔ department mapping |

### Custom Fields (via Fixtures)

`department` (Link → CRM Department) added to all 7 CRM doctypes:
`CRM Lead`, `CRM Deal`, `CRM Contacts`, `CRM Organization`, `CRM Task`, `FCRM Note`, `CRM Call Log`

---

## Behaviour Reference

| Scenario | Behaviour |
|---|---|
| User in 1 department | Filter silently applied, no widget shown |
| User in 2+ departments | Dept switcher widget shown in list header |
| User in no department | Sees nothing (`1=0` filter applied) |
| System Manager / Admin | No filter — full access, all-dept dropdown shown |
| Opening a record outside dept | Frontend redirect + server blocks access |
| Creating a new record | Dept auto-set to creator's first active dept |
| Reassigning dept on a record | Any user can change dept to any department |
| Admin creating a record | Dept not auto-set — admin sets manually |

---

## File Structure

```
st_crm_helper/
├── st_crm_helper/
│   ├── __init__.py
│   ├── hooks.py
│   ├── modules.txt
│   ├── patches.txt
│   ├── install.py
│   ├── config/
│   │   ├── __init__.py
│   │   └── desktop.py
│   ├── public/
│   │   └── js/
│   │       ├── department_filter.js    ← global desk JS (app_include_js)
│   │       ├── crm_list_filter.js      ← list view filter + widget
│   │       └── crm_form_guard.js       ← form-level access guard
│   ├── templates/
│   ├── www/
│   ├── st_crm_helper/                  ← default module
│   │   └── __init__.py
│   ├── crm_department/                 ← CRM Department module
│   │   ├── __init__.py
│   │   └── doctype/
│   │       ├── crm_department/
│   │       │   ├── crm_department.json
│   │       │   └── crm_department.py
│   │       └── crm_department_user/
│   │           ├── crm_department_user.json
│   │           └── crm_department_user.py
│   ├── api/
│   │   └── department.py
│   ├── overrides/
│   │   └── department_filter.py
│   └── fixtures/
│       └── custom_field.json
├── pyproject.toml
├── MANIFEST.in
├── license.txt
└── README.md
```

---

## License

MIT — StandardTouch e-Solutions
