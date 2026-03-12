#!/usr/bin/env python3
"""Seed Odoo with user data for 6 roles (10 users total).

Run ON the Odoo server (103.72.97.51) via SSH.
Connects to Odoo XML-RPC at http://127.0.0.1:8069.
"""

import xmlrpc.client

URL = 'http://127.0.0.1:8069'
DB = 'odoo'
USER = 'admin'
PASS = 'admin'

common = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/common', allow_none=True)
uid = common.authenticate(DB, USER, PASS, {})
if not uid:
    print("ERROR: Authentication failed!")
    exit(1)
print(f"Authenticated as uid={uid}")

models = xmlrpc.client.ServerProxy(f'{URL}/xmlrpc/2/object', allow_none=True)


def search_read(model, domain, fields=None, limit=0):
    kwargs = {'fields': fields or []}
    if limit:
        kwargs['limit'] = limit
    return models.execute_kw(DB, uid, PASS, model, 'search_read', [domain], kwargs)


def search(model, domain):
    return models.execute_kw(DB, uid, PASS, model, 'search', [domain])


def create(model, vals):
    return models.execute_kw(DB, uid, PASS, model, 'create', [vals])


def write(model, ids, vals):
    return models.execute_kw(DB, uid, PASS, model, 'write', [ids, vals])


def get_ref(xml_id):
    """Resolve an XML ID like 'base.group_system' to a database ID."""
    module, name = xml_id.split('.', 1)
    recs = search_read('ir.model.data', [('module', '=', module), ('name', '=', name)], ['res_id'], limit=1)
    if recs:
        return recs[0]['res_id']
    print(f"  WARNING: XML ID '{xml_id}' not found!")
    return None


# ============================================================
# 1. Resolve group IDs
# ============================================================
print("\n=== Resolving group IDs ===")

GROUP_IDS = {}
group_refs = {
    'admin': 'base.group_system',
    'sale_user': 'sales_team.group_sale_salesman',
    'sale_manager': 'sales_team.group_sale_salesman_all_leads',
    'account_user': 'account.group_account_user',
    'internal_user': 'base.group_user',
}

# project.group_project_manager may not exist if project module not installed
project_ref = 'project.group_project_manager'

for key, xml_id in group_refs.items():
    gid = get_ref(xml_id)
    if gid:
        GROUP_IDS[key] = gid
        print(f"  {key} -> {xml_id} = {gid}")

# Try project manager group
pm_gid = get_ref(project_ref)
if pm_gid:
    GROUP_IDS['project_manager'] = pm_gid
    print(f"  project_manager -> {project_ref} = {pm_gid}")
else:
    print(f"  project_manager -> {project_ref} NOT FOUND, will use internal_user instead")

# ============================================================
# 2. Create Sales Teams
# ============================================================
print("\n=== Creating Sales Teams ===")

teams_to_create = [
    {'name': 'Hunter', 'sequence': 10},
    {'name': 'Farmer', 'sequence': 20},
]

team_ids = {}
for team_data in teams_to_create:
    existing = search_read('crm.team', [('name', '=', team_data['name'])], ['id', 'name'])
    if existing:
        team_ids[team_data['name']] = existing[0]['id']
        print(f"  Team '{team_data['name']}' already exists (id={existing[0]['id']})")
    else:
        tid = create('crm.team', team_data)
        team_ids[team_data['name']] = tid
        print(f"  Created team '{team_data['name']}' (id={tid})")

# ============================================================
# 3. Create Odoo Users
# ============================================================
print("\n=== Creating Odoo Users ===")

# User definitions: (name, login, groups_keys, team_name_or_None)
USERS = [
    # CEO already exists as admin - skip creation, just update
    # Hunter Lead
    {
        'name': 'Nguyễn Văn Hùng',
        'login': 'hung.nguyen',
        'groups': ['internal_user', 'sale_manager'],
        'team': 'Hunter',
    },
    # Hunter 1
    {
        'name': 'Lê Thị Mai',
        'login': 'mai.le',
        'groups': ['internal_user', 'sale_user'],
        'team': 'Hunter',
    },
    # Hunter 2
    {
        'name': 'Phạm Quốc Bảo',
        'login': 'bao.pham',
        'groups': ['internal_user', 'sale_user'],
        'team': 'Hunter',
    },
    # Farmer Lead
    {
        'name': 'Trần Thị Hương',
        'login': 'huong.tran',
        'groups': ['internal_user', 'sale_manager'],
        'team': 'Farmer',
    },
    # Farmer 1
    {
        'name': 'Nguyễn Đức Anh',
        'login': 'anh.nguyen',
        'groups': ['internal_user', 'sale_user'],
        'team': 'Farmer',
    },
    # Farmer 2
    {
        'name': 'Vũ Thị Lan',
        'login': 'lan.vu',
        'groups': ['internal_user', 'sale_user'],
        'team': 'Farmer',
    },
    # Finance
    {
        'name': 'Hoàng Minh Tú',
        'login': 'tu.hoang',
        'groups': ['internal_user', 'account_user'],
        'team': None,
    },
    # Ops/PM
    {
        'name': 'Đặng Quang Minh',
        'login': 'minh.dang',
        'groups': ['internal_user', 'project_manager'] if 'project_manager' in GROUP_IDS else ['internal_user'],
        'team': None,
    },
    # Admin/Tech
    {
        'name': 'Lý Thanh Sơn',
        'login': 'son.ly',
        'groups': ['internal_user', 'admin'],
        'team': None,
    },
]

created_users = {}  # login -> user_id

for u in USERS:
    existing = search_read('res.users', [('login', '=', u['login'])], ['id', 'name'])
    if existing:
        user_id = existing[0]['id']
        print(f"  User '{u['login']}' already exists (id={user_id}, name={existing[0]['name']})")
        created_users[u['login']] = user_id
        # Update password and groups anyway
        group_cmds = [(4, GROUP_IDS[g]) for g in u['groups'] if g in GROUP_IDS]
        update_vals = {'password': 'masios2024'}
        if group_cmds:
            update_vals['groups_id'] = group_cmds
        write('res.users', [user_id], update_vals)
        print(f"    -> Updated password and groups")
    else:
        group_cmds = [(4, GROUP_IDS[g]) for g in u['groups'] if g in GROUP_IDS]
        vals = {
            'name': u['name'],
            'login': u['login'],
            'password': 'masios2024',
            'lang': 'vi_VN',
            'groups_id': group_cmds,
        }
        try:
            user_id = create('res.users', vals)
            created_users[u['login']] = user_id
            print(f"  Created user '{u['login']}' - {u['name']} (id={user_id})")
        except Exception as e:
            print(f"  ERROR creating '{u['login']}': {e}")
            continue

# Also track admin user
admin_users = search_read('res.users', [('login', '=', 'admin')], ['id', 'name'])
if admin_users:
    created_users['admin'] = admin_users[0]['id']
    print(f"  Admin user found (id={admin_users[0]['id']})")

# ============================================================
# 4. Assign Users to Sales Teams
# ============================================================
print("\n=== Assigning Users to Sales Teams ===")

for u in USERS:
    if u['team'] and u['login'] in created_users:
        team_id = team_ids.get(u['team'])
        if team_id:
            user_id = created_users[u['login']]
            # Set sale_team_id on the user's related partner or via crm.team member
            # In Odoo 18, team membership is via crm.team.member
            existing_members = search_read('crm.team.member',
                [('crm_team_id', '=', team_id), ('user_id', '=', user_id)],
                ['id'])
            if existing_members:
                print(f"  {u['login']} already in team {u['team']}")
            else:
                try:
                    create('crm.team.member', {
                        'crm_team_id': team_id,
                        'user_id': user_id,
                    })
                    print(f"  Added {u['login']} to team {u['team']}")
                except Exception as e:
                    print(f"  ERROR adding {u['login']} to team {u['team']}: {e}")

# Also set team leader
for team_name, leader_login in [('Hunter', 'hung.nguyen'), ('Farmer', 'huong.tran')]:
    if leader_login in created_users:
        team_id = team_ids.get(team_name)
        if team_id:
            try:
                write('crm.team', [team_id], {'user_id': created_users[leader_login]})
                print(f"  Set {leader_login} as leader of team {team_name}")
            except Exception as e:
                print(f"  ERROR setting leader for {team_name}: {e}")

# ============================================================
# 5. Create Telegram Users
# ============================================================
print("\n=== Creating Telegram Users ===")

# First, get existing roles
roles = search_read('masios.telegram_role', [], ['id', 'code', 'name'])
role_map = {r['code']: r['id'] for r in roles}
role_strs = [str(r['code']) + '=' + str(r['id']) for r in roles]
print("  Found roles: " + ', '.join(role_strs))

if not role_map:
    print("  ERROR: No telegram roles found! Make sure masios_command_center module is installed.")
else:
    # Telegram user definitions
    TELEGRAM_USERS = [
        {
            'name': 'Trần Minh Đức',
            'telegram_id': '2048339435',
            'telegram_username': '@minhducCEO',
            'role_code': 'ceo',
            'odoo_login': 'admin',
            'notes': 'CEO - Toàn quyền',
        },
        {
            'name': 'Nguyễn Văn Hùng',
            'telegram_id': '1481072032',
            'telegram_username': '@hungHunterLead',
            'role_code': 'hunter_lead',
            'odoo_login': 'hung.nguyen',
            'notes': 'Hunter Lead',
        },
        {
            'name': 'Lê Thị Mai',
            'telegram_id': '1000000001',
            'telegram_username': '@maiHunter1',
            'role_code': 'hunter_lead',  # Hunter members get hunter_lead role (no separate hunter role)
            'odoo_login': 'mai.le',
            'notes': 'Hunter 1',
        },
        {
            'name': 'Phạm Quốc Bảo',
            'telegram_id': '1000000002',
            'telegram_username': '@baoHunter2',
            'role_code': 'hunter_lead',
            'odoo_login': 'bao.pham',
            'notes': 'Hunter 2',
        },
        {
            'name': 'Trần Thị Hương',
            'telegram_id': '1000000003',
            'telegram_username': '@huongFarmerLead',
            'role_code': 'farmer_lead',
            'odoo_login': 'huong.tran',
            'notes': 'Farmer Lead',
        },
        {
            'name': 'Nguyễn Đức Anh',
            'telegram_id': '1000000004',
            'telegram_username': '@anhFarmer1',
            'role_code': 'farmer_lead',
            'odoo_login': 'anh.nguyen',
            'notes': 'Farmer 1',
        },
        {
            'name': 'Vũ Thị Lan',
            'telegram_id': '1000000005',
            'telegram_username': '@lanFarmer2',
            'role_code': 'farmer_lead',
            'odoo_login': 'lan.vu',
            'notes': 'Farmer 2',
        },
        {
            'name': 'Hoàng Minh Tú',
            'telegram_id': '1000000006',
            'telegram_username': '@tuFinance',
            'role_code': 'finance',
            'odoo_login': 'tu.hoang',
            'notes': 'Finance',
        },
        {
            'name': 'Đặng Quang Minh',
            'telegram_id': '1000000007',
            'telegram_username': '@minhOps',
            'role_code': 'ops',
            'odoo_login': 'minh.dang',
            'notes': 'Ops/PM',
        },
        {
            'name': 'Lý Thanh Sơn',
            'telegram_id': '1000000008',
            'telegram_username': '@sonAdmin',
            'role_code': 'ceo',  # Admin/Tech gets CEO-level access
            'odoo_login': 'son.ly',
            'notes': 'Admin/Tech - full access',
        },
    ]

    for tu in TELEGRAM_USERS:
        # Check if telegram_id already exists
        existing = search_read('masios.telegram_user',
            [('telegram_id', '=', tu['telegram_id'])],
            ['id', 'name'])

        role_id = role_map.get(tu['role_code'])
        if not role_id:
            print(f"  WARNING: Role '{tu['role_code']}' not found, skipping {tu['name']}")
            continue

        odoo_user_id = created_users.get(tu['odoo_login'], False)

        vals = {
            'name': tu['name'],
            'telegram_id': tu['telegram_id'],
            'telegram_username': tu.get('telegram_username', ''),
            'role_id': role_id,
            'odoo_user_id': odoo_user_id or False,
            'notes': tu.get('notes', ''),
            'active': True,
        }

        if existing:
            rec_id = existing[0]['id']
            write('masios.telegram_user', [rec_id], vals)
            print(f"  Updated telegram user '{tu['name']}' (id={rec_id}, tg_id={tu['telegram_id']})")
        else:
            try:
                rec_id = create('masios.telegram_user', vals)
                print(f"  Created telegram user '{tu['name']}' (id={rec_id}, tg_id={tu['telegram_id']})")
            except Exception as e:
                print(f"  ERROR creating telegram user '{tu['name']}': {e}")

# ============================================================
# Summary
# ============================================================
print("\n" + "=" * 60)
print("SEED DATA COMPLETE")
print("=" * 60)

# Count results
all_users = search_read('res.users', [('share', '=', False)], ['login', 'name'])
all_teams = search_read('crm.team', [], ['name'])
all_tg_users = search_read('masios.telegram_user', [], ['name', 'telegram_id', 'role_code'])

print(f"\nOdoo Internal Users: {len(all_users)}")
for u in all_users:
    print(f"  - {u['login']:20s} | {u['name']}")

print(f"\nSales Teams: {len(all_teams)}")
for t in all_teams:
    members = search_read('crm.team.member', [('crm_team_id', '=', t['id'])], ['user_id'])
    member_names = [m['user_id'][1] for m in members] if members else []
    print(f"  - {t['name']:15s} | Members: {', '.join(member_names) if member_names else 'none'}")

print(f"\nTelegram Users: {len(all_tg_users)}")
for tu in all_tg_users:
    print(f"  - {tu['name']:25s} | tg_id={tu['telegram_id']:15s} | role={tu.get('role_code', '?')}")

print("\nAll passwords set to: masios2024")
print("Done!")
