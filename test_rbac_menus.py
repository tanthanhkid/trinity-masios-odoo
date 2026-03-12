"""Test RBAC menu visibility for each role via Playwright headless browser."""
import asyncio
import os
from playwright.async_api import async_playwright

ODOO_URL = "http://103.72.97.51:8069"

TEST_USERS = [
    {"role": "CEO", "login": "admin", "password": "admin"},
    {"role": "Hunter Lead", "login": "hung.hunter@masibio.vn", "password": "masios2024"},
    {"role": "Farmer Lead", "login": "mai.farmer@masibio.vn", "password": "masios2024"},
    {"role": "Finance", "login": "phuc.finance@masibio.vn", "password": "masios2024"},
    {"role": "Ops/PM", "login": "dat.ops@masibio.vn", "password": "masios2024"},
    {"role": "Admin/Tech", "login": "tung.admin@masibio.vn", "password": "masios2024"},
]

VN_TO_EN = {
    "Thảo luận": "Discuss", "Lịch": "Calendar", "Liên hệ": "Contacts",
    "CRM": "CRM", "Bán hàng": "Sales", "Kế toán": "Invoicing",
    "Hóa đơn": "Invoicing", "Dự án": "Project", "Command Center": "Command Center",
    "Cấu hình": "Settings", "Thiết lập": "Settings", "Cài đặt": "Settings", "Ứng dụng": "Apps",
    "Contacts": "Contacts", "Sales": "Sales", "Invoicing": "Invoicing",
    "Project": "Project", "Settings": "Settings", "Discuss": "Discuss",
    "Calendar": "Calendar", "Apps": "Apps",
}

EXPECTED = {
    "CEO": {"Discuss", "Calendar", "Contacts", "CRM", "Sales", "Invoicing",
            "Project", "Command Center", "Settings", "Apps"},
    "Hunter Lead": {"Contacts", "CRM", "Sales", "Command Center"},
    "Farmer Lead": {"Contacts", "CRM", "Sales", "Command Center"},
    "Finance": {"Contacts", "Invoicing", "Command Center"},
    "Ops/PM": {"Contacts", "CRM", "Sales", "Project", "Command Center"},
    "Admin/Tech": {"Discuss", "Calendar", "Contacts", "Command Center", "Settings", "Apps"},
}


async def test_user(browser, user_info):
    """Login as user, open apps dropdown, extract visible apps."""
    role = user_info["role"]
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        ignore_https_errors=True,
    )
    page = await context.new_page()
    page.set_default_timeout(60000)

    try:
        # Login
        await page.goto(f"{ODOO_URL}/web/login", timeout=60000)
        await page.wait_for_selector("input[name='login']", timeout=15000)
        await page.fill("input[name='login']", user_info["login"])
        await page.fill("input[name='password']", user_info["password"])
        await page.click("button[type='submit']")
        await page.wait_for_url("**/odoo**", timeout=60000)
        await asyncio.sleep(2)

        # Click the apps menu dropdown (waffle icon in top-left navbar)
        apps_btn = page.locator("button[title='Menu Chính'], button[title='Home Menu'], .o_navbar_apps_menu button, nav button.dropdown")
        await apps_btn.first.click()
        await asyncio.sleep(1)

        # Take screenshot AFTER dropdown is open
        screenshot_path = f"test_screenshots/rbac_{role.lower().replace('/', '_').replace(' ', '_')}.png"
        await page.screenshot(path=screenshot_path, full_page=True)

        # Extract app names from the dropdown
        menus_raw = await page.evaluate("""
            () => {
                const items = [];
                // Odoo 18: apps dropdown contains .o_app elements or menu items
                const selectors = [
                    '.o_home_menu .o_app .o_caption',
                    '.o_home_menu .o_app .o_app_name',
                    '.o_navbar_apps_menu .dropdown-menu .dropdown-item',
                    '.o-dropdown--menu .o_app .o_caption',
                    '.o-dropdown--menu .dropdown-item',
                    '.o_home_menu_wrapper .o_app .o_caption',
                ];
                for (const sel of selectors) {
                    document.querySelectorAll(sel).forEach(el => {
                        const name = el.textContent.trim();
                        if (name && name.length < 40 && !items.includes(name)) items.push(name);
                    });
                    if (items.length > 0) break;
                }

                // If nothing found, try broader search
                if (items.length === 0) {
                    // Get all visible dropdown menus
                    document.querySelectorAll('.show .dropdown-item, [aria-expanded="true"] + * a, .o-dropdown.show a').forEach(el => {
                        const name = el.textContent.trim();
                        if (name && name.length < 40 && !items.includes(name)) items.push(name);
                    });
                }

                // Last resort: dump what's in the apps menu area
                if (items.length === 0) {
                    const appsMenu = document.querySelector('.o_navbar_apps_menu');
                    if (appsMenu) {
                        const dropdown = appsMenu.querySelector('.dropdown-menu, .o-dropdown--menu, [role="menu"]');
                        if (dropdown) {
                            return ['__DEBUG__:' + dropdown.innerHTML.substring(0, 500)];
                        }
                    }
                    // Try finding ANY open dropdown
                    const openDropdown = document.querySelector('.show, [aria-expanded="true"]');
                    if (openDropdown) {
                        return ['__DEBUG_OPEN__:' + openDropdown.parentElement.innerHTML.substring(0, 500)];
                    }
                    return ['__DEBUG_NONE__'];
                }

                return items;
            }
        """)

        # Check for debug output
        if menus_raw and menus_raw[0].startswith('__DEBUG'):
            print(f"  [{role}] {menus_raw[0][:200]}")
            menus_raw = []

        # Normalize to English
        menus_en = [VN_TO_EN.get(m, m) for m in menus_raw]
        print(f"  [{role}] Apps: {menus_raw} -> {menus_en}")

        return role, menus_en, menus_raw, "OK"

    except Exception as e:
        try:
            sp = f"test_screenshots/rbac_{role.lower().replace('/', '_').replace(' ', '_')}_error.png"
            await page.screenshot(path=sp)
        except:
            pass
        return role, [], [], f"ERROR: {str(e)[:150]}"
    finally:
        await context.close()


async def main():
    os.makedirs("test_screenshots", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("=" * 70)
        print("RBAC MENU VISIBILITY TEST - Odoo 18 (Headless)")
        print("=" * 70)

        results = []
        for user in TEST_USERS:
            print(f"\nTesting {user['role']}...")
            role, menus_en, menus_raw, status = await test_user(browser, user)
            results.append((role, menus_en, menus_raw, status))

        await browser.close()

        # Results
        print(f"\n{'=' * 70}")
        print("RESULTS")
        print(f"{'=' * 70}")

        total_pass = 0
        for role, menus_en, menus_raw, status in results:
            expected = EXPECTED.get(role, set())
            menu_set = set(menus_en)

            if status != "OK" or not menus_en:
                verdict = f"FAIL ({status if status != 'OK' else 'no menus found'})"
                icon = "FAIL"
            else:
                missing = expected - menu_set
                extra = menu_set - expected
                if not missing and not extra:
                    verdict = "PASS (exact match)"
                    icon = "PASS"
                    total_pass += 1
                elif not missing:
                    verdict = f"PASS (+ extra: {extra})"
                    icon = "PASS"
                    total_pass += 1
                else:
                    verdict = f"FAIL (missing: {sorted(missing)})"
                    icon = "FAIL"
                    if extra:
                        verdict += f" (extra: {sorted(extra)})"

            print(f"\n  {icon} {role}")
            print(f"    Login:     {[u['login'] for u in TEST_USERS if u['role']==role][0]}")
            print(f"    Raw:       {menus_raw}")
            print(f"    English:   {sorted(menus_en)}")
            print(f"    Expected:  {sorted(expected)}")
            print(f"    Verdict:   {verdict}")

        print(f"\n{'=' * 70}")
        print(f"TOTAL: {total_pass}/{len(results)} PASSED")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
