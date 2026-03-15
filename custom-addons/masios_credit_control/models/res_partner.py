from odoo import api, fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    customer_classification = fields.Selection([
        ('new', 'Khách hàng mới'),
        ('old', 'Khách hàng cũ'),
    ], string='Phân loại KH', default='new', tracking=True)

    credit_allowed = fields.Boolean(
        string='Cho phép công nợ',
        compute='_compute_credit_allowed',
        store=True,
    )
    credit_limit = fields.Monetary(
        string='Hạn mức công nợ',
        currency_field='currency_id',
        tracking=True,
    )
    outstanding_debt = fields.Monetary(
        string='Công nợ hiện tại',
        compute='_compute_outstanding_debt',
        store=True,
        currency_field='currency_id',
    )
    credit_available = fields.Monetary(
        string='Hạn mức còn lại',
        compute='_compute_outstanding_debt',
        store=True,
        currency_field='currency_id',
    )
    credit_exceeded = fields.Boolean(
        string='Vượt hạn mức',
        compute='_compute_outstanding_debt',
        store=True,
    )

    @api.depends('customer_classification')
    def _compute_credit_allowed(self):
        for partner in self:
            partner.credit_allowed = partner.customer_classification == 'old'

    @api.depends('credit_limit', 'customer_classification',
                 'invoice_ids.amount_residual', 'invoice_ids.state',
                 'invoice_ids.move_type', 'invoice_ids.payment_state')
    def _compute_outstanding_debt(self):
        # Batch: get all unpaid invoices for all partners at once
        real_ids = [pid for pid in self.ids if isinstance(pid, int)]
        if real_ids:
            invoices = self.env['account.move'].sudo().search_read(
                [('partner_id', 'in', real_ids), ('move_type', '=', 'out_invoice'),
                 ('state', '=', 'posted'), ('payment_state', '!=', 'paid')],
                ['partner_id', 'amount_residual']
            )
            # Sum by partner
            debt_map = {}
            for inv in invoices:
                pid = inv['partner_id'][0]
                debt_map[pid] = debt_map.get(pid, 0) + inv['amount_residual']
        else:
            debt_map = {}

        for partner in self:
            partner.outstanding_debt = debt_map.get(partner.id, 0)
            partner.credit_available = partner.credit_limit - partner.outstanding_debt
            partner.credit_exceeded = (
                partner.customer_classification == 'old'
                and partner.credit_limit > 0
                and partner.outstanding_debt > partner.credit_limit
            )
