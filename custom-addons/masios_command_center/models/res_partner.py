from odoo import api, fields, models
from datetime import timedelta


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # === VIP Level ===
    vip_level = fields.Selection([
        ('none', 'Không'),
        ('silver', 'Bạc'),
        ('gold', 'Vàng'),
        ('platinum', 'Bạch kim'),
    ], string='Hạng VIP', default='none', tracking=True)

    # === Lịch sử đơn hàng (computed) ===
    last_order_date = fields.Date(
        string='Ngày đặt hàng gần nhất',
        compute='_compute_order_dates',
        store=True,
    )
    first_order_date = fields.Date(
        string='Ngày đặt hàng đầu tiên',
        compute='_compute_order_dates',
        store=True,
    )

    # === Chu kỳ mua hàng (computed) ===
    repeat_cycle_days = fields.Integer(
        string='Chu kỳ mua hàng TB (ngày)',
        compute='_compute_repeat_cycle',
        store=True,
        help='Trung bình số ngày giữa các đơn hàng đã xác nhận',
    )
    expected_reorder_date = fields.Date(
        string='Ngày dự kiến đặt lại',
        compute='_compute_expected_reorder',
        store=True,
    )

    # === Sleeping customer detection ===
    days_since_last_order = fields.Integer(
        string='Số ngày từ đơn cuối',
        compute='_compute_sleeping_status',
    )
    is_sleeping = fields.Boolean(
        string='Khách đang ngủ',
        compute='_compute_sleeping_status',
        help='KH không đặt hàng >= 30 ngày',
    )
    sleeping_bucket = fields.Selection([
        ('none', 'Hoạt động'),
        ('30-59', '30-59 ngày'),
        ('60-89', '60-89 ngày'),
        ('90+', '90+ ngày'),
    ], string='Nhóm ngủ', compute='_compute_sleeping_status')

    # === Hunter/Farmer assignment ===
    hunter_farmer_type = fields.Selection([
        ('hunter', 'Hunter'),
        ('farmer', 'Farmer'),
    ], string='Loại team', compute='_compute_hunter_farmer', store=True,
        help='Dựa trên team của đơn hàng gần nhất')

    # === AR Aging (computed từ hóa đơn chưa thanh toán) ===
    ar_aging_bucket = fields.Selection([
        ('current', 'Chưa đến hạn'),
        ('1-30', '1-30 ngày'),
        ('31-60', '31-60 ngày'),
        ('61-90', '61-90 ngày'),
        ('90+', '90+ ngày'),
    ], string='Nhóm tuổi nợ', compute='_compute_ar_aging')

    @api.depends('sale_order_ids.state', 'sale_order_ids.date_order')
    def _compute_order_dates(self):
        """Tính ngày đặt hàng đầu tiên và gần nhất từ SO đã xác nhận."""
        # Batch query: lấy min/max date_order cho tất cả partner cùng lúc
        real_ids = [pid for pid in self.ids if isinstance(pid, int)]
        date_map = {}
        if real_ids:
            self.env.cr.execute("""
                SELECT partner_id,
                       MIN(date_order)::date AS first_date,
                       MAX(date_order)::date AS last_date
                FROM sale_order
                WHERE partner_id IN %s
                  AND state IN ('sale', 'done')
                GROUP BY partner_id
            """, (tuple(real_ids),))
            for row in self.env.cr.dictfetchall():
                date_map[row['partner_id']] = (row['first_date'], row['last_date'])

        for partner in self:
            dates = date_map.get(partner.id)
            if dates:
                partner.first_order_date = dates[0]
                partner.last_order_date = dates[1]
            else:
                partner.first_order_date = False
                partner.last_order_date = False

    @api.depends('sale_order_ids.state', 'sale_order_ids.date_order')
    def _compute_repeat_cycle(self):
        """Tính trung bình số ngày giữa các đơn hàng liên tiếp."""
        real_ids = [pid for pid in self.ids if isinstance(pid, int)]
        cycle_map = {}
        if real_ids:
            # Lấy tất cả ngày đặt hàng đã xác nhận, sắp xếp theo thời gian
            self.env.cr.execute("""
                SELECT partner_id, date_order::date AS order_date
                FROM sale_order
                WHERE partner_id IN %s
                  AND state IN ('sale', 'done')
                ORDER BY partner_id, date_order
            """, (tuple(real_ids),))
            # Nhóm theo partner
            from collections import defaultdict
            partner_dates = defaultdict(list)
            for row in self.env.cr.dictfetchall():
                partner_dates[row['partner_id']].append(row['order_date'])

            for pid, dates in partner_dates.items():
                if len(dates) >= 2:
                    # Tính khoảng cách giữa các đơn liên tiếp
                    gaps = [(dates[i+1] - dates[i]).days for i in range(len(dates)-1)]
                    # Loại bỏ gap = 0 (nhiều đơn cùng ngày)
                    gaps = [g for g in gaps if g > 0]
                    if gaps:
                        cycle_map[pid] = sum(gaps) // len(gaps)

        for partner in self:
            partner.repeat_cycle_days = cycle_map.get(partner.id, 0)

    @api.depends('last_order_date', 'repeat_cycle_days')
    def _compute_expected_reorder(self):
        """Dự kiến ngày đặt hàng tiếp theo = last_order_date + repeat_cycle_days."""
        for partner in self:
            if partner.last_order_date and partner.repeat_cycle_days > 0:
                partner.expected_reorder_date = (
                    partner.last_order_date + timedelta(days=partner.repeat_cycle_days)
                )
            else:
                partner.expected_reorder_date = False

    def _compute_sleeping_status(self):
        """Tính trạng thái ngủ: KH không đặt hàng >= 30 ngày."""
        today = fields.Date.context_today(self)
        for partner in self:
            if partner.last_order_date:
                delta = (today - partner.last_order_date).days
            else:
                delta = 0
            partner.days_since_last_order = delta
            partner.is_sleeping = delta >= 30

            if delta < 30:
                partner.sleeping_bucket = 'none'
            elif delta < 60:
                partner.sleeping_bucket = '30-59'
            elif delta < 90:
                partner.sleeping_bucket = '60-89'
            else:
                partner.sleeping_bucket = '90+'

    @api.depends('sale_order_ids.state', 'sale_order_ids.team_id')
    def _compute_hunter_farmer(self):
        """Xác định loại team dựa trên team của đơn hàng gần nhất."""
        real_ids = [pid for pid in self.ids if isinstance(pid, int)]
        team_map = {}
        if real_ids:
            # Lấy team_id của SO mới nhất (đã xác nhận) cho mỗi partner
            self.env.cr.execute("""
                SELECT DISTINCT ON (partner_id)
                       partner_id, team_id
                FROM sale_order
                WHERE partner_id IN %s
                  AND state IN ('sale', 'done')
                  AND team_id IS NOT NULL
                ORDER BY partner_id, date_order DESC
            """, (tuple(real_ids),))
            for row in self.env.cr.dictfetchall():
                team_map[row['partner_id']] = row['team_id']

        # Lấy XML IDs của Hunter/Farmer teams
        hunter_team = self.env.ref(
            'masios_command_center.team_hunter', raise_if_not_found=False
        )
        farmer_team = self.env.ref(
            'masios_command_center.team_farmer', raise_if_not_found=False
        )
        hunter_id = hunter_team.id if hunter_team else None
        farmer_id = farmer_team.id if farmer_team else None

        for partner in self:
            tid = team_map.get(partner.id)
            if tid == hunter_id:
                partner.hunter_farmer_type = 'hunter'
            elif tid == farmer_id:
                partner.hunter_farmer_type = 'farmer'
            else:
                partner.hunter_farmer_type = False

    def _compute_ar_aging(self):
        """Tính nhóm tuổi nợ dựa trên hóa đơn quá hạn lâu nhất."""
        today = fields.Date.context_today(self)
        real_ids = [pid for pid in self.ids if isinstance(pid, int)]
        aging_map = {}
        if real_ids:
            # Lấy invoice_date_due sớm nhất của hóa đơn chưa thanh toán
            self.env.cr.execute("""
                SELECT partner_id,
                       MIN(invoice_date_due) AS oldest_due
                FROM account_move
                WHERE partner_id IN %s
                  AND move_type = 'out_invoice'
                  AND state = 'posted'
                  AND payment_state NOT IN ('paid', 'in_payment', 'reversed')
                  AND invoice_date_due IS NOT NULL
                GROUP BY partner_id
            """, (tuple(real_ids),))
            for row in self.env.cr.dictfetchall():
                if row['oldest_due']:
                    aging_map[row['partner_id']] = (today - row['oldest_due']).days

        for partner in self:
            days = aging_map.get(partner.id, -1)
            if days < 0:
                # Không có hóa đơn quá hạn hoặc không có hóa đơn
                partner.ar_aging_bucket = False
            elif days <= 0:
                partner.ar_aging_bucket = 'current'
            elif days <= 30:
                partner.ar_aging_bucket = '1-30'
            elif days <= 60:
                partner.ar_aging_bucket = '31-60'
            elif days <= 90:
                partner.ar_aging_bucket = '61-90'
            else:
                partner.ar_aging_bucket = '90+'
