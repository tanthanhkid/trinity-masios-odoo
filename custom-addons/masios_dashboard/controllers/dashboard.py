import json
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request


class DashboardController(http.Controller):

    @http.route('/dashboard', type='http', auth='user', website=True)
    def dashboard_page(self, **kwargs):
        return request.render('masios_dashboard.dashboard_page')

    @http.route('/dashboard/data', type='http', auth='user', methods=['GET'], csrf=False)
    def dashboard_data(self, **kwargs):
        data = {
            'kpis': self._get_kpis(),
            'pipeline': self._get_pipeline(),
            'recent_orders': self._get_recent_orders(),
            'invoices': self._get_invoices(),
            'credit_alerts': self._get_credit_alerts(),
        }
        return request.make_json_response(data)

    def _get_kpis(self):
        today = datetime.now()
        first_day = today.replace(day=1)

        # Pipeline value (active opportunities)
        leads = request.env['crm.lead'].search([
            ('type', '=', 'opportunity'),
            ('active', '=', True),
        ])
        pipeline_value = sum(leads.mapped('expected_revenue'))

        # Revenue this month (paid invoices)
        invoices = request.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('invoice_date', '>=', first_day.strftime('%Y-%m-%d')),
        ])
        monthly_revenue = sum(invoices.mapped('amount_total'))

        # Total outstanding debt
        unpaid = request.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
            ('amount_residual', '>', 0),
        ])
        total_debt = sum(unpaid.mapped('amount_residual'))

        # New leads this month
        new_leads = request.env['crm.lead'].search_count([
            ('create_date', '>=', first_day.strftime('%Y-%m-%d')),
        ])

        return {
            'pipeline_value': pipeline_value,
            'monthly_revenue': monthly_revenue,
            'total_debt': total_debt,
            'new_leads': new_leads,
        }

    def _get_pipeline(self):
        stages = request.env['crm.stage'].search([], order='sequence')
        result = []
        for stage in stages:
            leads = request.env['crm.lead'].search([
                ('stage_id', '=', stage.id),
                ('active', '=', True),
            ])
            result.append({
                'stage': stage.name,
                'count': len(leads),
                'value': sum(leads.mapped('expected_revenue')),
            })
        return result

    def _get_recent_orders(self):
        orders = request.env['sale.order'].search(
            [], limit=15, order='create_date desc'
        )
        result = []
        for o in orders:
            result.append({
                'id': o.id,
                'name': o.name,
                'partner': o.partner_id.name,
                'date': o.date_order.strftime('%Y-%m-%d') if o.date_order else '',
                'amount': o.amount_total,
                'state': o.state,
            })
        return result

    def _get_invoices(self):
        invoices = request.env['account.move'].search([
            ('move_type', '=', 'out_invoice'),
            ('state', '=', 'posted'),
        ], limit=15, order='invoice_date desc')
        result = []
        for inv in invoices:
            days_overdue = 0
            if inv.invoice_date_due and inv.amount_residual > 0:
                due = inv.invoice_date_due
                delta = datetime.now().date() - due
                days_overdue = max(0, delta.days)
            result.append({
                'id': inv.id,
                'name': inv.name,
                'partner': inv.partner_id.name,
                'date': inv.invoice_date.strftime('%Y-%m-%d') if inv.invoice_date else '',
                'amount': inv.amount_total,
                'residual': inv.amount_residual,
                'paid': inv.amount_residual == 0,
                'days_overdue': days_overdue,
            })
        return result

    def _get_credit_alerts(self):
        partners = request.env['res.partner'].search([
            ('customer_classification', '=', 'old'),
            ('credit_limit', '>', 0),
        ])
        alerts = []
        for p in partners:
            if p.credit_exceeded:
                alerts.append({
                    'id': p.id,
                    'name': p.name,
                    'credit_limit': p.credit_limit,
                    'outstanding_debt': p.outstanding_debt,
                    'exceeded_by': p.outstanding_debt - p.credit_limit,
                })
        return alerts
