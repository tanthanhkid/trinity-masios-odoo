from odoo import http
from odoo.http import request


# Role detection: maps Odoo group XML IDs to role codes
ROLE_DETECTION = [
    ('base.group_system', 'admin'),
    ('sales_team.group_sale_salesman_all_leads', 'lead'),
    ('account.group_account_user', 'finance'),
    ('project.group_project_manager', 'ops'),
    ('project.group_project_user', 'ops'),
    ('sales_team.group_sale_salesman', 'sales'),
]

# Role definitions for the welcome page
ROLES = {
    'ceo': {
        'title': 'CEO / Giám đốc',
        'color': '#6366f1',
        'icon': 'fa-crown',
        'description': 'Tổng quan toàn bộ hoạt động kinh doanh, giám sát KPI và ra quyết định chiến lược.',
        'features': [
            {'name': 'CRM Pipeline', 'icon': 'fa-funnel-dollar', 'url': '/odoo/crm',
             'desc': 'Theo dõi leads, cơ hội kinh doanh và tỷ lệ chuyển đổi'},
            {'name': 'Doanh số', 'icon': 'fa-chart-line', 'url': '/odoo/sales',
             'desc': 'Báo giá, đơn hàng Hunter & Farmer'},
            {'name': 'Công nợ', 'icon': 'fa-file-invoice-dollar', 'url': '/odoo/accounting',
             'desc': 'Hóa đơn, AR aging, trạng thái thanh toán'},
            {'name': 'Dự án', 'icon': 'fa-tasks', 'url': '/odoo/project',
             'desc': 'Tasks, tiến độ, blockers'},
            {'name': 'Dashboard', 'icon': 'fa-tachometer-alt', 'url': '/dashboard',
             'desc': 'KPI tổng hợp, pipeline chart, cảnh báo công nợ'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Quản lý vai trò Telegram, người dùng'},
        ],
        'tips': [
            'Dùng /morning_brief trên Telegram để nhận báo cáo buổi sáng',
            'Dùng /ceo_alert để xem cảnh báo quan trọng',
            'Dùng /doanhso_homnay để theo dõi doanh số realtime',
        ],
    },
    'hunter_lead': {
        'title': 'Hunter Lead / Trưởng nhóm Săn khách',
        'color': '#f59e0b',
        'icon': 'fa-crosshairs',
        'description': 'Quản lý đội Hunter, theo dõi leads mới, SLA và chuyển đổi khách hàng mới.',
        'features': [
            {'name': 'CRM Pipeline', 'icon': 'fa-funnel-dollar', 'url': '/odoo/crm',
             'desc': 'Leads mới, cơ hội, chuyển đổi khách hàng'},
            {'name': 'Báo giá & Đơn hàng', 'icon': 'fa-file-alt', 'url': '/odoo/sales',
             'desc': 'Tạo báo giá, theo dõi đơn hàng đầu tiên'},
            {'name': 'Khách hàng', 'icon': 'fa-users', 'url': '/odoo/contacts',
             'desc': 'Quản lý thông tin khách hàng mới'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Cấu hình Telegram bot'},
        ],
        'tips': [
            'Dùng /hunter_today để xem tổng quan ngày',
            'Dùng /hunter_sla để theo dõi SLA liên hệ lead',
            'Dùng /hunter_quotes để xem báo giá đang chờ',
            'Dùng /newlead để tạo lead nhanh qua Telegram',
        ],
    },
    'farmer_lead': {
        'title': 'Farmer Lead / Trưởng nhóm Chăm khách',
        'color': '#10b981',
        'icon': 'fa-seedling',
        'description': 'Quản lý đội Farmer, chăm sóc khách hàng cũ, tái đặt hàng và công nợ.',
        'features': [
            {'name': 'Khách hàng', 'icon': 'fa-users', 'url': '/odoo/contacts',
             'desc': 'VIP, khách ngủ đông, chu kỳ tái đặt hàng'},
            {'name': 'Đơn hàng', 'icon': 'fa-shopping-cart', 'url': '/odoo/sales',
             'desc': 'Đơn tái đặt, theo dõi doanh số Farmer'},
            {'name': 'CRM', 'icon': 'fa-handshake', 'url': '/odoo/crm',
             'desc': 'Cơ hội upsell, cross-sell khách hàng cũ'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Cấu hình Telegram bot'},
        ],
        'tips': [
            'Dùng /farmer_today để xem tổng quan ngày',
            'Dùng /farmer_reorder để xem khách sắp tái đặt',
            'Dùng /farmer_sleeping để theo dõi khách ngủ đông',
            'Dùng /farmer_vip để chăm sóc khách VIP',
        ],
    },
    'finance': {
        'title': 'Finance / Kế toán',
        'color': '#3b82f6',
        'icon': 'fa-calculator',
        'description': 'Quản lý hóa đơn, công nợ, thu hồi nợ và theo dõi dòng tiền.',
        'features': [
            {'name': 'Hóa đơn', 'icon': 'fa-file-invoice', 'url': '/odoo/accounting',
             'desc': 'Tạo, đăng và quản lý hóa đơn'},
            {'name': 'Khách hàng', 'icon': 'fa-users', 'url': '/odoo/contacts',
             'desc': 'Hạn mức công nợ, trạng thái thanh toán'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Cấu hình Telegram bot'},
        ],
        'tips': [
            'Dùng /congno_denhan để xem công nợ sắp đến hạn',
            'Dùng /congno_quahan để xem công nợ quá hạn',
            'Dùng /brief_ar để tổng quan công nợ',
            'Dùng /brief_cash để xem áp lực dòng tiền',
        ],
    },
    'ops': {
        'title': 'Ops/PM / Vận hành',
        'color': '#8b5cf6',
        'icon': 'fa-cogs',
        'description': 'Quản lý tasks, dự án, theo dõi tiến độ và xử lý blockers.',
        'features': [
            {'name': 'Dự án & Tasks', 'icon': 'fa-tasks', 'url': '/odoo/project',
             'desc': 'Tạo, gán và theo dõi tasks'},
            {'name': 'CRM', 'icon': 'fa-chart-bar', 'url': '/odoo/crm',
             'desc': 'Xem tổng quan pipeline (đọc)'},
            {'name': 'Đơn hàng', 'icon': 'fa-clipboard-list', 'url': '/odoo/sales',
             'desc': 'Theo dõi trạng thái đơn hàng (đọc)'},
            {'name': 'Khách hàng', 'icon': 'fa-users', 'url': '/odoo/contacts',
             'desc': 'Thông tin khách hàng liên quan tasks'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Cấu hình Telegram bot'},
        ],
        'tips': [
            'Dùng /task_quahan để xem tasks quá hạn',
            'Dùng /midday để xem flash report giữa ngày',
            'Dùng /eod để xem báo cáo cuối ngày',
        ],
    },
    'admin_tech': {
        'title': 'Admin/Tech / Quản trị hệ thống',
        'color': '#ef4444',
        'icon': 'fa-shield-alt',
        'description': 'Quản trị hệ thống, phân quyền, giám sát sức khỏe hệ thống.',
        'features': [
            {'name': 'Cài đặt', 'icon': 'fa-cog', 'url': '/odoo/settings',
             'desc': 'Cấu hình hệ thống, modules, users'},
            {'name': 'Command Center', 'icon': 'fa-satellite-dish', 'url': '/odoo/action-471',
             'desc': 'Quản lý vai trò và người dùng Telegram'},
            {'name': 'Khách hàng', 'icon': 'fa-users', 'url': '/odoo/contacts',
             'desc': 'Quản lý dữ liệu khách hàng'},
            {'name': 'Ứng dụng', 'icon': 'fa-puzzle-piece', 'url': '/odoo/action-39',
             'desc': 'Cài đặt/gỡ modules'},
        ],
        'tips': [
            'Kiểm tra /odoo/settings để quản lý users và groups',
            'Dùng Command Center để thêm/sửa Telegram users',
            'Giám sát logs tại /var/log/odoo/odoo-server.log trên server',
        ],
    },
}


class WelcomeController(http.Controller):

    def _detect_role(self, user):
        """Detect user role based on Odoo groups and telegram_user."""
        # Check if admin (CEO)
        if user.has_group('base.group_system'):
            # Check if actually Admin/Tech (no sales groups)
            if not user.has_group('sales_team.group_sale_salesman'):
                # Admin without sales = Admin/Tech (unless CEO)
                tg_user = request.env['masios.telegram_user'].sudo().search(
                    [('odoo_user_id', '=', user.id)], limit=1)
                if tg_user and tg_user.role_id.code == 'ceo':
                    return 'ceo'
                return 'admin_tech'
            return 'ceo'

        # Check telegram role first (most accurate)
        tg_user = request.env['masios.telegram_user'].sudo().search(
            [('odoo_user_id', '=', user.id)], limit=1)
        if tg_user and tg_user.role_id:
            code = tg_user.role_id.code
            role_map = {
                'ceo': 'ceo',
                'hunter_lead': 'hunter_lead',
                'farmer_lead': 'farmer_lead',
                'finance': 'finance',
                'ops': 'ops',
                'admin_tech': 'admin_tech',
            }
            return role_map.get(code, 'hunter_lead')

        # Fallback: detect from Odoo groups
        if user.has_group('account.group_account_user'):
            return 'finance'
        if user.has_group('project.group_project_manager'):
            return 'ops'
        if user.has_group('sales_team.group_sale_salesman_all_leads'):
            # Lead = could be Hunter or Farmer lead, check team
            return 'hunter_lead'
        if user.has_group('sales_team.group_sale_salesman'):
            return 'hunter_lead'

        return 'hunter_lead'  # default

    @http.route('/welcome', type='http', auth='user', website=True)
    def welcome_page(self, **kwargs):
        user = request.env.user
        role_code = self._detect_role(user)
        role = ROLES.get(role_code, ROLES['hunter_lead'])

        return request.render('masios_command_center.welcome_page', {
            'user': user,
            'role_code': role_code,
            'role': role,
        })
