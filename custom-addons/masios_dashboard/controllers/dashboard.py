import json
from datetime import datetime, timedelta

from odoo import http
from odoo.http import request


class DashboardController(http.Controller):

    @http.route('/dashboard', type='http', auth='user', website=True)
    def dashboard_page(self, **kwargs):
        if not request.env.user.has_group('sales_team.group_sale_manager'):
            return request.redirect('/web')
        return request.render('masios_dashboard.dashboard_page')

    @http.route('/dashboard/data', type='http', auth='user', methods=['GET'], csrf=False)
    def dashboard_data(self, **kwargs):
        if not request.env.user.has_group('sales_team.group_sale_manager'):
            return request.make_json_response({'error': 'Access denied'}, status=403)
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
        Lead = request.env['crm.lead']
        data = Lead.read_group(
            [('type', '=', 'opportunity'), ('active', '=', True)],
            ['expected_revenue'],
            ['stage_id']
        )
        return [{
            'stage': item['stage_id'][1] if item['stage_id'] else 'Unknown',
            'count': item['stage_id_count'],
            'value': item['expected_revenue'] or 0,
        } for item in data]

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
        Partner = request.env['res.partner']
        # Get old customers with credit limits
        partners = Partner.search_read(
            [('customer_classification', '=', 'old'), ('credit_limit', '>', 0)],
            ['name', 'credit_limit', 'outstanding_debt', 'credit_exceeded'],
            limit=20
        )
        return [p for p in partners if p.get('credit_exceeded')]
