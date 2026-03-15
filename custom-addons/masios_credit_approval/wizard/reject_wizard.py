from odoo import fields, models


class CreditApprovalRejectWizard(models.TransientModel):
    _name = 'credit.approval.reject.wizard'
    _description = 'Từ chối phê duyệt công nợ'

    approval_id = fields.Many2one(
        'credit.approval.request',
        string='Yêu cầu',
        required=True,
    )
    reason = fields.Text(string='Lý do từ chối', required=True)

    def action_reject(self):
        self.ensure_one()
        self.approval_id.do_reject(
            rejected_by=self.env.user.name,
            reason=self.reason,
            via='web',
        )
        return {'type': 'ir.actions.act_window_close'}
