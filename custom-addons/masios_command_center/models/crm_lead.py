from odoo import api, fields, models


class CrmLead(models.Model):
    _inherit = 'crm.lead'

    # === SLA tracking ===
    sla_hours = fields.Float(
        string='SLA (giờ)',
        default=4.0,
        help='Thời gian tối đa để liên hệ lần đầu (mặc định 4 giờ)',
    )
    first_touch_date = fields.Datetime(
        string='Ngày liên hệ đầu tiên',
        tracking=True,
        help='Thời điểm nhân viên liên hệ lead lần đầu',
    )
    sla_status = fields.Selection([
        ('ok', 'Đạt SLA'),
        ('warning', 'Cảnh báo'),
        ('breached', 'Vi phạm SLA'),
    ], string='Trạng thái SLA', compute='_compute_sla_status')

    # === Lead source ===
    lead_source = fields.Selection([
        ('website', 'Website'),
        ('referral', 'Giới thiệu'),
        ('cold_call', 'Gọi lạnh'),
        ('social', 'Mạng xã hội'),
        ('event', 'Sự kiện'),
        ('other', 'Khác'),
    ], string='Nguồn lead', tracking=True)

    # === Hunter owner ===
    hunter_owner_id = fields.Many2one(
        'res.users',
        string='Hunter phụ trách',
        tracking=True,
        help='Nhân viên Hunter chịu trách nhiệm lead này',
    )

    def _compute_sla_status(self):
        """Tính trạng thái SLA dựa trên thời gian từ tạo lead đến first_touch.
        - ok: đã liên hệ trong vòng sla_hours
        - warning: chưa liên hệ, đã qua sla_hours nhưng chưa quá 24h
        - breached: chưa liên hệ quá 24h, HOẶC đã liên hệ nhưng trễ hơn sla_hours
        """
        now = fields.Datetime.now()
        for lead in self:
            if not lead.create_date:
                lead.sla_status = 'ok'
                continue

            if lead.first_touch_date:
                # Đã liên hệ — liên hệ đúng hạn thì ok, trễ thì breached
                hours_elapsed = (lead.first_touch_date - lead.create_date).total_seconds() / 3600
                if hours_elapsed <= (lead.sla_hours or 4.0):
                    lead.sla_status = 'ok'
                else:
                    lead.sla_status = 'breached'
            else:
                # Chưa liên hệ — kiểm tra thời gian đã trôi qua
                hours_elapsed = (now - lead.create_date).total_seconds() / 3600
                if hours_elapsed <= (lead.sla_hours or 4.0):
                    lead.sla_status = 'ok'
                elif hours_elapsed <= 24:
                    lead.sla_status = 'warning'
                else:
                    lead.sla_status = 'breached'
