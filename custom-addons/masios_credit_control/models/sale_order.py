from odoo import fields, models, _
from odoo.exceptions import UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    partner_credit_exceeded = fields.Boolean(
        related='partner_id.credit_exceeded',
        string='KH vượt hạn mức',
    )
    partner_classification = fields.Selection(
        related='partner_id.customer_classification',
        string='Phân loại KH',
    )

    def action_confirm(self):
        for order in self:
            partner = order.partner_id
            if partner.customer_classification == 'new':
                # KH mới: không cho phép có hóa đơn chưa thanh toán
                unpaid = self.env['account.move'].search_count([
                    ('partner_id', '=', partner.id),
                    ('move_type', '=', 'out_invoice'),
                    ('state', '=', 'posted'),
                    ('amount_residual', '>', 0),
                ])
                if unpaid > 0:
                    raise UserError(_(
                        "Khách hàng mới không được phép công nợ. "
                        "Vui lòng thanh toán hóa đơn trước khi xác nhận đơn hàng mới."
                    ))
            elif partner.customer_classification == 'old' and partner.credit_limit > 0:
                # KH cũ: kiểm tra hạn mức công nợ
                new_total = partner.outstanding_debt + order.amount_total
                if new_total > partner.credit_limit:
                    raise UserError(_(
                        "Vượt hạn mức công nợ!\n"
                        "Hạn mức: %(limit)s\n"
                        "Công nợ hiện tại: %(debt)s\n"
                        "Đơn hàng này: %(order)s\n"
                        "Hạn mức còn lại: %(available)s",
                        limit=f"{partner.credit_limit:,.0f}",
                        debt=f"{partner.outstanding_debt:,.0f}",
                        order=f"{order.amount_total:,.0f}",
                        available=f"{partner.credit_available:,.0f}",
                    ))
        return super().action_confirm()
