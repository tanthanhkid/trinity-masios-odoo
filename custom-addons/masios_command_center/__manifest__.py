{
    'name': 'Masios Command Center',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Trung tâm điều hành Telegram — mở rộng CRM, Sales, Invoice, Project',
    'description': """
        MASI OS Command Center
        ======================
        Mở rộng data model cho Telegram bot điều hành:
        - VIP level, sleeping customer detection, reorder prediction
        - Hunter/Farmer team assignment
        - SLA tracking cho leads
        - AR aging & collection status cho invoices
        - Task categorization cho project tasks
    """,
    'author': 'Masi OS',
    'depends': [
        'base',
        'crm',
        'sale_management',
        'account',
        'masios_credit_control',
        'project',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/team_data.xml',
        'views/telegram_user_views.xml',
        'data/telegram_role_data.xml',
        'data/telegram_user_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
