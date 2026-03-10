# Odoo ORM & Module Development Reference

## Field Types

### Simple Fields

```python
from odoo import fields, models

class MyModel(models.Model):
    _name = 'my.model'
    _description = 'My Model'

    # Basic types
    name = fields.Char(string='Name', required=True, size=100)
    description = fields.Text(string='Description')
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)
    price = fields.Float(digits=(12, 2))
    amount = fields.Monetary(currency_field='currency_id')
    date = fields.Date(default=fields.Date.today)
    datetime = fields.Datetime(default=fields.Datetime.now)
    html_content = fields.Html(sanitize=True)
    image = fields.Binary(attachment=True)

    # Selection
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], default='draft', string='Status')
```

### Relational Fields

```python
    # Many2one (FK to another model)
    partner_id = fields.Many2one('res.partner', string='Customer', ondelete='cascade')
    company_id = fields.Many2one('res.company', default=lambda self: self.env.company)

    # One2many (reverse of Many2one)
    line_ids = fields.One2many('my.model.line', 'order_id', string='Lines')

    # Many2many
    tag_ids = fields.Many2many('my.model.tag', string='Tags')
```

### Computed Fields

```python
    total = fields.Float(compute='_compute_total', store=True)

    @api.depends('line_ids.price', 'line_ids.quantity')
    def _compute_total(self):
        for record in self:
            record.total = sum(line.price * line.quantity for line in record.line_ids)
```

### Inverse Fields (editable computed)

```python
    full_name = fields.Char(compute='_compute_full_name', inverse='_inverse_full_name')

    def _compute_full_name(self):
        for rec in self:
            rec.full_name = f"{rec.first_name} {rec.last_name}"

    def _inverse_full_name(self):
        for rec in self:
            parts = rec.full_name.split(' ', 1)
            rec.first_name = parts[0]
            rec.last_name = parts[1] if len(parts) > 1 else ''
```

## Constraints

```python
from odoo.exceptions import ValidationError

class MyModel(models.Model):
    # SQL constraint
    _sql_constraints = [
        ('name_unique', 'UNIQUE(name)', 'Name must be unique!'),
        ('price_positive', 'CHECK(price >= 0)', 'Price must be positive!'),
    ]

    # Python constraint
    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        for record in self:
            if record.date_end < record.date_start:
                raise ValidationError("End date must be after start date.")
```

## CRUD Operations

```python
# Create
record = self.env['my.model'].create({'name': 'Test', 'price': 100.0})

# Read / Search
records = self.env['my.model'].search([('state', '=', 'draft')], limit=10)
record = self.env['my.model'].browse(record_id)

# Update
record.write({'state': 'confirmed'})

# Delete
record.unlink()

# Search count
count = self.env['my.model'].search_count([('active', '=', True)])
```

## Common Search Domains

```python
# Operators: =, !=, >, >=, <, <=, like, ilike, in, not in, child_of, parent_of
[('state', '=', 'draft')]
[('name', 'ilike', 'test')]
[('id', 'in', [1, 2, 3])]
[('date', '>=', '2024-01-01')]

# AND (default): list items
[('state', '=', 'draft'), ('active', '=', True)]

# OR: use '|' prefix
['|', ('state', '=', 'draft'), ('state', '=', 'confirmed')]
```

## Views (XML)

### Form View

```xml
<record id="my_model_view_form" model="ir.ui.view">
    <field name="name">my.model.form</field>
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <form string="My Model">
            <header>
                <button name="action_confirm" type="object" string="Confirm"
                        class="oe_highlight" invisible="state != 'draft'"/>
                <field name="state" widget="statusbar"
                       statusbar_visible="draft,confirmed,done"/>
            </header>
            <sheet>
                <group>
                    <group>
                        <field name="name"/>
                        <field name="partner_id"/>
                    </group>
                    <group>
                        <field name="date"/>
                        <field name="price"/>
                    </group>
                </group>
                <notebook>
                    <page string="Lines">
                        <field name="line_ids">
                            <list editable="bottom">
                                <field name="product_id"/>
                                <field name="quantity"/>
                                <field name="price"/>
                            </list>
                        </field>
                    </page>
                    <page string="Notes">
                        <field name="description"/>
                    </page>
                </notebook>
            </sheet>
        </form>
    </field>
</record>
```

### List/Tree View

```xml
<record id="my_model_view_list" model="ir.ui.view">
    <field name="name">my.model.list</field>
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <list string="My Models">
            <field name="name"/>
            <field name="partner_id"/>
            <field name="date"/>
            <field name="price" sum="Total"/>
            <field name="state" decoration-success="state == 'done'"
                   decoration-info="state == 'draft'"/>
        </list>
    </field>
</record>
```

### Search View

```xml
<record id="my_model_view_search" model="ir.ui.view">
    <field name="name">my.model.search</field>
    <field name="model">my.model</field>
    <field name="arch" type="xml">
        <search>
            <field name="name"/>
            <field name="partner_id"/>
            <filter name="draft" string="Draft" domain="[('state', '=', 'draft')]"/>
            <filter name="confirmed" string="Confirmed" domain="[('state', '=', 'confirmed')]"/>
            <separator/>
            <filter name="my_records" string="My Records" domain="[('create_uid', '=', uid)]"/>
            <group expand="0" string="Group By">
                <filter name="group_state" string="Status" context="{'group_by': 'state'}"/>
                <filter name="group_date" string="Date" context="{'group_by': 'date:month'}"/>
            </group>
        </search>
    </field>
</record>
```

### Action & Menu

```xml
<record id="my_model_action" model="ir.actions.act_window">
    <field name="name">My Models</field>
    <field name="res_model">my.model</field>
    <field name="view_mode">list,form</field>
</record>

<menuitem id="my_module_menu_root" name="My Module" sequence="10"/>
<menuitem id="my_model_menu" name="My Models"
          parent="my_module_menu_root"
          action="my_model_action" sequence="10"/>
```

## Security (ir.model.access.csv)

```csv
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_my_model_user,my.model.user,model_my_model,base.group_user,1,1,1,0
access_my_model_manager,my.model.manager,model_my_model,base.group_system,1,1,1,1
```

## Inheritance

### Classic Inheritance (extend existing model)

```python
class ResPartner(models.Model):
    _inherit = 'res.partner'

    my_custom_field = fields.Char(string='Custom Field')
```

### Delegation Inheritance

```python
class SpecialModel(models.Model):
    _name = 'special.model'
    _inherits = {'my.model': 'parent_id'}

    parent_id = fields.Many2one('my.model', required=True, ondelete='cascade')
    special_field = fields.Char()
```

## Business Methods

```python
def action_confirm(self):
    for record in self:
        if record.state != 'draft':
            raise UserError("Only draft records can be confirmed.")
        record.state = 'confirmed'
    return True

def action_done(self):
    self.write({'state': 'done'})
    return True
```

## Onchange Methods

```python
@api.onchange('partner_id')
def _onchange_partner_id(self):
    if self.partner_id:
        self.name = self.partner_id.name
```

## Odoo Shell (for debugging)

```bash
/opt/odoo/odoo-server/odoo-bin shell -c /etc/odoo.conf -d odoo

# In shell:
>>> records = env['res.partner'].search([], limit=5)
>>> for r in records: print(r.name)
>>> env.cr.commit()
```

## CLI Reference

```bash
# Start server
odoo-bin -c /etc/odoo.conf

# Upgrade module
odoo-bin -c /etc/odoo.conf -u module_name -d dbname --stop-after-init

# Install module
odoo-bin -c /etc/odoo.conf -i module_name -d dbname --stop-after-init

# Scaffold new module
odoo-bin scaffold module_name /path/to/addons/

# Database operations
odoo-bin -c /etc/odoo.conf --db-filter='^mydb$' --no-database-list
```
