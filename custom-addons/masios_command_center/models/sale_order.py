from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # === Loại đơn hàng: đơn đầu tiên hay đơn lặp ===
    order_type = fields.Selection([
        ('first_order', 'Đơn đầu tiên'),
        ('repeat_order', 'Đơn lặp lại'),
    ], string='Loại đơn hàng', compute='_compute_order_type', store=True)

    is_first_order = fields.Boolean(
        string='Là đơn đầu tiên',
        compute='_compute_order_type',
        store=True,
    )

    @api.depends('partner_id', 'state')
    def _compute_order_type(self):
        """Xác định đơn hàng đầu tiên hay đơn lặp lại.
        Đơn đầu tiên = không có SO nào khác đã xác nhận trước đó cho cùng KH.
        """
        for order in self:
            if not order.partner_id or order.state not in ('sale', 'done'):
                order.order_type = False
                order.is_first_order = False
                continue

            # Đếm SO đã xác nhận trước đó (không tính chính nó)
            earlier_count = self.env['sale.order'].search_count([
                ('partner_id', '=', order.partner_id.id),
                ('state', 'in', ('sale', 'done')),
                ('id', '!=', order.id),
                ('date_order', '<', order.date_order),
            ])
            if earlier_count == 0:
                order.order_type = 'first_order'
                order.is_first_order = True
            else:
                order.order_type = 'repeat_order'
                order.is_first_order = False
