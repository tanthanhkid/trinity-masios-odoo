{
    'name': 'Masi OS - CEO Dashboard',
    'version': '18.0.1.0.0',
    'category': 'Website',
    'summary': 'Dashboard tổng hợp cho CEO',
    'description': 'Trang dashboard hiển thị KPI, pipeline, đơn hàng, hóa đơn, cảnh báo công nợ',
    'author': 'Masi OS',
    'depends': ['sale_management', 'account', 'crm', 'masios_credit_control', 'website'],
    'data': [
        'views/dashboard_template.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'masios_dashboard/static/src/css/dashboard.css',
            'masios_dashboard/static/src/js/dashboard.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
