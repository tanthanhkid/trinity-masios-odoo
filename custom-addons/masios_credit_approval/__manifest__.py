{
    'name': 'Masi OS - Credit Approval',
    'version': '18.0.1.0.0',
    'category': 'Sales',
    'summary': 'Phê duyệt công nợ qua Telegram khi vượt ngưỡng',
    'description': """
        - Ngưỡng công nợ cấu hình trong Settings (mặc định 20 triệu VND)
        - Tạo yêu cầu phê duyệt khi confirm SO vượt ngưỡng
        - Gửi thông báo Telegram cho CEO với nút Duyệt/Từ chối
        - Lưu lịch sử phê duyệt trong Odoo
        - Tự động confirm SO khi CEO duyệt
    """,
    'author': 'Masi OS',
    'depends': ['masios_credit_control', 'sale_management', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'wizard/reject_wizard_views.xml',
        'views/credit_approval_views.xml',
        'views/res_config_settings_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
