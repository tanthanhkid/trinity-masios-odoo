import json
import logging
from datetime import datetime, timedelta

from odoo import fields, http
from odoo.http import request

_logger = logging.getLogger(__name__)


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
        data = {}
        for key, getter in [
            ('kpis', self._get_kpis),
            ('pipeline', self._get_pipeline),
            ('recent_orders', self._get_recent_orders),
            ('invoices', self._get_invoices),
            ('credit_alerts', self._get_credit_alerts),
        ]:
            try:
                data[key] = getter()
            except Exception as e:
                _logger.error("Dashboard %s failed: %s", key, e, exc_info=True)
                data[key] = [] if key != 'kpis' else {
                    'pipeline_value': 0, 'monthly_revenue': 0,
                    'total_debt': 0, 'new_leads': 0,
                }
        return request.make_json_response(data)

    def _get_kpis(self):
        today = fields.Date.today()
        first_day = today.replace(day=1)
        first_day_str = first_day.isoformat()

        # Pipeline value (active opportunities) — aggregate in DB
        pipeline_data = request.env['crm.lead'].read_group(
            [('type', '=', 'opportunity'), ('active', '=', True)],
            ['expected_revenue:sum'],
            [],
        )
        pipeline_value = pipeline_data[0]['expected_revenue'] or 0 if pipeline_data else 0

        # Revenue this month (posted invoices) — aggregate in DB
        revenue_data = request.env['account.move'].read_group(
            [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
             ('invoice_date', '>=', first_day_str)],
            ['amount_total:sum'],
            [],
        )
        monthly_revenue = revenue_data[0]['amount_total'] or 0 if revenue_data else 0

        # Total outstanding debt — aggregate in DB
        debt_data = request.env['account.move'].read_group(
            [('move_type', '=', 'out_invoice'), ('state', '=', 'posted'),
             ('amount_residual', '>', 0)],
            ['amount_residual:sum'],
            [],
        )
        total_debt = debt_data[0]['amount_residual'] or 0 if debt_data else 0

        # New leads this month
        new_leads = request.env['crm.lead'].search_count([
            ('create_date', '>=', first_day_str),
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
            'count': item.get('__count', item.get('stage_id_count', 0)),
            'value': item['expected_revenue'] or 0,
        } for item in data]

    def _get_recent_orders(self):
        orders = request.env['sale.order'].search_read(
            [], fields=['name', 'partner_id', 'date_order', 'amount_total', 'state'],
            limit=15, order='create_date desc'
        )
        return [{
            'id': o['id'],
            'name': o['name'],
            'partner': o['partner_id'][1] if o['partner_id'] else '',
            'date': str(o['date_order'] or '')[:10],
            'amount': o['amount_total'],
            'state': o['state'],
        } for o in orders]

    def _get_invoices(self):
        invoices = request.env['account.move'].search_read(
            [('move_type', '=', 'out_invoice'), ('state', '=', 'posted')],
            fields=['name', 'partner_id', 'invoice_date', 'invoice_date_due',
                    'amount_total', 'amount_residual'],
            limit=15, order='invoice_date desc'
        )
        today = fields.Date.today()
        result = []
        for inv in invoices:
            days_overdue = 0
            if inv['invoice_date_due'] and inv['amount_residual'] > 0:
                due = inv['invoice_date_due']
                if isinstance(due, str):
                    due = datetime.strptime(due[:10], '%Y-%m-%d').date()
                days_overdue = max(0, (today - due).days)
            result.append({
                'id': inv['id'],
                'name': inv['name'],
                'partner': inv['partner_id'][1] if inv['partner_id'] else '',
                'date': str(inv['invoice_date'] or '')[:10],
                'amount': inv['amount_total'],
                'residual': inv['amount_residual'],
                'paid': inv['amount_residual'] == 0,
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
        alerts = []
        for p in partners:
            if p.get('credit_exceeded'):
                p['exceeded_by'] = p.get('outstanding_debt', 0) - p.get('credit_limit', 0)
                alerts.append(p)
        return alerts
