import json
import logging
import urllib.request

from odoo import api, fields, models, _
from odoo.exceptions import UserError

logger = logging.getLogger(__name__)


class CreditApprovalRequest(models.Model):
    _name = 'credit.approval.request'
    _description = 'Yêu cầu phê duyệt công nợ'
    _inherit = ['mail.thread']
    _order = 'create_date desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Mã yêu cầu',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    sale_order_id = fields.Many2one(
        'sale.order',
        string='Đơn hàng',
        required=True,
        ondelete='cascade',
    )
    partner_id = fields.Many2one(
        related='sale_order_id.partner_id',
        string='Khách hàng',
        store=True,
    )
    salesperson_id = fields.Many2one(
        related='sale_order_id.user_id',
        string='Nhân viên bán hàng',
        store=True,
    )
    amount_total = fields.Monetary(
        related='sale_order_id.amount_total',
        string='Giá trị đơn hàng',
        store=True,
        currency_field='currency_id',
    )
    currency_id = fields.Many2one(
        related='sale_order_id.currency_id',
        store=True,
    )
    outstanding_debt = fields.Monetary(
        string='Công nợ hiện tại',
        currency_field='currency_id',
    )
    new_total_debt = fields.Monetary(
        string='Tổng nợ sau đơn hàng',
        currency_field='currency_id',
    )
    approval_threshold = fields.Monetary(
        string='Ngưỡng phê duyệt',
        currency_field='currency_id',
    )
    state = fields.Selection([
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
    ], string='Trạng thái', default='pending', tracking=True)
    approved_by = fields.Char(string='Người duyệt')
    approved_via = fields.Selection([
        ('telegram', 'Telegram'),
        ('web', 'Odoo Web'),
    ], string='Duyệt qua')
    approved_date = fields.Datetime(string='Thời gian duyệt')
    reject_reason = fields.Text(string='Lý do từ chối')
    telegram_message_id = fields.Char(string='Telegram Message ID')
    telegram_chat_id = fields.Char(string='Telegram Chat ID')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'credit.approval.request'
                ) or _('New')
        records = super().create(vals_list)
        for rec in records:
            rec._send_telegram_notification()
        return records

    def action_approve(self):
        """Button action for web approval."""
        self.ensure_one()
        return self.do_approve(approved_by=self.env.user.name, via='web')

    def do_approve(self, approved_by='', via='web'):
        """Approve the request and auto-confirm the sale order."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Yêu cầu này đã được xử lý.'))

        self.write({
            'state': 'approved',
            'approved_by': approved_by or self.env.user.name,
            'approved_via': via,
            'approved_date': fields.Datetime.now(),
        })

        # Auto-confirm the sale order (bypass credit checks)
        if self.sale_order_id.state in ('draft', 'sent'):
            self.sale_order_id.with_context(
                bypass_credit_approval=True,
                bypass_credit_check=True,
            ).action_confirm()

        return True

        # Update Telegram message
        self._update_telegram_message('approved')

        # Log to chatter on the sale order
        via_label = dict(self._fields['approved_via'].selection).get(via, via)
        self.sale_order_id.message_post(
            body=_(
                "✅ Công nợ được phê duyệt bởi %(by)s qua %(via)s.\n"
                "Yêu cầu: %(name)s",
                by=self.approved_by,
                via=via_label,
                name=self.name,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

    def action_reject_wizard(self):
        """Open reject reason wizard."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Lý do từ chối',
            'res_model': 'credit.approval.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_approval_id': self.id},
        }

    def do_reject(self, rejected_by='', reason='', via='web'):
        """Reject the request. Sale order stays in draft."""
        self.ensure_one()
        if self.state != 'pending':
            raise UserError(_('Yêu cầu này đã được xử lý.'))

        self.write({
            'state': 'rejected',
            'approved_by': rejected_by or self.env.user.name,
            'approved_via': via,
            'approved_date': fields.Datetime.now(),
            'reject_reason': reason,
        })

        # Update Telegram message
        self._update_telegram_message('rejected')

        # Log to chatter on the sale order
        reason_text = f"\nLý do: {reason}" if reason else ""
        via_label = dict(self._fields['approved_via'].selection).get(via, via)
        self.sale_order_id.message_post(
            body=_(
                "❌ Công nợ bị từ chối bởi %(by)s qua %(via)s.%(reason)s\n"
                "Yêu cầu: %(name)s",
                by=self.approved_by,
                via=via_label,
                reason=reason_text,
                name=self.name,
            ),
            message_type='comment',
            subtype_xmlid='mail.mt_note',
        )

        return True

    # --- Telegram integration ---

    def _get_telegram_config(self):
        """Get Telegram bot token and CEO chat ID from system parameters."""
        ICP = self.env['ir.config_parameter'].sudo()
        bot_token = ICP.get_param('masios_credit_approval.telegram_bot_token', '')
        ceo_chat_id = ICP.get_param('masios_credit_approval.telegram_ceo_chat_id', '')
        return bot_token, ceo_chat_id

    def _send_telegram_notification(self):
        """Send approval request notification to CEO via Telegram Bot API."""
        bot_token, ceo_chat_id = self._get_telegram_config()
        if not bot_token or not ceo_chat_id:
            logger.warning(
                "Telegram config missing (bot_token=%s, ceo_chat_id=%s) — skipping notification for %s",
                bool(bot_token), bool(ceo_chat_id), self.name,
            )
            return

        partner = self.partner_id
        so = self.sale_order_id
        salesperson = self.salesperson_id.name or 'N/A'

        text = (
            f"🔔 <b>YÊU CẦU PHÊ DUYỆT CÔNG NỢ</b>\n\n"
            f"📋 Mã: <b>{self.name}</b>\n"
            f"📦 Đơn hàng: <b>{so.name}</b>\n"
            f"🏢 Khách hàng: <b>{partner.name}</b>\n"
            f"👤 Nhân viên: <b>{salesperson}</b>\n\n"
            f"💰 Giá trị đơn: <b>{self.amount_total:,.0f}</b> VND\n"
            f"💳 Công nợ hiện tại: <b>{self.outstanding_debt:,.0f}</b> VND\n"
            f"📊 Tổng nợ sau đơn: <b>{self.new_total_debt:,.0f}</b> VND\n"
            f"⚠️ Ngưỡng: <b>{self.approval_threshold:,.0f}</b> VND\n\n"
            f"Vui lòng duyệt hoặc từ chối."
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "✅ Duyệt", "callback_data": f"credit_approve_{self.id}"},
                {"text": "❌ Từ chối", "callback_data": f"credit_reject_{self.id}"},
            ]]
        }

        payload = {
            "chat_id": ceo_chat_id,
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard),
        }

        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, data=data,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode('utf-8'))
                if result.get('ok'):
                    msg_id = result['result']['message_id']
                    self.write({
                        'telegram_message_id': str(msg_id),
                        'telegram_chat_id': ceo_chat_id,
                    })
                    logger.info("Telegram notification sent for %s (msg_id=%s)", self.name, msg_id)
                else:
                    logger.error("Telegram API error for %s: %s", self.name, result)
        except Exception as e:
            logger.error("Failed to send Telegram notification for %s: %s", self.name, e)

    def _update_telegram_message(self, new_state):
        """Update the original Telegram message after approval/rejection."""
        bot_token, _ = self._get_telegram_config()
        if not bot_token or not self.telegram_message_id or not self.telegram_chat_id:
            return

        partner = self.partner_id
        so = self.sale_order_id

        if new_state == 'approved':
            status = "✅ ĐÃ DUYỆT"
            by_text = f"Duyệt bởi: {self.approved_by}"
        else:
            status = "❌ ĐÃ TỪ CHỐI"
            by_text = f"Từ chối bởi: {self.approved_by}"
            if self.reject_reason:
                by_text += f"\nLý do: {self.reject_reason}"

        text = (
            f"{'✅' if new_state == 'approved' else '❌'} <b>PHÊ DUYỆT CÔNG NỢ — {status}</b>\n\n"
            f"📋 Mã: <b>{self.name}</b>\n"
            f"📦 Đơn hàng: <b>{so.name}</b>\n"
            f"🏢 Khách hàng: <b>{partner.name}</b>\n\n"
            f"💰 Giá trị đơn: <b>{self.amount_total:,.0f}</b> VND\n"
            f"💳 Công nợ: <b>{self.outstanding_debt:,.0f}</b> VND\n\n"
            f"{by_text}"
        )

        payload = {
            "chat_id": self.telegram_chat_id,
            "message_id": int(self.telegram_message_id),
            "text": text,
            "parse_mode": "HTML",
        }

        url = f"https://api.telegram.org/bot{bot_token}/editMessageText"
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                url, data=data,
                headers={'Content-Type': 'application/json'},
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
            logger.info("Telegram message updated for %s → %s", self.name, new_state)
        except Exception as e:
            logger.error("Failed to update Telegram message for %s: %s", self.name, e)
