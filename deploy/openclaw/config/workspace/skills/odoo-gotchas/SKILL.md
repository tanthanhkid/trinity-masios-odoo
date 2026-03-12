# Odoo 18 Gotchas & Error Prevention Guide

Reference this skill BEFORE writing any Odoo code. It contains all known errors, their root causes, and proven fixes from production experience.

---

## 1. XML-RPC Issues

### 1.1 allow_none=True (CRITICAL)
**Error**: `TypeError: cannot marshal None unless allow_none is enabled`
**When**: Odoo methods return None (e.g., `sale.advance.payment.inv.create_invoices()`)
**Fix**: ALWAYS initialize ServerProxy with `allow_none=True`:
```python
models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object", allow_none=True)
```

### 1.2 Integer Overflow (32-bit)
**Error**: `OverflowError: int exceeds XML-RPC limits` or silent truncation
**When**: Monetary values > 2,147,483,647 (2.1B VND is common!)
**Fix**: Cast large numbers to float:
```python
# BAD
'expected_revenue': 3500000000  # Fails! > 2^31
# GOOD
'expected_revenue': float(3500000000)
```

### 1.3 Many2one Field Returns
**Error**: `TypeError: 'bool' object is not subscriptable`
**When**: Accessing `record['partner_id'][1]` when field is False/None
**Fix**: Always check before accessing:
```python
partner = record.get('partner_id')
name = partner[1] if partner else None
pid = partner[0] if partner else None
```

### 1.4 Connection Timeout
**Error**: Hangs indefinitely or `ConnectionRefusedError`
**Fix**: Use custom TimeoutTransport:
```python
import xmlrpc.client
class TimeoutTransport(xmlrpc.client.Transport):
    def __init__(self, timeout=30):
        super().__init__()
        self.timeout = timeout
    def make_connection(self, host):
        conn = super().make_connection(host)
        conn.timeout = self.timeout
        return conn
```

### 1.5 Fault Message Parsing
**Error**: Odoo XML-RPC Fault contains full Python traceback
**Fix**: Extract last line only:
```python
except xmlrpc.client.Fault as e:
    msg = e.faultString.strip().split("\n")[-1]
```

---

## 2. Odoo 18 API Changes (vs Odoo 16/17)

### 2.1 Invoice Creation from Sale Order
**Error**: `AttributeError: 'sale.order' has no method 'action_create_invoices'`
**Reality**: Odoo 18 uses `_create_invoices()` (with underscore prefix)
**Fix**:
```python
# Method 1: Direct method call
inv_ids = models.execute_kw(db, uid, pw, 'sale.order', '_create_invoices', [[so_id]])

# Method 2: Wizard (returns None - need allow_none=True!)
wiz_id = models.execute_kw(db, uid, pw, 'sale.advance.payment.inv', 'create',
    [{'advance_payment_method': 'delivered'}])
models.execute_kw(db, uid, pw, 'sale.advance.payment.inv', 'create_invoices',
    [[wiz_id]], {'active_ids': [so_id], 'active_model': 'sale.order'})

# Method 3: Direct invoice creation (most reliable via XML-RPC)
inv_id = models.execute_kw(db, uid, pw, 'account.move', 'create', [{
    'move_type': 'out_invoice',
    'partner_id': partner_id,
    'invoice_line_ids': [(0, 0, {
        'product_id': product_id,
        'quantity': qty,
        'price_unit': price,
    })]
}])
models.execute_kw(db, uid, pw, 'account.move', 'action_post', [[inv_id]])
```

### 2.2 move_type Not type
**Error**: Field 'type' not found on account.move
**Fix**: Use `move_type` for invoice type:
- `out_invoice` = Customer Invoice
- `in_invoice` = Vendor Bill
- `out_refund` = Credit Note
- `in_refund` = Debit Note

### 2.3 company_dependent Fields (JSONB)
**Error**: `psycopg2.errors.CannotCoerce: cannot cast type numeric to jsonb`
**When**: Adding `company_dependent=True` to a field that already has numeric data in DB
**Root cause**: Odoo 18 stores company_dependent fields as JSONB in PostgreSQL
**Rule**: NEVER add `company_dependent=True` to existing fields that have data. If base Odoo already defines a field as company_dependent, do NOT override that attribute in your custom module.
```python
# BAD - will crash on module upgrade if data exists
credit_limit = fields.Monetary(company_dependent=True)

# GOOD - let base module handle company_dependent
credit_limit = fields.Monetary(string='Han muc', tracking=True)
```

### 2.4 State Field Values
Sale Order states: `draft` → `sent` → `sale` → `done` → `cancel`
Invoice states: `draft` → `posted` → `cancel`
**Gotcha**: Can't generate PDF from draft invoices. Must `action_post` first.
**Gotcha**: Can't create invoice from SO in `draft` state. Must `action_confirm` first.

### 2.5 payment_state vs amount_residual
```python
# For checking if invoice is unpaid, use amount_residual:
domain = [('state', '=', 'posted'), ('amount_residual', '>', 0)]

# payment_state values: 'not_paid', 'partial', 'paid', 'in_payment'
# But amount_residual is more reliable for financial calculations
```

---

## 3. Custom Module Development

### 3.1 Computed Fields with NewId
**Error**: `TypeError: unhashable type: 'NewId'` or wrong query results
**When**: Computed field tries to query DB with temporary record IDs
**Fix**: Filter out non-integer IDs:
```python
def _compute_something(self):
    real_ids = [pid for pid in self.ids if isinstance(pid, int)]
    if real_ids:
        # query with real_ids only
        data = self.env['model'].search_read([('id', 'in', real_ids)], ...)
    else:
        data = []
```

### 3.2 N+1 Query Prevention
**BAD**: Querying inside a loop
```python
for partner in self:
    invoices = self.env['account.move'].search([('partner_id', '=', partner.id)])
    partner.debt = sum(inv.amount_residual for inv in invoices)
```
**GOOD**: Batch query outside loop
```python
real_ids = [p.id for p in self if isinstance(p.id, int)]
invoices = self.env['account.move'].search_read(
    [('partner_id', 'in', real_ids), ('state', '=', 'posted')],
    ['partner_id', 'amount_residual'])
debt_map = {}
for inv in invoices:
    pid = inv['partner_id'][0]
    debt_map[pid] = debt_map.get(pid, 0) + inv['amount_residual']
for partner in self:
    partner.debt = debt_map.get(partner.id, 0)
```

### 3.3 Monetary Fields Need currency_field
```python
# BAD - will show no currency symbol
amount = fields.Monetary()

# GOOD
amount = fields.Monetary(currency_field='currency_id')
```

### 3.4 Module Upgrade vs Install
- `button_immediate_install` - first time install
- `button_immediate_upgrade` - update existing module
- **Gotcha**: Upgrade can fail if field types changed (e.g., numeric → jsonb)
- **Gotcha**: Data files with `noupdate="1"` won't update on upgrade
- **Always backup DB before upgrade**: `pg_dump odoo > backup.sql`

### 3.5 XML Data Records
```xml
<!-- noupdate="1" means: only create on install, skip on upgrade -->
<odoo noupdate="1">
    <record id="role_ceo" model="masios.telegram_role">
        <field name="name">CEO</field>
    </record>
</odoo>

<!-- noupdate="0" (default) means: recreate/update on every upgrade -->
```

---

## 4. Domain Filter Gotchas

### 4.1 Domain Must Be List
```python
# BAD
domain = "('state', '=', 'posted')"

# GOOD
domain = [('state', '=', 'posted')]
```

### 4.2 Boolean Values
```python
# BAD
[('active', '=', 'true')]

# GOOD
[('active', '=', True)]
```

### 4.3 Date Formats
```python
# BAD
[('date_order', '>', '01/15/2024')]

# GOOD - ISO format only
[('date_order', '>', '2024-01-15')]
```

### 4.4 Relational Field Queries
```python
# Search partner's invoices
[('partner_id', '=', 42)]           # exact ID
[('partner_id', 'in', [1, 2, 3])]   # multiple IDs
[('partner_id.name', 'ilike', 'abc')] # dotted path (ORM only, NOT XML-RPC)
```

---

## 5. PDF Report Generation

### 5.1 Session-Based Auth Required
**Error**: PDF download returns HTML login page instead of PDF
**Root cause**: PDF reports use HTTP session auth, NOT XML-RPC
**Fix**: Authenticate via `/web/session/authenticate` first:
```python
import urllib.request, http.cookiejar, json

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Step 1: Authenticate
auth_data = json.dumps({
    "jsonrpc": "2.0", "params": {"db": db, "login": user, "password": pw}
}).encode()
req = urllib.request.Request(f"{url}/web/session/authenticate",
    data=auth_data, headers={"Content-Type": "application/json"})
opener.open(req)

# Step 2: Download PDF
pdf_url = f"{url}/report/pdf/account.report_invoice/{invoice_id}"
pdf_data = opener.open(pdf_url).read()
```

### 5.2 Verify PDF Content
**Error**: Silent failure - returns HTML error page instead of PDF
**Fix**: Check magic bytes:
```python
if not pdf_data[:5] == b"%PDF-":
    raise ValueError("Not a valid PDF - session may have expired")
```

### 5.3 Report Names
- Sale Order: `sale.report_saleorder`
- Invoice: `account.report_invoice`
- These are Odoo-version-specific!

---

## 6. Credit Control & Sales Flow

### 6.1 Credit Check Logic
```python
# New customers: NO unpaid invoices allowed (strict)
if classification == 'new':
    if any_unpaid_invoices:
        raise UserError("New customer cannot have credit")

# Old customers: check credit_limit
if classification == 'old':
    if credit_limit == 0:
        pass  # UNLIMITED credit (0 means no limit, NOT zero limit!)
    elif outstanding_debt > credit_limit:
        raise UserError("Credit limit exceeded")
```

### 6.2 First Order Detection
```python
# Must exclude current order AND check only confirmed orders
earlier = self.env['sale.order'].search_count([
    ('partner_id', '=', order.partner_id.id),
    ('id', '!=', order.id),
    ('state', 'in', ('sale', 'done')),
    ('date_order', '<', order.date_order),
])
is_first = earlier == 0
```

---

## 7. read_group Pitfalls

### 7.1 Fails Silently on Missing Fields
**Error**: `xmlrpc.client.Fault: field 'xxx' not found`
**Fix**: Always wrap in try/except:
```python
def safe_read_group(model, domain, fields, groupby):
    try:
        return models.execute_kw(db, uid, pw, model, 'read_group',
            [domain, fields, groupby])
    except Exception:
        return []
```

### 7.2 Aggregation Field Names
```python
result = models.execute_kw(db, uid, pw, 'account.move', 'read_group',
    [[('state', '=', 'posted')], ['amount_total'], []])
# Result: [{'amount_total': 123456.0, '__count': 10}]
# Note: field name stays same, count is __count
```

### 7.3 None in Aggregation Results
```python
# read_group may return None for sum fields if no records match
total = result[0].get('amount_total') or 0  # Always default to 0
```

---

## 8. Search & CRUD via XML-RPC

### 8.1 search_read vs search + read
```python
# search_read = combined (preferred, one round-trip)
records = models.execute_kw(db, uid, pw, 'res.partner', 'search_read',
    [[('is_company', '=', True)]], {'fields': ['name', 'email'], 'limit': 10})

# search + read = two calls (needed when you need IDs separately)
ids = models.execute_kw(db, uid, pw, 'res.partner', 'search',
    [[('is_company', '=', True)]])
records = models.execute_kw(db, uid, pw, 'res.partner', 'read',
    [ids], {'fields': ['name', 'email']})
```

### 8.2 write() Takes List of IDs
```python
# BAD
models.execute_kw(db, uid, pw, 'res.partner', 'write', [42, {'name': 'New'}])

# GOOD - IDs must be a list
models.execute_kw(db, uid, pw, 'res.partner', 'write', [[42], {'name': 'New'}])
```

### 8.3 One2many/Many2many Command Tuples
```python
# (0, 0, {vals}) = create new record
# (1, id, {vals}) = update existing
# (2, id, 0) = delete
# (3, id, 0) = unlink (remove relation, don't delete)
# (4, id, 0) = link existing record
# (5, 0, 0) = unlink all
# (6, 0, [ids]) = replace all with these IDs

# Example: Add invoice lines
'invoice_line_ids': [(0, 0, {'product_id': 1, 'quantity': 5, 'price_unit': 100})]

# Example: Add user to groups
'groups_id': [(4, group_id)]

# Example: Set team members
'member_ids': [(6, 0, [user1_id, user2_id])]
```

### 8.4 Protected Models (Cannot Delete)
These models raise errors on delete via XML-RPC:
- `ir.model`, `ir.module.module`, `ir.model.access`
- `res.users`, `res.company`
- `ir.rule`, `ir.config_parameter`

---

## 9. SSH & Deployment (Windows-specific)

### 9.1 ALWAYS Use Paramiko (NEVER sshpass)
**Error**: sshpass fails on Windows (TTY issues, hangs)
```python
import paramiko
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

# Odoo server (key-based, no password)
ssh.connect('103.72.97.51', port=24700, username='root')

# Mac Studio (password-based)
ssh.connect('100.81.203.48', username='masios', password='19112003',
    allow_agent=False, look_for_keys=False)
```

### 9.2 File Transfer via SFTP
```python
sftp = ssh.open_sftp()
sftp.put('/local/path/script.py', '/remote/path/script.py')
sftp.close()
```

### 9.3 Docker File Permissions
Files copied via `docker cp` get owner 501:dialout (Mac UID). Fix:
```bash
docker exec -u root <container> chown openclaw:openclaw /path/to/file
```

### 9.4 CRLF in Shell Scripts
**Error**: `/bin/bash: no such file or directory` (invisible \r)
**Fix**: Always save .sh files with LF line endings, not CRLF.

---

## 10. OpenClaw & Telegram Integration

### 10.1 exec-approvals.json Scope
- Only works in LOCAL/CLI mode (`openclaw agent --session-id X`)
- Does NOT apply to Telegram gateway
- Gateway requires: `elevatedDefault: "full"` + `exec.security: "full"`

### 10.2 mcporter Hangs in Docker
**Error**: `mcporter call odoo.xxx` hangs indefinitely inside container
**Fix**: Use direct XML-RPC instead of mcporter for scripts (e.g., alert_runner.py)

### 10.3 Multiple Bot Instances
**Error**: Telegram 409 Conflict
**Cause**: Two containers using same bot token
**Fix**: Use different bot tokens for different instances

---

## 11. Sale Order Creation Gotchas

### 11.1 Fiscal Position SQL Conflict with Custom credit_limit
**Error**: `operator does not exist: numeric -> unknown` during SO confirmation
**When**: Custom module overrides `credit_limit` field type (e.g., removed `company_dependent`) but fiscal position computation still expects original type
**Fix**: Set `fiscal_position_id: False` when creating sale orders via XML-RPC:
```python
so_id = models.execute_kw(db, uid, pw, 'sale.order', 'create', [{
    'partner_id': partner_id,
    'fiscal_position_id': False,  # Avoid SQL type conflict
    'order_line': [(0, 0, {...})],
}])
```

### 11.2 Invoice Policy Must Be 'order'
**Error**: No invoice lines generated from SO
**When**: Product has `invoice_policy: 'delivery'` (default) but no deliveries done
**Fix**: Set `invoice_policy: 'order'` on products that should be invoiced without delivery:
```python
models.execute_kw(db, uid, pw, 'product.template', 'write',
    [[product_tmpl_id], {'invoice_policy': 'order'}])
```

### 11.3 Backdating Records via SQL
**Error**: Odoo ORM ignores `create_date` in `create()` vals
**When**: Need old create_dates for SLA testing
**Fix**: Use SSH + psql to update directly:
```sql
UPDATE crm_lead SET create_date = '2026-03-05 03:00:00' WHERE id = 42;
```
Note: This bypasses ORM — use only for seed/test data.

---

## Quick Reference: Error → Fix Map

| Error Message | Root Cause | Fix |
|---|---|---|
| `cannot marshal None` | Method returns None | `allow_none=True` on ServerProxy |
| `int exceeds XML-RPC limits` | Value > 2^31 | Cast to `float()` |
| `'bool' object not subscriptable` | Many2one field is False | Check `if field` before `field[0]` |
| `cannot cast numeric to jsonb` | company_dependent on existing data | Remove company_dependent attribute |
| `no method 'action_create_invoices'` | Odoo 18 API change | Use `_create_invoices()` or wizard |
| `field 'type' not found` | Odoo 18 renamed to move_type | Use `move_type` |
| `PDF returns HTML page` | Session expired | Re-authenticate via /web/session |
| `unhashable type: 'NewId'` | Computed field with temp IDs | Filter `isinstance(pid, int)` |
| `sshpass: command not found` | Windows doesn't support sshpass | Use paramiko |
| `no such file or directory` (shell) | CRLF line endings | Convert to LF |
| `Telegram 409 Conflict` | Duplicate bot tokens | Use unique token per instance |
| `operator does not exist: numeric -> unknown` | Field type mismatch in DB | Check column type, migrate data |
| `fiscal_position_id` SQL error | Custom field overrides conflict | Set `fiscal_position_id: False` on SO create |
| No invoice lines from SO | Product invoice_policy is 'delivery' | Set `invoice_policy: 'order'` on product |
| `create_date` ignored in create() | ORM auto-sets create_date | Use direct SQL via SSH for backdating |
