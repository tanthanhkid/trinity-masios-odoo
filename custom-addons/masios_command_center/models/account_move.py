from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    # === Dispute tracking ===
    dispute_status = fields.Selection([
        ('none', 'Không có'),
        ('disputed', 'Đang tranh chấp'),
        ('resolved', 'Đã giải quyết'),
    ], string='Trạng thái tranh chấp', default='none', tracking=True)

    dispute_note = fields.Text(
        string='Ghi chú tranh chấp',
        help='Mô tả chi tiết vấn đề tranh chấp',
    )

    # === Collection tracking ===
    collection_status = fields.Selection([
        ('none', 'Chưa xử lý'),
        ('reminded', 'Đã nhắc nợ'),
        ('promised', 'Đã hẹn trả'),
        ('collected', 'Đã thu'),
    ], string='Trạng thái thu nợ', default='none', tracking=True)

    # === Days overdue ===
    days_overdue = fields.Integer(
        string='Số ngày quá hạn',
        compute='_compute_days_overdue',
    )

    def _compute_days_overdue(self):
        """Tính số ngày quá hạn = today - invoice_date_due (chỉ cho hóa đơn chưa thanh toán)."""
        today = fields.Date.context_today(self)
        for move in self:
            if (move.move_type == 'out_invoice'
                    and move.state == 'posted'
                    and move.payment_state not in ('paid', 'in_payment', 'reversed')
                    and move.invoice_date_due):
                delta = (today - move.invoice_date_due).days
                move.days_overdue = max(delta, 0)
            else:
                move.days_overdue = 0
