from odoo import api, fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    credit_approval_ids = fields.One2many(
        'credit.approval.request', 'sale_order_id',
        string='Yêu cầu phê duyệt công nợ',
    )
    credit_approval_pending = fields.Boolean(
        string='Chờ phê duyệt công nợ',
        compute='_compute_credit_approval_pending',
    )

    @api.depends('credit_approval_ids.state')
    def _compute_credit_approval_pending(self):
        for order in self:
            order.credit_approval_pending = any(
                r.state == 'pending' for r in order.credit_approval_ids
            )

    def action_confirm(self):
        if self.env.context.get('bypass_credit_approval'):
            return super().action_confirm()

        ICP = self.env['ir.config_parameter'].sudo()
        threshold = float(ICP.get_param(
            'masios_credit_approval.threshold', '20000000'
        ))

        if threshold <= 0:
            return super().action_confirm()

        for order in self:
            partner = order.partner_id

            # Refresh debt computation
            partner.invalidate_recordset(['outstanding_debt'])
            partner._compute_outstanding_debt()

            new_total = partner.outstanding_debt + order.amount_total

            if new_total <= threshold:
                continue

            # Check if already approved
            existing = self.env['credit.approval.request'].search([
                ('sale_order_id', '=', order.id),
                ('state', '=', 'approved'),
            ], limit=1)
            if existing:
                # Already approved by CEO — bypass credit checks
                return order.with_context(
                    bypass_credit_approval=True,
                    bypass_credit_check=True,
                ).action_confirm()

            # Check if pending request already exists
            pending = self.env['credit.approval.request'].search([
                ('sale_order_id', '=', order.id),
                ('state', '=', 'pending'),
            ], limit=1)
            if pending:
                raise UserError(_(
                    "Đơn hàng %(order)s đang chờ CEO phê duyệt công nợ.\n"
                    "Mã yêu cầu: %(req)s\n"
                    "Vui lòng đợi CEO duyệt qua Telegram hoặc Odoo web.",
                    order=order.name,
                    req=pending.name,
                ))

            # Create approval request in a separate cursor so it persists
            # even when UserError rolls back the main transaction
            approval_name = self._create_approval_request_autonomous(
                order_id=order.id,
                outstanding_debt=partner.outstanding_debt,
                new_total_debt=new_total,
                threshold=threshold,
            )

            raise UserError(_(
                "⚠️ Công nợ vượt ngưỡng phê duyệt!\n\n"
                "Khách hàng: %(partner)s\n"
                "Công nợ hiện tại: %(debt)s VND\n"
                "Đơn hàng này: %(order_amount)s VND\n"
                "Tổng nợ mới: %(total)s VND\n"
                "Ngưỡng: %(threshold)s VND\n\n"
                "Yêu cầu phê duyệt (%(approval)s) đã được gửi cho CEO qua Telegram.\n"
                "Đơn hàng sẽ tự động xác nhận khi CEO duyệt.",
                partner=partner.name,
                debt=f"{partner.outstanding_debt:,.0f}",
                order_amount=f"{order.amount_total:,.0f}",
                total=f"{new_total:,.0f}",
                threshold=f"{threshold:,.0f}",
                approval=approval_name,
            ))

        return super().action_confirm()

    def _create_approval_request_autonomous(self, order_id, outstanding_debt, new_total_debt, threshold):
        """Create approval request in a new cursor so it survives UserError rollback."""
        approval_name = 'New'
        # Use a fresh cursor that commits independently
        with self.pool.cursor() as new_cr:
            new_env = api.Environment(new_cr, self.env.uid, self.env.context)
            req = new_env['credit.approval.request'].create({
                'sale_order_id': order_id,
                'outstanding_debt': outstanding_debt,
                'new_total_debt': new_total_debt,
                'approval_threshold': threshold,
            })
            approval_name = req.name
            # new_cr auto-commits on exit of the with block
        return approval_name
