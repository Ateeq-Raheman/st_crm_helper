console.log("✅ [ST CRM] crm_dashboard_dept.js LOADED");

(function () {
	"use strict";

	const DASHBOARD_METHODS = ["crm.api.dashboard.get_dashboard","crm.api.dashboard.get_chart"];
	const ST_DASH_STORAGE_KEY = "st_crm_dashboard_dept";

	window.stCrmDashboard = window.stCrmDashboard || {};
	stCrmDashboard.context = null;
	stCrmDashboard.selectedDept = null;
	stCrmDashboard._fetchPatched = false;
	stCrmDashboard._observing = false;

	function getCsrfToken() {
		if (window.csrf_token) return window.csrf_token;
		const match = document.cookie.match(/csrftoken=([^;]+)/);
		return match ? match[1] : "unauthorized";
	}

	stCrmDashboard.fetchContext = function () {
		if (stCrmDashboard.context) return Promise.resolve(stCrmDashboard.context);
		return fetch("/api/method/st_crm_helper.api.dashboard.get_dashboard_context", {
			method: "POST",
			headers: { "Content-Type": "application/json", "X-Frappe-CSRF-Token": getCsrfToken() },
			body: JSON.stringify({}),
		})
		.then(function(r){ return r.json(); })
		.then(function(data) {
			stCrmDashboard.context = data.message || {};
			var stored = localStorage.getItem(ST_DASH_STORAGE_KEY);
			var names = (stCrmDashboard.context.departments || []).map(function(d){ return d.name; });
			var valid = stored === "__all__" || names.indexOf(stored) !== -1;
			stCrmDashboard.selectedDept = valid ? stored : (stCrmDashboard.context.active_department || "__all__");
			console.log("[ST CRM] context loaded:", JSON.stringify(stCrmDashboard.context));
			return stCrmDashboard.context;
		})
		.catch(function(err) {
			console.error("[ST CRM] Failed to fetch context", err);
			stCrmDashboard.context = { bypass: false, departments: [] };
			stCrmDashboard.selectedDept = "__all__";
			return stCrmDashboard.context;
		});
	};

	stCrmDashboard.setDept = function(dept) {
		stCrmDashboard.selectedDept = dept;
		localStorage.setItem(ST_DASH_STORAGE_KEY, dept);
	};

	stCrmDashboard.getActiveDept = function() {
		return stCrmDashboard.selectedDept || "__all__";
	};

	stCrmDashboard.patchFetch = function() {
		if (stCrmDashboard._fetchPatched) return;
		stCrmDashboard._fetchPatched = true;
		var _orig = window.fetch.bind(window);
		window.fetch = function(input, init) {
			var url = typeof input === "string" ? input : (input && input.url) || "";
			var isDash = DASHBOARD_METHODS.some(function(m){ return url.indexOf(m.replace(/\./g, "/")) !== -1 || url.indexOf(m) !== -1; });
			if (isDash && init && init.body) {
				try {
					var dept = stCrmDashboard.getActiveDept();
					if (typeof init.body === "string") {
						var body = JSON.parse(init.body);
						body.department = dept;
						init = Object.assign({}, init, { body: JSON.stringify(body) });
						console.log("[ST CRM] injected dept:", dept);
					}
				} catch(e) { console.warn("[ST CRM] inject error", e); }
			}
			return _orig(input, init);
		};
		console.log("[ST CRM] fetch patched");
	};

	stCrmDashboard.injectSwitcher = function() {
		if (document.querySelector(".st-crm-dash-switcher")) return;
		if (window.location.href.indexOf("/crm/dashboard") === -1) return;
		var ctx = stCrmDashboard.context;
		if (!ctx) return;
		var showWidget = ctx.bypass || (ctx.departments && ctx.departments.length > 1);
		console.log("[ST CRM] injectSwitcher — showWidget:", showWidget, "bypass:", ctx.bypass, "depts:", ctx.departments ? ctx.departments.length : 0);
		if (!showWidget) return;

		var depts = ctx.departments || [];
		var current = stCrmDashboard.selectedDept || "__all__";
		var allOpt = '<option value="__all__"' + (current === "__all__" ? " selected" : "") + ">All Departments</option>";
		var deptOpts = depts.map(function(d){ return '<option value="' + d.name + '"' + (current === d.name ? " selected" : "") + ">" + d.name + "</option>"; }).join("");

		var widget = document.createElement("div");
		widget.className = "st-crm-dash-switcher";
		widget.style.cssText = "display:inline-flex;align-items:center;gap:6px;font-size:12px;margin-left:8px;";
		widget.innerHTML = '<span style="font-weight:600;">Dept:</span><select style="border:1.5px solid #ee1c29;border-radius:6px;padding:4px 10px;font-size:12px;background:#fff;cursor:pointer;outline:none;">' + allOpt + deptOpts + "</select>";
		widget.querySelector("select").addEventListener("change", function() {
			stCrmDashboard.setDept(this.value);
			window.location.reload();
		});

		var mounted = false;
		var buttons = document.querySelectorAll("button");
		for (var i = 0; i < buttons.length; i++) {
			if (buttons[i].textContent.indexOf("Last") !== -1) {
				var bar = buttons[i].closest("div");
				if (bar) { bar.appendChild(widget); mounted = true; break; }
			}
		}
		if (!mounted) {
			var headings = document.querySelectorAll("h1,h2,h3");
			for (var j = 0; j < headings.length; j++) {
				if (headings[j].textContent.trim() === "Dashboard") {
					headings[j].parentElement.insertBefore(widget, headings[j].nextSibling);
					mounted = true; break;
				}
			}
		}
		console.log("[ST CRM] switcher mounted:", mounted);
	};

	stCrmDashboard.startObserver = function() {
		if (stCrmDashboard._observing) return;
		stCrmDashboard._observing = true;

		var _origPush = history.pushState.bind(history);
		history.pushState = function() {
			_origPush.apply(history, arguments);
			setTimeout(function() {
				document.querySelectorAll(".st-crm-dash-switcher").forEach(function(el){ el.remove(); });
				if (window.location.href.indexOf("/crm/dashboard") !== -1) _tryInit();
			}, 100);
		};

		window.addEventListener("popstate", function() {
			document.querySelectorAll(".st-crm-dash-switcher").forEach(function(el){ el.remove(); });
			if (window.location.href.indexOf("/crm/dashboard") !== -1) _tryInit();
		});

		var observer = new MutationObserver(function() {
			if (window.location.href.indexOf("/crm/dashboard") !== -1 && !document.querySelector(".st-crm-dash-switcher") && stCrmDashboard.context) {
				stCrmDashboard.injectSwitcher();
			}
		});
		observer.observe(document.body, { childList: true, subtree: true });

		if (window.location.href.indexOf("/crm/dashboard") !== -1) _tryInit();
	};

	function _tryInit() {
		stCrmDashboard.fetchContext().then(function() {
			stCrmDashboard.patchFetch();
			var tries = 0;
			function retry() {
				stCrmDashboard.injectSwitcher();
				if (!document.querySelector(".st-crm-dash-switcher") && tries++ < 20) {
					setTimeout(retry, 300);
				}
			}
			retry();
		});
	}

	var storedDept = localStorage.getItem(ST_DASH_STORAGE_KEY);
	if (storedDept) stCrmDashboard.selectedDept = storedDept;
	stCrmDashboard.patchFetch();

	document.addEventListener("DOMContentLoaded", function() {
		stCrmDashboard.startObserver();
	});

})();
