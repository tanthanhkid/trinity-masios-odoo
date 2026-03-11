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
        currency_field='currency_id',
    )
    credit_available = fields.Monetary(
        string='Hạn mức còn lại',
        compute='_compute_outstanding_debt',
        currency_field='currency_id',
    )
    credit_exceeded = fields.Boolean(
        string='Vượt hạn mức',
        compute='_compute_outstanding_debt',
    )

    @api.depends('customer_classification')
    def _compute_credit_allowed(self):
        for partner in self:
            partner.credit_allowed = partner.customer_classification == 'old'

    @api.depends('credit_limit')
    def _compute_outstanding_debt(self):
        for partner in self:
            invoices = self.env['account.move'].search([
                ('partner_id', '=', partner.id),
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('amount_residual', '>', 0),
            ])
            partner.outstanding_debt = sum(invoices.mapped('amount_residual'))
            partner.credit_available = partner.credit_limit - partner.outstanding_debt
            partner.credit_exceeded = (
                partner.customer_classification == 'old'
                and partner.credit_limit > 0
                and partner.outstanding_debt > partner.credit_limit
            )
