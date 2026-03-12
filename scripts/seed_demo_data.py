#!/usr/bin/env python3
"""
Comprehensive seed/demo data for Odoo 18.0
- Task 1: Create invoices from existing confirmed Sale Orders + mixed payment states
- Task 2: Create 8 CRM leads (Vietnamese B2B agriculture)
- Task 3: Create 10 project tasks (if project module installed)
"""

import xmlrpc.client
from datetime import datetime, timedelta
import random
import traceback

# ── Connection ──────────────────────────────────────────────────────
URL = "http://127.0.0.1:8069"
DB = "odoo"
USER = "admin"
PASS = "admin"

common = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/common", allow_none=True)
models = xmlrpc.client.ServerProxy(f"{URL}/xmlrpc/2/object", allow_none=True)

uid = common.authenticate(DB, USER, PASS, {})
if not uid:
    raise RuntimeError("Authentication failed!")
print(f"[OK] Authenticated as uid={uid}")


def kw(model, method, args, kwargs=None):
    """Shorthand for execute_kw"""
    return models.execute_kw(DB, uid, PASS, model, method, args, kwargs or {})


def search(model, domain, **kw_args):
    return kw(model, 'search', [domain], kw_args)


def search_read(model, domain, fields, **kw_args):
    return kw(model, 'search_read', [domain], {'fields': fields, **kw_args})


def create(model, vals):
    return kw(model, 'create', [vals])


def write(model, ids, vals):
    return kw(model, 'write', [ids, vals])


# ── Helpers ─────────────────────────────────────────────────────────
def date_str(delta_days=0):
    return (datetime.now() + timedelta(days=delta_days)).strftime('%Y-%m-%d')


# ════════════════════════════════════════════════════════════════════
# TASK 1: Create Invoices from existing Sale Orders
# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 1: Creating Invoices from Confirmed Sale Orders")
print("=" * 60)

try:
    # Find confirmed sale orders (state = 'sale')
    confirmed_sos = search_read('sale.order', [('state', '=', 'sale')],
                                ['id', 'name', 'partner_id', 'amount_total', 'order_line'])
    print(f"Found {len(confirmed_sos)} confirmed sale orders")

    # Check existing invoices to avoid duplicates
    existing_invoices = search_read('account.move',
                                    [('move_type', '=', 'out_invoice')],
                                    ['id', 'partner_id', 'ref'])

    invoices_created = []

    for so in confirmed_sos:
        so_id = so['id']
        so_name = so['name']

        # Check if SO already has invoices
        existing_inv_for_so = search('account.move', [
            ('move_type', '=', 'out_invoice'),
            ('invoice_origin', '=', so_name)
        ])
        if existing_inv_for_so:
            print(f"  [SKIP] {so_name} already has invoice(s): {existing_inv_for_so}")
            continue

        try:
            # Try wizard approach first
            ctx = {
                'active_ids': [so_id],
                'active_model': 'sale.order',
                'active_id': so_id,
            }
            wiz_id = kw('sale.advance.payment.inv', 'create',
                        [{'advance_payment_method': 'delivered'}],
                        {'context': ctx})
            kw('sale.advance.payment.inv', 'create_invoices',
               [[wiz_id]], {'context': ctx})

            # Find the newly created invoice
            new_invs = search('account.move', [
                ('move_type', '=', 'out_invoice'),
                ('invoice_origin', '=', so_name)
            ])
            if new_invs:
                invoices_created.append((so_name, new_invs[0]))
                print(f"  [OK] {so_name} -> Invoice #{new_invs[0]} (wizard)")
            else:
                print(f"  [WARN] Wizard ran but no invoice found for {so_name}")
        except Exception as e:
            print(f"  [WARN] Wizard failed for {so_name}: {e}")
            # Fallback: create invoice directly
            try:
                # Get SO lines
                so_lines = search_read('sale.order.line', [('order_id', '=', so_id)],
                                       ['product_id', 'product_uom_qty', 'price_unit', 'name'])
                if not so_lines:
                    print(f"  [SKIP] {so_name} has no lines")
                    continue

                inv_lines = []
                for line in so_lines:
                    inv_lines.append((0, 0, {
                        'product_id': line['product_id'][0] if line['product_id'] else False,
                        'quantity': line['product_uom_qty'],
                        'price_unit': line['price_unit'],
                        'name': line['name'] or 'Product',
                    }))

                inv_id = create('account.move', {
                    'move_type': 'out_invoice',
                    'partner_id': so['partner_id'][0],
                    'invoice_origin': so_name,
                    'invoice_line_ids': inv_lines,
                })
                invoices_created.append((so_name, inv_id))
                print(f"  [OK] {so_name} -> Invoice #{inv_id} (direct)")
            except Exception as e2:
                print(f"  [FAIL] Direct invoice for {so_name}: {e2}")

    print(f"\nCreated {len(invoices_created)} invoices from SOs")

    # ── Now handle ALL draft invoices: post them and set varied states ──
    all_draft_invoices = search_read('account.move', [
        ('move_type', '=', 'out_invoice'),
        ('state', '=', 'draft'),
    ], ['id', 'name', 'amount_total', 'partner_id'])

    print(f"\nFound {len(all_draft_invoices)} draft invoices to process")

    # Define payment scenarios
    scenarios = [
        ('paid', -15),       # paid, due 15 days ago
        ('overdue', -30),    # unpaid, 30 days overdue
        ('overdue', -45),    # unpaid, 45 days overdue
        ('partial', -20),    # partial payment, 20 days overdue
        ('current', 15),     # due in 15 days, unpaid
        ('current', 30),     # due in 30 days, unpaid
        ('paid', -5),        # recently paid
        ('partial', -10),    # partial, 10 days overdue
        ('overdue', -60),    # very overdue
        ('current', 7),      # due in 7 days
        ('paid', -25),       # paid
        ('partial', 0),      # partial, due today
        ('overdue', -35),    # overdue
        ('current', 20),     # future
        ('paid', -2),        # just paid
        ('overdue', -50),    # very overdue
        ('current', 45),     # far future
    ]

    # Find payment journal
    journals = search_read('account.journal', [('type', '=', 'bank')], ['id', 'name'], limit=1)
    if not journals:
        journals = search_read('account.journal', [('type', '=', 'cash')], ['id', 'name'], limit=1)
    payment_journal_id = journals[0]['id'] if journals else False
    print(f"Payment journal: {journals[0]['name'] if journals else 'NONE'} (id={payment_journal_id})")

    for i, inv in enumerate(all_draft_invoices):
        scenario = scenarios[i % len(scenarios)]
        state_type, due_delta = scenario
        inv_id = inv['id']
        amount = inv['amount_total']

        try:
            # Set invoice date and due date BEFORE posting
            inv_date = date_str(due_delta - 30)  # invoice date before due date
            due_date = date_str(due_delta)
            write('account.move', [inv_id], {
                'invoice_date': inv_date,
                'invoice_date_due': due_date,
            })

            # Post the invoice
            kw('account.move', 'action_post', [[inv_id]])
            print(f"  [OK] Invoice #{inv_id} posted (scenario={state_type}, due={due_date})")

            # Register payments
            if state_type == 'paid' and payment_journal_id and amount > 0:
                try:
                    ctx = {
                        'active_ids': [inv_id],
                        'active_model': 'account.move',
                    }
                    wiz_id = kw('account.payment.register', 'create', [{
                        'journal_id': payment_journal_id,
                        'payment_date': date_str(due_delta + 2),
                        'amount': amount,
                    }], {'context': ctx})
                    kw('account.payment.register', 'action_create_payments',
                       [[wiz_id]], {'context': ctx})
                    print(f"    -> PAID in full ({amount})")
                except Exception as pe:
                    print(f"    -> Payment failed: {pe}")

            elif state_type == 'partial' and payment_journal_id and amount > 0:
                try:
                    partial_amount = round(amount * random.uniform(0.3, 0.6), 2)
                    ctx = {
                        'active_ids': [inv_id],
                        'active_model': 'account.move',
                    }
                    wiz_id = kw('account.payment.register', 'create', [{
                        'journal_id': payment_journal_id,
                        'payment_date': date_str(due_delta + 5),
                        'amount': partial_amount,
                    }], {'context': ctx})
                    kw('account.payment.register', 'action_create_payments',
                       [[wiz_id]], {'context': ctx})
                    print(f"    -> PARTIAL payment ({partial_amount} of {amount})")
                except Exception as pe:
                    print(f"    -> Partial payment failed: {pe}")

        except Exception as e:
            print(f"  [FAIL] Invoice #{inv_id}: {e}")

except Exception as e:
    print(f"[ERROR] Task 1 failed: {e}")
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# TASK 2: Create 8 CRM Leads (Vietnamese B2B Agriculture)
# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 2: Creating CRM Leads")
print("=" * 60)

try:
    # Get CRM stages
    stages = search_read('crm.stage', [], ['id', 'name'])
    print(f"CRM Stages: {[(s['id'], s['name']) for s in stages]}")
    stage_map = {s['name'].lower(): s['id'] for s in stages}

    # Map to standard stage names (Odoo 18 defaults)
    def find_stage(keywords):
        for kw_item in keywords:
            for name, sid in stage_map.items():
                if kw_item.lower() in name:
                    return sid
        return stages[0]['id'] if stages else 1

    stage_new = find_stage(['new', 'mới'])
    stage_qualified = find_stage(['qualified', 'đủ điều kiện'])
    stage_proposition = find_stage(['proposition', 'đề xuất', 'proposal'])
    stage_won = find_stage(['won', 'thắng'])

    # Get users for assignment
    users = search_read('res.users', [('share', '=', False)], ['id', 'name'], limit=5)
    user_ids = [u['id'] for u in users]
    print(f"Users: {[(u['id'], u['name']) for u in users]}")

    # Get or create partners for leads
    lead_data = [
        {
            'company': 'Công ty TNHH Nông sản Đồng Xanh',
            'contact': 'Nguyễn Văn Hùng',
            'email': 'hung.nguyen@dongxanh.vn',
            'phone': '0901234567',
            'lead_name': 'Cung cấp phân bón hữu cơ - Đồng Xanh',
            'revenue': 850000000,
            'prob': 75,
            'stage': stage_proposition,
        },
        {
            'company': 'Tập đoàn Nông nghiệp Mekong',
            'contact': 'Trần Thị Mai',
            'email': 'mai.tran@mekongagri.com',
            'phone': '0912345678',
            'lead_name': 'Hệ thống tưới tiêu thông minh - Mekong Agri',
            'revenue': 1200000000,
            'prob': 60,
            'stage': stage_qualified,
        },
        {
            'company': 'HTX Nông nghiệp Phú Thọ',
            'contact': 'Lê Minh Tuấn',
            'email': 'tuan.le@htxphutho.vn',
            'phone': '0923456789',
            'lead_name': 'Giống lúa chất lượng cao - HTX Phú Thọ',
            'revenue': 450000000,
            'prob': 40,
            'stage': stage_new,
        },
        {
            'company': 'Công ty CP Chế biến Thuỷ sản Cà Mau',
            'contact': 'Phạm Hoàng Long',
            'email': 'long.pham@thuysancamau.vn',
            'phone': '0934567890',
            'lead_name': 'Thức ăn nuôi tôm cao cấp - Cà Mau Seafood',
            'revenue': 2100000000,
            'prob': 85,
            'stage': stage_won,
        },
        {
            'company': 'Công ty TNHH Cà phê Tây Nguyên Xanh',
            'contact': 'Đặng Quốc Bảo',
            'email': 'bao.dang@tayxanh.coffee',
            'phone': '0945678901',
            'lead_name': 'Máy rang xay cà phê công nghiệp - Tây Nguyên',
            'revenue': 680000000,
            'prob': 55,
            'stage': stage_qualified,
        },
        {
            'company': 'Trang trại Bò sữa TH True Milk Nghệ An',
            'contact': 'Vũ Thị Hương',
            'email': 'huong.vu@thtruemilk.vn',
            'phone': '0956789012',
            'lead_name': 'Hệ thống quản lý đàn bò IoT - TH Nghệ An',
            'revenue': 3500000000,
            'prob': 30,
            'stage': stage_new,
        },
        {
            'company': 'Công ty TNHH XNK Gạo Việt Phát',
            'contact': 'Hoàng Đức Anh',
            'email': 'anh.hoang@vietphatrice.com',
            'phone': '0967890123',
            'lead_name': 'Xuất khẩu gạo ST25 sang EU - Việt Phát',
            'revenue': 5000000000,
            'prob': 70,
            'stage': stage_proposition,
        },
        {
            'company': 'HTX Rau sạch Đà Lạt Farm',
            'contact': 'Ngô Thanh Tùng',
            'email': 'tung.ngo@dalatfarm.vn',
            'phone': '0978901234',
            'lead_name': 'Nhà kính thông minh & hệ thống thuỷ canh - Đà Lạt',
            'revenue': 920000000,
            'prob': 50,
            'stage': stage_qualified,
        },
    ]

    leads_created = 0
    for i, ld in enumerate(lead_data):
        # Check if lead already exists
        existing = search('crm.lead', [('name', '=', ld['lead_name'])])
        if existing:
            print(f"  [SKIP] Lead already exists: {ld['lead_name']}")
            continue

        # Find or create partner
        partner_ids = search('res.partner', [('name', '=', ld['company'])])
        if partner_ids:
            partner_id = partner_ids[0]
        else:
            partner_id = create('res.partner', {
                'name': ld['company'],
                'is_company': True,
                'email': ld['email'],
                'phone': ld['phone'],
                'country_id': search('res.country', [('code', '=', 'VN')])[0],
            })
            # Create contact person
            create('res.partner', {
                'name': ld['contact'],
                'parent_id': partner_id,
                'email': ld['email'],
                'phone': ld['phone'],
                'type': 'contact',
            })

        assigned_user = user_ids[i % len(user_ids)]

        lead_id = create('crm.lead', {
            'name': ld['lead_name'],
            'partner_id': partner_id,
            'contact_name': ld['contact'],
            'email_from': ld['email'],
            'phone': ld['phone'],
            'expected_revenue': ld['revenue'],
            'probability': ld['prob'],
            'stage_id': ld['stage'],
            'user_id': assigned_user,
            'type': 'opportunity',
            'description': f"Khách hàng B2B ngành nông nghiệp.\nCông ty: {ld['company']}\nLiên hệ: {ld['contact']}",
        })

        # Mark won leads
        if ld['stage'] == stage_won:
            try:
                kw('crm.lead', 'action_set_won_rainbowman', [[lead_id]])
            except Exception:
                try:
                    kw('crm.lead', 'action_set_won', [[lead_id]])
                except Exception:
                    pass  # stage assignment is enough

        print(f"  [OK] Lead #{lead_id}: {ld['lead_name']} (stage={ld['stage']}, rev={ld['revenue']:,.0f})")
        leads_created += 1

    print(f"\nCreated {leads_created} CRM leads")

except Exception as e:
    print(f"[ERROR] Task 2 failed: {e}")
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# TASK 3: Create 10 Project Tasks (if project module installed)
# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("TASK 3: Creating Project Tasks")
print("=" * 60)

try:
    # Check if project module is installed
    installed = search('ir.module.module', [
        ('name', '=', 'project'),
        ('state', '=', 'installed')
    ])
    if not installed:
        print("[SKIP] Project module not installed")
    else:
        print("[OK] Project module is installed")

        # Get or create a project
        projects = search_read('project.project', [], ['id', 'name'], limit=5)
        if projects:
            project_id = projects[0]['id']
            print(f"Using existing project: {projects[0]['name']} (#{project_id})")
        else:
            project_id = create('project.project', {
                'name': 'Vận hành Kinh doanh Nông nghiệp',
                'description': 'Dự án quản lý hoạt động kinh doanh nông sản',
            })
            print(f"Created project #{project_id}: Vận hành Kinh doanh Nông nghiệp")

        # Get task stages
        task_stages = search_read('project.task.type', [], ['id', 'name'])
        print(f"Task stages: {[(s['id'], s['name']) for s in task_stages]}")

        if not task_stages:
            # Create default stages
            for sname in ['Mới', 'Đang thực hiện', 'Hoàn thành', 'Huỷ']:
                create('project.task.type', {'name': sname})
            task_stages = search_read('project.task.type', [], ['id', 'name'])

        def find_task_stage(keywords):
            for kw_item in keywords:
                for s in task_stages:
                    if kw_item.lower() in s['name'].lower():
                        return s['id']
            return task_stages[0]['id'] if task_stages else 1

        stage_todo = find_task_stage(['new', 'to do', 'mới', 'backlog'])
        stage_progress = find_task_stage(['progress', 'in progress', 'đang', 'doing'])
        stage_done = find_task_stage(['done', 'hoàn thành', 'complete', 'solved'])

        tasks_data = [
            {
                'name': 'Khảo sát thị trường phân bón hữu cơ Q2/2026',
                'stage': stage_todo,
                'deadline': date_str(14),
                'priority': '1',
                'desc': 'Khảo sát nhu cầu phân bón hữu cơ tại Tây Nguyên và ĐBSCL',
            },
            {
                'name': 'Chuẩn bị hồ sơ xuất khẩu gạo ST25 sang EU',
                'stage': stage_progress,
                'deadline': date_str(7),
                'priority': '1',
                'desc': 'Hoàn thiện chứng nhận GlobalGAP, phytosanitary certificate',
            },
            {
                'name': 'Lắp đặt hệ thống tưới tiêu thông minh - Phase 1',
                'stage': stage_progress,
                'deadline': date_str(-5),  # overdue
                'priority': '1',
                'desc': 'Triển khai hệ thống IoT tưới tiêu tại Mekong Agri',
            },
            {
                'name': 'Đánh giá chất lượng giống lúa mới vụ Đông Xuân',
                'stage': stage_done,
                'deadline': date_str(-10),
                'priority': '0',
                'desc': 'So sánh năng suất 5 giống lúa thử nghiệm',
            },
            {
                'name': 'Đào tạo nhân viên sử dụng hệ thống CRM Odoo',
                'stage': stage_progress,
                'deadline': date_str(-3),  # overdue
                'priority': '0',
                'desc': 'Training 2 ngày cho team sales về quy trình CRM',
            },
            {
                'name': 'Kiểm tra kho hàng & tồn kho cuối tháng 3',
                'stage': stage_todo,
                'deadline': date_str(19),
                'priority': '0',
                'desc': 'Kiểm kê tồn kho phân bón, thuốc BVTV, giống',
            },
            {
                'name': 'Thiết kế nhà kính thuỷ canh Đà Lạt - Bản vẽ kỹ thuật',
                'stage': stage_progress,
                'deadline': date_str(21),
                'priority': '1',
                'desc': 'Hoàn thiện bản vẽ kỹ thuật nhà kính 2000m2',
            },
            {
                'name': 'Báo cáo tài chính Q1/2026 cho CEO',
                'stage': stage_todo,
                'deadline': date_str(-1),  # overdue
                'priority': '1',
                'desc': 'Tổng hợp doanh thu, chi phí, lợi nhuận Q1',
            },
            {
                'name': 'Ký hợp đồng cung cấp thức ăn tôm - Cà Mau',
                'stage': stage_done,
                'deadline': date_str(-15),
                'priority': '0',
                'desc': 'Hợp đồng 12 tháng, giá trị 2.1 tỷ VND',
            },
            {
                'name': 'Cập nhật bảng giá sản phẩm Q2/2026',
                'stage': stage_todo,
                'deadline': date_str(25),
                'priority': '0',
                'desc': 'Review và cập nhật giá theo biến động thị trường',
            },
        ]

        tasks_created = 0
        for td in tasks_data:
            existing = search('project.task', [
                ('name', '=', td['name']),
                ('project_id', '=', project_id),
            ])
            if existing:
                print(f"  [SKIP] Task already exists: {td['name']}")
                continue

            assigned = user_ids[tasks_created % len(user_ids)] if user_ids else uid
            task_vals = {
                'name': td['name'],
                'project_id': project_id,
                'user_ids': [(4, assigned)],
                'date_deadline': td['deadline'],
                'stage_id': td['stage'],
                'priority': td['priority'],
                'description': td['desc'],
            }
            task_id = create('project.task', task_vals)
            print(f"  [OK] Task #{task_id}: {td['name']} (deadline={td['deadline']})")
            tasks_created += 1

        print(f"\nCreated {tasks_created} project tasks")

except Exception as e:
    print(f"[ERROR] Task 3 failed: {e}")
    traceback.print_exc()


# ════════════════════════════════════════════════════════════════════
# SUMMARY
# ════════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("SEED DATA CREATION COMPLETE")
print("=" * 60)

# Count totals
try:
    total_inv = len(search('account.move', [('move_type', '=', 'out_invoice')]))
    total_leads = len(search('crm.lead', [('type', '=', 'opportunity')]))
    total_tasks = 0
    try:
        total_tasks = len(search('project.task', []))
    except Exception:
        pass
    print(f"Total invoices: {total_inv}")
    print(f"Total opportunities: {total_leads}")
    print(f"Total project tasks: {total_tasks}")
except Exception:
    pass
