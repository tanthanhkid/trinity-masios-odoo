{
    'name': 'Masi OS - Credit Control',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Quản lý công nợ & phân loại khách hàng',
    'description': """
        - Phân loại khách hàng: Mới/Cũ
        - Hạn mức công nợ cho khách hàng cũ
        - Kiểm tra công nợ khi xác nhận đơn hàng
        - KH mới: không cho phép công nợ
        - KH cũ: kiểm tra hạn mức credit limit
    """,
    'author': 'Masi OS',
    'depends': ['sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
