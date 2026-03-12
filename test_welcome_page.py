"""Test welcome page renders correctly for each role via Playwright headless."""
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

EXPECTED_ROLE_TITLES = {
    "CEO": "CEO / Giám đốc",
    "Hunter Lead": "Hunter Lead / Trưởng nhóm Săn khách",
    "Farmer Lead": "Farmer Lead / Trưởng nhóm Chăm khách",
    "Finance": "Finance / Kế toán",
    "Ops/PM": "Ops/PM / Vận hành",
    "Admin/Tech": "Admin/Tech / Quản trị hệ thống",
}


async def test_user(browser, user_info):
    """Login, check if redirected to /welcome, verify role content."""
    role = user_info["role"]
    context = await browser.new_context(
        viewport={"width": 1440, "height": 900},
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
        await page.locator("form[action='/web/login'] button[type='submit']").first.click()

        # Wait for redirect - should go to /welcome
        await page.wait_for_load_state("networkidle", timeout=60000)
        await asyncio.sleep(3)
        final_url = page.url

        # Check if landed on welcome page
        on_welcome = "/welcome" in final_url

        # Extract page content
        content = await page.evaluate("""
            () => {
                const roleBadge = document.querySelector('.role-badge');
                const heroTitle = document.querySelector('.welcome-hero h1');
                const featureCards = document.querySelectorAll('.feature-card h5');
                const tips = document.querySelectorAll('.tip-item');

                return {
                    roleBadge: roleBadge ? roleBadge.textContent.trim() : null,
                    heroTitle: heroTitle ? heroTitle.textContent.trim() : null,
                    features: Array.from(featureCards).map(el => el.textContent.trim()),
                    tipCount: tips.length,
                };
            }
        """)

        # Screenshot
        screenshot_path = f"test_screenshots/welcome_{role.lower().replace('/', '_').replace(' ', '_')}.png"
        await page.screenshot(path=screenshot_path, full_page=True)

        return role, final_url, on_welcome, content, "OK"

    except Exception as e:
        try:
            sp = f"test_screenshots/welcome_{role.lower().replace('/', '_').replace(' ', '_')}_error.png"
            await page.screenshot(path=sp)
        except:
            pass
        return role, "", False, {}, f"ERROR: {str(e)[:150]}"
    finally:
        await context.close()


async def main():
    os.makedirs("test_screenshots", exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        print("=" * 70)
        print("WELCOME PAGE TEST - Odoo 18 (Headless)")
        print("=" * 70)

        results = []
        for user in TEST_USERS:
            print(f"\nTesting {user['role']}...")
            result = await test_user(browser, user)
            results.append(result)

        await browser.close()

        # Results
        print(f"\n{'=' * 70}")
        print("RESULTS")
        print(f"{'=' * 70}")

        total_pass = 0
        for role, url, on_welcome, content, status in results:
            expected_title = EXPECTED_ROLE_TITLES.get(role, "")

            checks = []
            if status != "OK":
                checks.append(f"ERROR: {status}")
            else:
                # Check 1: Landed on /welcome
                if on_welcome:
                    checks.append("PASS: Redirected to /welcome")
                else:
                    checks.append(f"FAIL: Landed on {url} (expected /welcome)")

                # Check 2: Role badge matches
                badge = content.get('roleBadge', '')
                if expected_title and expected_title in badge:
                    checks.append(f"PASS: Role badge = '{badge}'")
                else:
                    checks.append(f"FAIL: Role badge = '{badge}' (expected '{expected_title}')")

                # Check 3: Has feature cards
                features = content.get('features', [])
                if features:
                    checks.append(f"PASS: {len(features)} feature cards")
                else:
                    checks.append("FAIL: No feature cards found")

                # Check 4: Has tips
                tip_count = content.get('tipCount', 0)
                if tip_count > 0:
                    checks.append(f"PASS: {tip_count} tips")
                else:
                    checks.append("FAIL: No tips found")

            all_pass = all("PASS" in c for c in checks)
            if all_pass:
                total_pass += 1
            icon = "PASS" if all_pass else "FAIL"

            print(f"\n  {icon} {role}")
            print(f"    Login:    {[u['login'] for u in TEST_USERS if u['role']==role][0]}")
            print(f"    URL:      {url}")
            print(f"    Hero:     {content.get('heroTitle', 'N/A')}")
            print(f"    Features: {content.get('features', [])}")
            for c in checks:
                print(f"    {c}")

        print(f"\n{'=' * 70}")
        print(f"TOTAL: {total_pass}/{len(results)} PASSED")
        print(f"Screenshots: test_screenshots/welcome_*.png")
        print(f"{'=' * 70}")


if __name__ == "__main__":
    asyncio.run(main())
