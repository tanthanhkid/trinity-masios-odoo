from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    credit_approval_threshold = fields.Float(
        string='Ngưỡng phê duyệt công nợ (VND)',
        config_parameter='masios_credit_approval.threshold',
        default=20000000,
        help='Khi tổng công nợ của khách hàng vượt số này, đơn hàng cần CEO phê duyệt.',
    )
    credit_approval_telegram_bot_token = fields.Char(
        string='Telegram Bot Token',
        config_parameter='masios_credit_approval.telegram_bot_token',
        help='Token của Telegram Bot để gửi thông báo phê duyệt.',
    )
    credit_approval_ceo_chat_id = fields.Char(
        string='CEO Telegram Chat ID',
        config_parameter='masios_credit_approval.telegram_ceo_chat_id',
        help='Chat ID của CEO trên Telegram để nhận thông báo phê duyệt.',
    )
