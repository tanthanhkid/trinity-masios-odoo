# Odoo Development Patterns

## Module Structure
```
my_module/
├── __init__.py           # Import models/
├── __manifest__.py       # name, version, depends, data
├── models/
│   ├── __init__.py       # Import each model file
│   └── my_model.py       # Model classes
├── views/
│   └── my_model_views.xml  # Form, list, search views + actions + menus
├── security/
│   └── ir.model.access.csv  # Access rights
├── data/                 # Default data XML
└── static/description/icon.png
```

## Model Naming
- Model name: `my.module.name` (dots)
- Table name: `my_module_name` (underscores, auto)
- File name: `my_module_name.py` (underscores)

## Key ORM Patterns
- `_name` = model identifier
- `_description` = human label
- `_inherit` = extend existing model
- `_inherits` = delegation inheritance
- `_order` = default sort
- `_rec_name` = display field

## Field Types
- Char, Text, Html, Integer, Float, Monetary, Boolean
- Date, Datetime
- Selection (list of tuples)
- Many2one, One2many, Many2many
- Binary (files/images)

## Deploy Custom Module
```bash
# 1. Put module in /opt/odoo/custom-addons/
# 2. Restart with upgrade:
sudo systemctl stop odoo
sudo -u odoo /opt/odoo/odoo-server/odoo-bin -c /etc/odoo.conf -u my_module -d odoo --stop-after-init
sudo systemctl start odoo
# 3. Or install new module:
# Replace -u with -i for first install
```

## Odoo Shell (debugging)
```bash
sudo -u odoo /opt/odoo/odoo-server/odoo-bin shell -c /etc/odoo.conf -d odoo
```

## Common Commands
- Update module: `-u module_name`
- Install module: `-i module_name`
- Scaffold: `odoo-bin scaffold module_name /path/`
- Always use `-d dbname --stop-after-init` for maintenance operations
