from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = 'project.task'

    # === Phân loại task cho Command Center ===
    task_category = fields.Selection([
        ('follow_up', 'Theo dõi'),
        ('collection', 'Thu nợ'),
        ('care', 'Chăm sóc KH'),
        ('escalation', 'Báo cáo cấp trên'),
        ('ops', 'Vận hành'),
        ('other', 'Khác'),
    ], string='Phân loại task', tracking=True)

    related_partner_id = fields.Many2one(
        'res.partner',
        string='Khách hàng liên quan',
        tracking=True,
        help='Khách hàng mà task này liên quan đến',
    )

    impact_level = fields.Selection([
        ('low', 'Thấp'),
        ('medium', 'Trung bình'),
        ('high', 'Cao'),
        ('critical', 'Nghiêm trọng'),
    ], string='Mức độ ảnh hưởng', default='medium', tracking=True)

    source_alert_code = fields.Char(
        string='Mã cảnh báo nguồn',
        help='Mã alert từ Command Center, ví dụ: H02, F01, A03',
    )
