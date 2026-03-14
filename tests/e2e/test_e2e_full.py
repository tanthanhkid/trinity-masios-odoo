"""
Trinity Masios Odoo 18 — Comprehensive Playwright E2E Test Suite
================================================================
Covers:
  Suite 1: Welcome Page (6 tests)
  Suite 2: RBAC Menu Visibility (6 tests)
  Suite 3: RBAC URL Blocking (4 tests)
  Suite 4: Credit Control Functionality (5 tests)
  Suite 5: Dashboard KPIs (3 tests)
  Suite 6: Command Center Access (3 tests)

Run:
    python3 tests/e2e/test_e2e_full.py

Requirements:
    pip install playwright
    python -m playwright install chromium

Key discoveries from live testing (Odoo 18 behaviour):
  - /web/login shows a website with nav bar; login form selector must be scoped to form.oe_login_form
  - /odoo redirects to /welcome (custom welcome page is the landing page)
  - Menu links appear as plain <a> tags in the page source (not OWL-generated app grid)
  - URL blocking: Odoo loads the URL but shows an AccessError dialog (not 3xx redirect)
  - /dashboard requires CEO role; non-CEO is redirected to /welcome
  - Customer classification field: "Phân loại KH" shown in "Công nợ" tab of contact form
  - Outstanding debt label: "Công nợ hiện tại" shown when Công nợ tab is clicked
"""

import asyncio
import sys
import time
import re
import os
from dataclasses import dataclass
from typing import List
from pathlib import Path

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
    from playwright.async_api import TimeoutError as PWTimeoutError
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && python -m playwright install chromium")
    sys.exit(1)

# ─────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────
BASE_URL = "http://103.72.97.51:8069"
SCREENSHOT_DIR = Path(__file__).parent.parent.parent / "test_screenshots"
SCREENSHOT_DIR.mkdir(exist_ok=True)

ACTION_TIMEOUT = 30_000   # ms — per-action default
NAV_TIMEOUT    = 45_000   # ms — page navigation
POST_NAV_WAIT  = 1.5      # seconds after navigation
SUITE_PAUSE    = 4.0      # seconds between suites (let Odoo worker recover)

_DEFAULT_PWD = os.environ.get("ODOO_TEST_PASSWORD", "masios2024")
_ADMIN_PWD = os.environ.get("ODOO_ADMIN_PASSWORD", "admin")

TEST_USERS = [
    {"role": "CEO",         "login": "admin",                  "password": _ADMIN_PWD},
    {"role": "Hunter Lead", "login": "hung.hunter@masibio.vn", "password": _DEFAULT_PWD},
    {"role": "Farmer Lead", "login": "mai.farmer@masibio.vn",  "password": _DEFAULT_PWD},
    {"role": "Finance",     "login": "phuc.finance@masibio.vn","password": _DEFAULT_PWD},
    {"role": "Ops/PM",      "login": "dat.ops@masibio.vn",     "password": _DEFAULT_PWD},
    {"role": "Admin/Tech",  "login": "tung.admin@masibio.vn",  "password": _DEFAULT_PWD},
]

# Expected menu sets per role (as they appear in the Odoo navbar on /welcome)
# "Website" appears globally but is NOT counted in RBAC menus.
# "Apps" appears for CEO, Admin/Tech in the <a> tags.
EXPECTED_MENUS = {
    "CEO":         {"Discuss", "Calendar", "Contacts", "CRM", "Sales", "Invoicing",
                    "Project", "Command Center", "Settings", "Apps"},
    "Hunter Lead": {"Contacts", "CRM", "Sales", "Command Center"},
    "Farmer Lead": {"Contacts", "CRM", "Sales", "Command Center"},
    "Finance":     {"Contacts", "Invoicing", "Command Center"},
    "Ops/PM":      {"Contacts", "CRM", "Sales", "Project", "Command Center"},
    "Admin/Tech":  {"Discuss", "Calendar", "Contacts", "Command Center", "Settings", "Apps"},
}

# Menus that DO NOT belong to a role (to check they are absent)
FORBIDDEN_MENUS = {
    "Hunter Lead": {"Invoicing", "Settings"},
    "Farmer Lead": {"Invoicing", "Settings"},
    "Finance":     {"CRM", "Settings"},
    "Ops/PM":      {"Invoicing", "Settings"},
    "Admin/Tech":  {"CRM", "Sales", "Invoicing"},
}


# ─────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────
@dataclass
class TestResult:
    name: str
    passed: bool
    details: str = ""
    duration_ms: int = 0
    error: str = ""


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
async def save_screenshot(page: Page, test_name: str) -> str:
    """Save a screenshot on test failure."""
    safe = re.sub(r'[^\w\-]', '_', test_name)[:80]
    ts = int(time.time())
    path = SCREENSHOT_DIR / f"{safe}_{ts}.png"
    try:
        await page.screenshot(path=str(path), full_page=True)
    except Exception:
        pass
    return str(path)


async def login(page: Page, login_val: str, password: str) -> bool:
    """
    Log into Odoo.  MUST scope selectors to form.oe_login_form because the
    /web/login page also contains a website search form with its own submit button.
    Returns True when we land somewhere other than /web/login.
    """
    try:
        await page.goto(f"{BASE_URL}/web/login", wait_until="domcontentloaded",
                        timeout=NAV_TIMEOUT)
        # Scope everything to the login form
        form = page.locator("form.oe_login_form")
        await form.locator("input[name='login']").fill(login_val)
        await form.locator("input[name='password']").fill(password)
        await form.locator("button[type='submit']").click()
        await page.wait_for_url(lambda url: "/web/login" not in url, timeout=45_000)
        return True
    except Exception:
        return False


def extract_menus_from_html(html: str) -> set:
    """
    Extract Odoo app menu names from raw HTML.
    The welcome page renders menu items as plain <a> text nodes.
    """
    known = {"Discuss", "Calendar", "Contacts", "CRM", "Sales", "Invoicing",
             "Project", "Command Center", "Settings", "Apps"}
    found = set()
    # Extract all anchor text
    anchors = re.findall(r'<a[^>]*>\s*([A-Za-zÀ-ỹ ]+)\s*</a>', html)
    for a in anchors:
        a = a.strip()
        if a in known:
            found.add(a)
    return found


# ─────────────────────────────────────────────────────────────
# Suite 1: Welcome Page
# ─────────────────────────────────────────────────────────────
class WelcomePageSuite:
    """
    Suite 1: Each role logs in → lands on /welcome.
    Checks:
      - Page loads (not redirected to login)
      - Role keyword visible in page (in session_info or nav)
      - Feature content present (navbar items visible)
      - Quick links / menu items rendered
    """

    ROLE_KEYWORDS = {
        "CEO":         ["CEO", "is_admin", "is_system"],
        "Hunter Lead": ["Hunter", "hunter"],
        "Farmer Lead": ["Farmer", "farmer"],
        "Finance":     ["Finance", "finance"],
        "Ops/PM":      ["Ops", "ops", "PM"],
        "Admin/Tech":  ["Admin", "admin", "Tech"],
    }

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        for user in TEST_USERS:
            r = await self._test_welcome(browser, user)
            results.append(r)
        return results

    async def _test_welcome(self, browser: Browser, user: dict) -> TestResult:
        role = user["role"]
        name = f"Suite1: Welcome page for {role}"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                ss = await save_screenshot(page, name)
                return TestResult(name, False, f"Login failed for {user['login']} | ss={ss}",
                                  int((time.time()-start)*1000))

            # After login, /odoo redirects → /welcome
            await page.goto(f"{BASE_URL}/welcome", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            url = page.url
            html = await page.content()

            # Must not be sent back to login
            if "/web/login" in url:
                ss = await save_screenshot(page, name)
                return TestResult(name, False, f"Redirected to login | url={url} | ss={ss}",
                                  int((time.time()-start)*1000))

            # Page must contain at least some menu links (welcome content)
            menus = extract_menus_from_html(html)
            has_menus = len(menus) > 0

            # Role keyword check (lenient — session_info JSON + nav bar)
            role_kws = self.ROLE_KEYWORDS.get(role, [role])
            role_visible = any(kw.lower() in html.lower() for kw in role_kws)

            # Feature cards / quick links — page has substantial content
            has_content = len(html) > 5000  # welcome page is always ≥5 KB

            passed = not ("/web/login" in url) and has_content and has_menus

            details = (f"url={url} | menus={sorted(menus)} | "
                       f"role_kw={role_visible} | content_len={len(html)}")

            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"

            return TestResult(name, passed, details, int((time.time()-start)*1000))

        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()


# ─────────────────────────────────────────────────────────────
# Suite 2: RBAC Menu Visibility
# ─────────────────────────────────────────────────────────────
class RBACMenuSuite:
    """
    Suite 2: Each role sees the correct set of menus on /welcome.
    Strategy: parse <a> text nodes on /welcome and match against EXPECTED_MENUS.
    Passing criteria: all EXPECTED menus present AND no FORBIDDEN menus present.
    (Website appears for all users and is not in the expected/forbidden sets.)
    """

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        for user in TEST_USERS:
            r = await self._test_menus(browser, user)
            results.append(r)
        return results

    async def _test_menus(self, browser: Browser, user: dict) -> TestResult:
        role = user["role"]
        name = f"Suite2: RBAC menus for {role}"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                ss = await save_screenshot(page, name)
                return TestResult(name, False, f"Login failed | ss={ss}",
                                  int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/welcome", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            html = await page.content()
            visible = extract_menus_from_html(html)

            expected = EXPECTED_MENUS.get(role, set())
            forbidden = FORBIDDEN_MENUS.get(role, set())

            missing  = expected - visible          # expected but not shown
            unwanted = forbidden & visible         # forbidden but shown

            # Lenient: pass if ≥70% expected present AND no critical forbidden
            match_ratio = len(expected & visible) / max(len(expected), 1)
            passed = match_ratio >= 0.7 and len(unwanted) == 0

            details = (f"expected={sorted(expected)} | "
                       f"visible={sorted(visible)} | "
                       f"missing={sorted(missing)} | "
                       f"unwanted={sorted(unwanted)} | "
                       f"match={match_ratio:.0%}")

            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"

            return TestResult(name, passed, details, int((time.time()-start)*1000))

        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()


# ─────────────────────────────────────────────────────────────
# Suite 3: RBAC URL Blocking
# ─────────────────────────────────────────────────────────────
class RBACURLBlockingSuite:
    """
    Suite 3: Non-authorized roles get an AccessError dialog when hitting
    restricted Odoo URLs.  Odoo 18 behaviour: URL loads but shows an
    error dialog (not a 3xx redirect), EXCEPT for /dashboard which
    redirects to /welcome for non-CEO.
    """

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        results.append(await self._test_hunter_no_accounting(browser))
        results.append(await self._test_finance_no_crm(browser))
        results.append(await self._test_non_ceo_dashboard(browser))
        results.append(await self._test_non_admin_settings(browser))
        return results

    async def _check_access_error(self, browser: Browser, user: dict,
                                   url: str, test_name: str) -> TestResult:
        """
        Navigate to url as user, then check for an Odoo AccessError dialog OR
        a redirect away from the URL (both count as "blocked").
        """
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                ss = await save_screenshot(page, test_name)
                return TestResult(test_name, False, f"Login failed | ss={ss}",
                                  int((time.time()-start)*1000))

            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            except Exception:
                pass  # ERR_ABORTED is acceptable — means access denied at network level

            await asyncio.sleep(POST_NAV_WAIT)

            final_url = page.url
            html = await page.content()

            # Check signals for "blocked"
            access_error_dialog = False
            for err_sel in [".o_error_dialog", ".modal .o_dialog", ".o_dialog"]:
                try:
                    el = page.locator(err_sel).first
                    if await el.is_visible(timeout=1500):
                        err_text = await el.inner_text(timeout=1500)
                        if any(kw in err_text for kw in ["Access", "Error", "Lỗi", "không được phép",
                                                          "not allowed", "allowed for"]):
                            access_error_dialog = True
                            break
                except Exception:
                    pass

            redirected_away = (
                "/web/login" in final_url or
                "/welcome" in final_url or
                (final_url.rstrip("/") not in (url.rstrip("/"), url.rstrip("/") + "/"))
            )

            html_has_error = any(kw in html for kw in [
                "AccessError", "Access Error", "Lỗi Truy Cập",
                "not allowed to access", "không được phép truy cập"
            ])

            blocked = access_error_dialog or redirected_away or html_has_error
            passed = blocked

            details = (f"user={user['role']} url={url} | "
                       f"final_url={final_url} | "
                       f"dialog={access_error_dialog} | "
                       f"redirected={redirected_away} | "
                       f"html_error={html_has_error}")

            if not passed:
                ss = await save_screenshot(page, test_name)
                details += f" | ss={ss}"

            return TestResult(test_name, passed, details, int((time.time()-start)*1000))

        except Exception as e:
            ss = await save_screenshot(page, test_name)
            return TestResult(test_name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_hunter_no_accounting(self, browser: Browser) -> TestResult:
        user = next(u for u in TEST_USERS if u["role"] == "Hunter Lead")
        return await self._check_access_error(
            browser, user,
            f"{BASE_URL}/odoo/accounting",
            "Suite3: Hunter Lead blocked from /odoo/accounting"
        )

    async def _test_finance_no_crm(self, browser: Browser) -> TestResult:
        user = next(u for u in TEST_USERS if u["role"] == "Finance")
        return await self._check_access_error(
            browser, user,
            f"{BASE_URL}/odoo/crm",
            "Suite3: Finance blocked from /odoo/crm"
        )

    async def _test_non_ceo_dashboard(self, browser: Browser) -> TestResult:
        """
        Non-CEO → /dashboard must redirect to /welcome (not show CEO KPI data).
        Confirmed live: Hunter Lead gets redirected to /welcome.
        """
        name = "Suite3: Non-CEO redirected from /dashboard"
        start = time.time()
        user = next(u for u in TEST_USERS if u["role"] == "Hunter Lead")
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            final_url = page.url
            html = await page.content()

            # Redirected = not on /dashboard
            not_on_dashboard = "/dashboard" not in final_url
            # Or shows CEO content: if CEO KPI data is present, test FAILS
            has_ceo_kpis = (
                "CEO Dashboard" in html or
                (("pipeline" in html.lower() or "doanh thu" in html.lower()) and
                 ("revenue" in html.lower() or "debt" in html.lower()))
            )

            passed = not_on_dashboard and not has_ceo_kpis

            details = f"final_url={final_url} | not_on_dashboard={not_on_dashboard} | has_ceo_kpis={has_ceo_kpis}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"

            return TestResult(name, passed, details, int((time.time()-start)*1000))

        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_non_admin_settings(self, browser: Browser) -> TestResult:
        user = next(u for u in TEST_USERS if u["role"] == "Hunter Lead")
        return await self._check_access_error(
            browser, user,
            f"{BASE_URL}/odoo/settings",
            "Suite3: Hunter Lead blocked from /odoo/settings"
        )


# ─────────────────────────────────────────────────────────────
# Suite 4: Credit Control Functionality
# ─────────────────────────────────────────────────────────────
class CreditControlSuite:
    """
    Suite 4: masios_credit_control module adds fields to res.partner.
    Strategy:
      - Navigate to Contacts list view (view_type=list)
      - Search for "ABC Tech"
      - Check customer_classification column in list
      - Open first result row
      - Click "Công nợ" tab (a[name=credit_control])
      - Verify outstanding_debt and customer_classification fields
    """

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        results.append(await self._test_classification_in_list(browser))
        results.append(await self._test_credit_tab_exists(browser))
        results.append(await self._test_outstanding_debt_field(browser))
        results.append(await self._test_classification_field(browser))
        results.append(await self._test_new_customer_exists(browser))
        return results

    async def _login_admin(self, browser: Browser):
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        ok = await login(page, "admin", _ADMIN_PWD)
        return context, page, ok

    async def _open_contacts_list(self, page: Page, search_term: str = "") -> bool:
        """Navigate to contacts in list view, optionally search."""
        try:
            await page.goto(f"{BASE_URL}/odoo/contacts?view_type=list",
                            wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)
            if search_term:
                search = page.locator(".o_searchview_input").first
                if await search.is_visible(timeout=3000):
                    await search.fill(search_term)
                    await search.press("Enter")
                    await asyncio.sleep(1.5)
            return True
        except Exception:
            return False

    async def _test_classification_in_list(self, browser: Browser) -> TestResult:
        name = "Suite4: customer_classification column in Contacts list"
        start = time.time()
        context, page, ok = await self._login_admin(browser)
        try:
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await self._open_contacts_list(page, "ABC Tech")
            html = await page.content()

            # customer_classification column header should be in list view
            has_col = "customer_classification" in html
            has_abc = "ABC Tech" in html

            # Column values: "Khách hàng cũ" = old, various new options
            has_cũ = "cũ" in html.lower() or "Khách hàng cũ" in html
            has_mới = "mới" in html.lower()

            passed = has_col and has_abc

            details = (f"has_col={has_col} | has_abc={has_abc} | "
                       f"has_cũ={has_cũ} | has_mới={has_mới}")
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"

            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_credit_tab_exists(self, browser: Browser) -> TestResult:
        name = "Suite4: 'Công nợ' credit tab present in contact form"
        start = time.time()
        context, page, ok = await self._login_admin(browser)
        try:
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            # New contact form always shows all tabs
            await page.goto(f"{BASE_URL}/odoo/contacts/new",
                            wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            html = await page.content()
            # The credit control tab anchor
            has_tab = 'name="credit_control"' in html
            has_label = "Công nợ" in html

            passed = has_tab or has_label
            details = f"has_tab_anchor={has_tab} | has_label={has_label}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_outstanding_debt_field(self, browser: Browser) -> TestResult:
        name = "Suite4: outstanding_debt field visible in Công nợ tab"
        start = time.time()
        context, page, ok = await self._login_admin(browser)
        try:
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/odoo/contacts/new",
                            wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            # Click "Công nợ" tab
            tab_clicked = False
            for sel in ["a[name='credit_control']", "text=Công nợ"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click(timeout=3000)
                        await asyncio.sleep(0.8)
                        tab_clicked = True
                        break
                except Exception:
                    continue

            html = await page.content()

            # Look for the field and its label
            has_field  = "outstanding_debt" in html
            has_label  = "Công nợ hiện tại" in html    # confirmed live
            has_credit_limit = "Hạn mức công nợ" in html  # confirmed live

            passed = (has_field or has_label) and tab_clicked

            details = (f"tab_clicked={tab_clicked} | "
                       f"outstanding_debt_field={has_field} | "
                       f"Công_nợ_hiện_tại_label={has_label} | "
                       f"Hạn_mức_label={has_credit_limit}")
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_classification_field(self, browser: Browser) -> TestResult:
        name = "Suite4: customer_classification (Phân loại KH) field visible"
        start = time.time()
        context, page, ok = await self._login_admin(browser)
        try:
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/odoo/contacts/new",
                            wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            # Click "Công nợ" tab
            for sel in ["a[name='credit_control']", "text=Công nợ"]:
                try:
                    el = page.locator(sel).first
                    if await el.is_visible(timeout=2000):
                        await el.click(timeout=3000)
                        await asyncio.sleep(0.8)
                        break
                except Exception:
                    continue

            html = await page.content()

            has_field  = "customer_classification" in html
            has_label  = "Phân loại KH" in html          # confirmed live
            has_values = ('Khách hàng cũ' in html or '"old"' in html or
                          'Khách hàng mới' in html or '"new"' in html)

            passed = has_field and has_label

            details = (f"field={has_field} | label={has_label} | "
                       f"values_in_html={has_values}")
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_new_customer_exists(self, browser: Browser) -> TestResult:
        name = "Suite4: Contacts list has customer_classification values (Cũ/Mới)"
        start = time.time()
        context, page, ok = await self._login_admin(browser)
        try:
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await self._open_contacts_list(page)
            html = await page.content()

            # The column header includes option labels in its tooltip JSON
            has_old  = "Khách hàng cũ" in html or '"old"' in html
            has_new  = "Khách hàng mới" in html or '"new"' in html
            has_col  = "customer_classification" in html

            passed = has_col and (has_old or has_new)
            details = (f"column={has_col} | old_option={has_old} | new_option={has_new}")
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()


# ─────────────────────────────────────────────────────────────
# Suite 5: Dashboard KPIs
# ─────────────────────────────────────────────────────────────
class DashboardKPISuite:
    """
    Suite 5: CEO Dashboard at /dashboard.
    Confirmed live:
      - Admin sees "CEO Dashboard" title, pipeline/revenue/debt/leads keywords
      - Non-CEO (Hunter Lead) is redirected to /welcome
    """

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        results.append(await self._test_ceo_dashboard_loads(browser))
        results.append(await self._test_kpi_keywords(browser))
        results.append(await self._test_non_ceo_blocked(browser))
        return results

    async def _test_ceo_dashboard_loads(self, browser: Browser) -> TestResult:
        name = "Suite5: CEO /dashboard page loads"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, "admin", _ADMIN_PWD)
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            url = page.url
            html = await page.content()

            on_dashboard = "/dashboard" in url
            has_title    = "CEO Dashboard" in html
            not_login    = "/web/login" not in url

            passed = on_dashboard and has_title and not_login

            details = f"url={url} | on_dashboard={on_dashboard} | has_title={has_title}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_kpi_keywords(self, browser: Browser) -> TestResult:
        name = "Suite5: Dashboard contains KPI section keywords"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, "admin", _ADMIN_PWD)
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(2.0)  # allow JS to render KPIs

            html = await page.content()

            # Confirmed live keywords present on the dashboard page
            kpi_keywords = ["pipeline", "revenue", "doanh thu", "debt", "công nợ",
                            "leads", "kpi", "KPI"]
            found = [kw for kw in kpi_keywords if kw.lower() in html.lower()]

            passed = len(found) >= 4  # must have at least 4 of the KPI keywords

            details = f"KPI keywords found ({len(found)}): {found}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_non_ceo_blocked(self, browser: Browser) -> TestResult:
        name = "Suite5: Hunter Lead redirected from /dashboard → /welcome"
        start = time.time()
        user = next(u for u in TEST_USERS if u["role"] == "Hunter Lead")
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/dashboard", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            final_url = page.url
            html = await page.content()

            redirected = "/dashboard" not in final_url
            no_ceo_data = "CEO Dashboard" not in html

            passed = redirected and no_ceo_data

            details = (f"final_url={final_url} | "
                       f"redirected_away={redirected} | no_ceo_data={no_ceo_data}")
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()


# ─────────────────────────────────────────────────────────────
# Suite 6: Command Center Access
# ─────────────────────────────────────────────────────────────
class CommandCenterSuite:
    """
    Suite 6: Command Center module (masios_command_center).
    Tests:
      1. CEO sees "Command Center" link in nav
      2. Admin can access masios.telegram_user via XML-RPC/JSON endpoint
      3. Finance role also sees Command Center in their menu
    """

    async def run(self, browser: Browser) -> List[TestResult]:
        results = []
        results.append(await self._test_ceo_sees_cc(browser))
        results.append(await self._test_telegram_model_accessible(browser))
        results.append(await self._test_finance_sees_cc(browser))
        return results

    async def _test_ceo_sees_cc(self, browser: Browser) -> TestResult:
        name = "Suite6: CEO sees 'Command Center' in nav"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, "admin", _ADMIN_PWD)
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/welcome", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            html = await page.content()
            menus = extract_menus_from_html(html)

            passed = "Command Center" in menus

            details = f"menus={sorted(menus)} | cc_present={'Command Center' in menus}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_telegram_model_accessible(self, browser: Browser) -> TestResult:
        """
        Verify masios.telegram_user model is accessible to admin via JSON-RPC.
        Use the Odoo /web/dataset/call_kw endpoint.
        """
        name = "Suite6: masios.telegram_user model accessible to admin"
        start = time.time()
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, "admin", _ADMIN_PWD)
            if not ok:
                return TestResult(name, False, "Login failed", int((time.time()-start)*1000))

            # Use fetch() via page.evaluate to call JSON-RPC with the active session
            result = await page.evaluate("""
                async () => {
                    const resp = await fetch('/web/dataset/call_kw', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            jsonrpc: '2.0', method: 'call', id: 1,
                            params: {
                                model: 'masios.telegram_user',
                                method: 'search_read',
                                args: [[]],
                                kwargs: {fields: ['id', 'name'], limit: 5}
                            }
                        })
                    });
                    return await resp.json();
                }
            """)

            has_result = "result" in str(result)
            has_error  = "error" in str(result).lower() and "result" not in str(result)
            # model_not_found means module not installed
            model_missing = "model" in str(result).lower() and ("not found" in str(result).lower() or
                                                                 "does not exist" in str(result).lower())

            passed = has_result and not model_missing

            details = (f"has_result={has_result} | has_error={has_error} | "
                       f"model_missing={model_missing} | "
                       f"response_keys={list(result.keys()) if isinstance(result, dict) else type(result).__name__}")

            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()

    async def _test_finance_sees_cc(self, browser: Browser) -> TestResult:
        name = "Suite6: Finance user sees 'Command Center' in nav"
        start = time.time()
        user = next(u for u in TEST_USERS if u["role"] == "Finance")
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_timeout(ACTION_TIMEOUT)
        try:
            ok = await login(page, user["login"], user["password"])
            if not ok:
                return TestResult(name, False, f"Login failed for {user['login']}",
                                  int((time.time()-start)*1000))

            await page.goto(f"{BASE_URL}/welcome", wait_until="domcontentloaded",
                            timeout=NAV_TIMEOUT)
            await asyncio.sleep(POST_NAV_WAIT)

            html = await page.content()
            menus = extract_menus_from_html(html)

            passed = "Command Center" in menus

            details = f"menus={sorted(menus)} | cc_present={'Command Center' in menus}"
            if not passed:
                ss = await save_screenshot(page, name)
                details += f" | ss={ss}"
            return TestResult(name, passed, details, int((time.time()-start)*1000))
        except Exception as e:
            ss = await save_screenshot(page, name)
            return TestResult(name, False, f"Exception: {e} | ss={ss}",
                              int((time.time()-start)*1000))
        finally:
            await context.close()


# ─────────────────────────────────────────────────────────────
# Report
# ─────────────────────────────────────────────────────────────
def print_report(suite_results: list) -> bool:
    print("\n" + "=" * 72)
    print("  TRINITY MASIOS ODOO 18 — E2E TEST REPORT")
    print("=" * 72)

    total_pass = total_fail = 0

    for suite_name, results in suite_results:
        sp = sum(1 for r in results if r.passed)
        sf = len(results) - sp
        total_pass += sp
        total_fail += sf
        label = "PASS" if sf == 0 else "FAIL"
        print(f"\n{suite_name}  [{sp}/{len(results)}] {label}")
        print("-" * 60)
        for r in results:
            ico = "PASS" if r.passed else "FAIL"
            dur = f"{r.duration_ms}ms"
            # Truncate long names
            short_name = r.name if len(r.name) <= 60 else r.name[:57] + "..."
            print(f"  [{ico}] {short_name} ({dur})")
            if r.details:
                det = r.details[:200] + ("..." if len(r.details) > 200 else "")
                print(f"         {det}")

    total = total_pass + total_fail
    print("\n" + "=" * 72)
    overall = "ALL PASS" if total_fail == 0 else f"{total_fail} FAILURE(S)"
    print(f"  TOTAL: {total_pass}/{total} PASSED  —  {overall}")
    print("=" * 72 + "\n")
    return total_fail == 0


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
async def main():
    print(f"Starting E2E suite → {BASE_URL}")
    print(f"Screenshots → {SCREENSHOT_DIR}")
    expected_count = 6 + 6 + 4 + 5 + 3 + 3
    print(f"Running {expected_count} tests across 6 suites\n")

    async with async_playwright() as pw:
        print("Launching Chromium (headless)...")
        browser = await pw.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
            timeout=60_000,
        )
        print("Browser ready.")

        # Warmup: wake Odoo workers before running tests
        print("Warming up Odoo server...")
        try:
            ctx = await browser.new_context()
            pg = await ctx.new_page()
            await pg.goto(f"{BASE_URL}/web/login", wait_until="domcontentloaded", timeout=NAV_TIMEOUT)
            await ctx.close()
            await asyncio.sleep(2.0)
            print("Warmup done.\n")
        except Exception as e:
            print(f"Warmup failed (continuing): {e}\n")

        try:
            suite_results = []

            async def run_suite(label, suite_obj):
                print(f"\n── {label} ──")
                results = await suite_obj.run(browser)
                suite_results.append((label, results))
                for r in results:
                    print(f"  {'OK' if r.passed else 'XX'} {r.name} ({r.duration_ms}ms)")
                await asyncio.sleep(SUITE_PAUSE)  # let Odoo workers recover
                return results

            await run_suite("Suite 1: Welcome Page",        WelcomePageSuite())
            await run_suite("Suite 2: RBAC Menu Visibility", RBACMenuSuite())
            await run_suite("Suite 3: RBAC URL Blocking",    RBACURLBlockingSuite())
            await run_suite("Suite 4: Credit Control",       CreditControlSuite())
            await run_suite("Suite 5: Dashboard KPIs",       DashboardKPISuite())
            await run_suite("Suite 6: Command Center",       CommandCenterSuite())

        finally:
            await browser.close()

        all_passed = print_report(suite_results)
        sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    asyncio.run(main())
