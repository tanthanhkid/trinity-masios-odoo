"""
Odoo Cleanup Script - Uninstall unnecessary modules and hide menus.
Connects via XML-RPC from Windows, no SSH needed.
"""
import xmlrpc.client
import time

url = "http://103.72.97.51:8069"
db, user, pw = "odoo", "admin", "admin"

print("=" * 60)
print("ODOO CLEANUP SCRIPT")
print("=" * 60)

# Connect
print("\n[1] Connecting to Odoo...")
common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
uid = common.authenticate(db, user, pw, {})
if not uid:
    print("ERROR: Authentication failed!")
    exit(1)
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
print(f"Connected as uid={uid}")

# Never uninstall these
PROTECTED = {
    'base', 'web', 'mail', 'account', 'sale', 'crm', 'project', 'contacts',
    'product', 'l10n_vn', 'sale_management', 'sales_team', 'sale_crm',
    'resource', 'analytic', 'uom', 'http_routing', 'portal', 'onboarding',
    'base_setup', 'base_import', 'bus', 'html_editor', 'web_editor',
}

# ============================================================
# STEP 1: Uninstall unnecessary modules
# ============================================================
print("\n" + "=" * 60)
print("STEP 1: UNINSTALL UNNECESSARY MODULES")
print("=" * 60)

modules_to_remove = [
    # SMS chain (children first)
    "calendar_sms",
    "crm_sms",
    "sale_sms",
    "project_sms",
    "sms",
    # Calendar
    "calendar",
    # IAP chain
    "iap_crm",
    "iap_mail",
    "partner_autocomplete",
    "iap",
    # Rating chain
    "portal_rating",
    "rating",
    # Payment
    "payment",
    # Misc unnecessary
    "sale_pdf_quote_builder",
    "sale_async_emails",
    "digest",
    "mail_bot",
    "utm",
    "privacy_lookup",
    "base_install_request",
    "account_qr_code_sepa",
    "account_qr_code_emv",
    "base_iban",
    "auth_totp_portal",
    "auth_totp_mail",
    "auth_totp",
    "web_tour",
    "project_todo",
    "phone_validation",
]

# Safety check
for m in modules_to_remove:
    if m in PROTECTED:
        print(f"ABORT: {m} is in PROTECTED list!")
        exit(1)

stats = {"uninstalled": [], "skipped_not_installed": [], "skipped_dependents": [], "failed": []}

for mod_name in modules_to_remove:
    print(f"\n--- {mod_name} ---")

    # Check if installed
    mod_ids = models.execute_kw(db, uid, pw, 'ir.module.module', 'search_read',
        [[('name', '=', mod_name)]],
        {'fields': ['id', 'state', 'shortdesc']})

    if not mod_ids:
        print(f"  NOT FOUND in module list, skipping")
        stats["skipped_not_installed"].append(mod_name)
        continue

    mod = mod_ids[0]
    if mod['state'] != 'installed':
        print(f"  State: {mod['state']} (not installed), skipping")
        stats["skipped_not_installed"].append(mod_name)
        continue

    print(f"  Found: {mod['shortdesc']} (id={mod['id']}, state={mod['state']})")

    # Check dependents - find modules that depend ON this module and are installed
    # ir.module.module.dependency: name = dependency name, module_id = the module that HAS the dependency
    dep_ids = models.execute_kw(db, uid, pw, 'ir.module.module.dependency', 'search_read',
        [[('name', '=', mod_name)]],
        {'fields': ['module_id']})

    if dep_ids:
        # Check if any of those parent modules are installed
        parent_mod_ids = [d['module_id'][0] for d in dep_ids]
        installed_parents = models.execute_kw(db, uid, pw, 'ir.module.module', 'search_read',
            [[('id', 'in', parent_mod_ids), ('state', '=', 'installed')]],
            {'fields': ['name', 'shortdesc']})

        if installed_parents:
            parent_names = [f"{p['name']} ({p['shortdesc']})" for p in installed_parents]
            print(f"  SKIP: Has installed dependents: {', '.join(parent_names)}")
            stats["skipped_dependents"].append((mod_name, parent_names))
            continue

    # Safe to uninstall
    print(f"  Uninstalling {mod_name}...")
    try:
        models.execute_kw(db, uid, pw, 'ir.module.module', 'button_immediate_uninstall', [[mod['id']]])
        print(f"  SUCCESS: {mod_name} uninstalled")
        stats["uninstalled"].append(mod_name)
        time.sleep(1)  # Brief pause between uninstalls
    except Exception as e:
        err_msg = str(e)
        # Truncate long error messages
        if len(err_msg) > 200:
            err_msg = err_msg[:200] + "..."
        print(f"  FAILED: {err_msg}")
        stats["failed"].append((mod_name, err_msg))

print("\n\n--- STEP 1 SUMMARY ---")
print(f"Uninstalled ({len(stats['uninstalled'])}): {', '.join(stats['uninstalled']) or 'none'}")
print(f"Skipped/not installed ({len(stats['skipped_not_installed'])}): {', '.join(stats['skipped_not_installed']) or 'none'}")
if stats['skipped_dependents']:
    print(f"Skipped/has dependents ({len(stats['skipped_dependents'])}):")
    for name, deps in stats['skipped_dependents']:
        print(f"  {name} <- {', '.join(deps)}")
if stats['failed']:
    print(f"Failed ({len(stats['failed'])}):")
    for name, err in stats['failed']:
        print(f"  {name}: {err}")

# ============================================================
# STEP 2: Hide unnecessary top-level menus
# ============================================================
print("\n" + "=" * 60)
print("STEP 2: HIDE UNNECESSARY TOP-LEVEL MENUS")
print("=" * 60)

# Menu XML IDs to KEEP visible (no group restriction)
keep_xmlids = [
    ('crm', 'crm_menu_root'),
    ('sale', 'sale_menu_root'),
    ('account', 'menu_finance'),
    ('project', 'menu_main_pm'),
    ('contacts', 'menu_contacts'),
    ('base', 'menu_administration'),
]

# Resolve keep IDs
keep_ids = set()
for module, name in keep_xmlids:
    try:
        recs = models.execute_kw(db, uid, pw, 'ir.model.data', 'search_read',
            [[('module', '=', module), ('name', '=', name)]],
            {'fields': ['res_id']})
        if recs:
            keep_ids.add(recs[0]['res_id'])
            print(f"  KEEP: {module}.{name} -> menu id {recs[0]['res_id']}")
        else:
            print(f"  WARN: {module}.{name} not found (module may be uninstalled)")
    except Exception as e:
        print(f"  WARN: Could not resolve {module}.{name}: {e}")

# Get admin group id
admin_group = models.execute_kw(db, uid, pw, 'ir.model.data', 'search_read',
    [[('module', '=', 'base'), ('name', '=', 'group_system')]],
    {'fields': ['res_id']})
admin_gid = admin_group[0]['res_id']
print(f"\nAdmin group id: {admin_gid}")

# Get all top-level menus
top_menus = models.execute_kw(db, uid, pw, 'ir.ui.menu', 'search_read',
    [[('parent_id', '=', False)]],
    {'fields': ['id', 'name', 'complete_name', 'groups_id']})

print(f"\nFound {len(top_menus)} top-level menus:")
hidden_count = 0
for menu in top_menus:
    if menu['id'] in keep_ids:
        print(f"  KEEP: [{menu['id']}] {menu['name']}")
    else:
        print(f"  HIDE: [{menu['id']}] {menu['name']} (restrict to admin only)")
        try:
            models.execute_kw(db, uid, pw, 'ir.ui.menu', 'write',
                [[menu['id']], {'groups_id': [(6, 0, [admin_gid])]}])
            hidden_count += 1
        except Exception as e:
            print(f"    FAILED to hide: {e}")

print(f"\nHidden {hidden_count} menus, kept {len(keep_ids)} visible")

# ============================================================
# STEP 3: Verify
# ============================================================
print("\n" + "=" * 60)
print("STEP 3: VERIFICATION")
print("=" * 60)

# Count installed modules
installed = models.execute_kw(db, uid, pw, 'ir.module.module', 'search_read',
    [[('state', '=', 'installed')]],
    {'fields': ['name', 'shortdesc'], 'order': 'name'})

print(f"\nInstalled modules ({len(installed)}):")
for m in installed:
    print(f"  - {m['name']}: {m['shortdesc']}")

# List visible top-level menus (no group restriction = visible to all)
top_menus_after = models.execute_kw(db, uid, pw, 'ir.ui.menu', 'search_read',
    [[('parent_id', '=', False)]],
    {'fields': ['id', 'name', 'groups_id']})

print(f"\nTop-level menus after cleanup ({len(top_menus_after)}):")
for menu in top_menus_after:
    groups = menu.get('groups_id', [])
    if not groups:
        visibility = "ALL USERS"
    elif groups == [admin_gid]:
        visibility = "ADMIN ONLY"
    else:
        visibility = f"groups: {groups}"
    print(f"  [{menu['id']}] {menu['name']} -> {visibility}")

print("\n" + "=" * 60)
print("CLEANUP COMPLETE")
print("=" * 60)
