from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class TelegramRole(models.Model):
    _name = 'masios.telegram_role'
    _description = 'Telegram Command Center Role'
    _order = 'sequence, name'

    name = fields.Char(string='Tên vai trò', required=True)  # CEO, Hunter Lead, Farmer Lead, Finance, Ops/PM
    code = fields.Char(string='Mã vai trò', required=True)  # ceo, hunter_lead, farmer_lead, finance, ops
    sequence = fields.Integer(default=10)
    description = fields.Text(string='Mô tả')
    active = fields.Boolean(default=True)

    # Permissions
    allowed_commands = fields.Text(
        string='Slash Commands cho phép',
        help='Mỗi command 1 dòng, vd: morning_brief\nhunter_today\n* = tất cả'
    )
    allowed_actions = fields.Text(
        string='Actions cho phép',
        help='Mỗi action 1 dòng, vd: da_lien_he\ndoi_owner\n* = tất cả'
    )
    view_scope = fields.Selection([
        ('all', 'Toàn bộ'),
        ('hunter', 'Hunter'),
        ('farmer', 'Farmer'),
        ('finance', 'Finance'),
        ('ops', 'Ops/PM'),
    ], string='Phạm vi xem', default='all')

    user_ids = fields.One2many('masios.telegram_user', 'role_id', string='Người dùng')
    user_count = fields.Integer(compute='_compute_user_count', string='Số người dùng')

    @api.depends('user_ids')
    def _compute_user_count(self):
        for role in self:
            role.user_count = len(role.user_ids)

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Mã vai trò phải là duy nhất!')
    ]


class TelegramUser(models.Model):
    _name = 'masios.telegram_user'
    _description = 'Telegram User'
    _order = 'name'
    _rec_name = 'display_name'

    name = fields.Char(string='Họ tên', required=True)
    telegram_id = fields.Char(string='Telegram User ID', required=True, index=True)
    telegram_username = fields.Char(string='Telegram Username', help='@username')
    role_id = fields.Many2one('masios.telegram_role', string='Vai trò', required=True, ondelete='restrict')
    odoo_user_id = fields.Many2one('res.users', string='Tài khoản Odoo', help='Liên kết với user Odoo (tùy chọn)')
    active = fields.Boolean(default=True, string='Hoạt động')
    notes = fields.Text(string='Ghi chú')

    # Computed
    display_name = fields.Char(compute='_compute_display_name', store=True)
    role_code = fields.Char(related='role_id.code', store=True, string='Mã vai trò')

    # Override permissions (optional, overrides role defaults)
    extra_commands = fields.Text(string='Commands bổ sung', help='Commands thêm ngoài role (1 dòng/command)')
    blocked_commands = fields.Text(string='Commands chặn', help='Commands chặn dù role cho phép (1 dòng/command)')

    @api.depends('name', 'telegram_id', 'role_id.name')
    def _compute_display_name(self):
        for user in self:
            role = user.role_id.name or ''
            user.display_name = f"{user.name} [{role}] ({user.telegram_id})"

    _sql_constraints = [
        ('telegram_id_unique', 'unique(telegram_id)', 'Telegram ID phải là duy nhất!')
    ]

    def get_allowed_commands(self):
        """Return list of allowed commands for this user"""
        self.ensure_one()
        role = self.role_id

        # Parse role commands
        raw = (role.allowed_commands or '').strip()
        if raw == '*':
            commands = ['*']
        else:
            commands = [c.strip() for c in raw.split('\n') if c.strip()]

        # Add extra commands
        if self.extra_commands:
            extras = [c.strip() for c in self.extra_commands.split('\n') if c.strip()]
            commands.extend(extras)

        # Remove blocked commands
        if self.blocked_commands:
            blocked = {c.strip() for c in self.blocked_commands.split('\n') if c.strip()}
            if '*' not in commands:
                commands = [c for c in commands if c not in blocked]

        return commands

    def get_allowed_actions(self):
        """Return list of allowed actions for this user"""
        self.ensure_one()
        role = self.role_id
        raw = (role.allowed_actions or '').strip()
        if raw == '*':
            return ['*']
        return [a.strip() for a in raw.split('\n') if a.strip()]

    def check_command(self, command):
        """Check if user can execute this command. Returns (allowed, reason)"""
        self.ensure_one()
        if not self.active:
            return False, 'Tài khoản đã bị vô hiệu hóa'

        commands = self.get_allowed_commands()
        if '*' in commands:
            # Check blocked
            if self.blocked_commands:
                blocked = {c.strip() for c in self.blocked_commands.split('\n') if c.strip()}
                if command in blocked:
                    return False, f'Command /{command} bị chặn cho vai trò {self.role_id.name}'
            return True, 'OK'

        if command in commands:
            return True, 'OK'

        return False, f'Vai trò {self.role_id.name} không có quyền sử dụng /{command}'

    def check_action(self, action):
        """Check if user can perform this action. Returns (allowed, reason)"""
        self.ensure_one()
        if not self.active:
            return False, 'Tài khoản đã bị vô hiệu hóa'

        actions = self.get_allowed_actions()
        if '*' in actions:
            return True, 'OK'
        if action in actions:
            return True, 'OK'

        return False, f'Vai trò {self.role_id.name} không có quyền thực hiện {action}'
