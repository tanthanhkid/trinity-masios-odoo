"""Unit tests for format_command router and key format_* functions."""
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from formatter import format_command, format_morning_brief, format_credit, \
    format_pending_approvals, format_kpi, format_pipeline, format_congno, \
    format_task_overdue, format_revenue_today


class TestFormatCommand:
    def test_known_command(self):
        result = format_command("/kpi", '{"monthly_revenue": 100000000}')
        assert result is not None
        assert "KPI" in result

    def test_unknown_command(self):
        assert format_command("/nonexistent", "{}") is None

    def test_formatter_exception(self):
        # Invalid JSON should not crash, should return error message
        result = format_command("/kpi", "not json at all")
        assert result is not None  # Should return fallback, not None


class TestFormatMorningBrief:
    def test_full_data(self):
        data = json.dumps({
            "date": "2026-03-15",
            "hunter_kpis": {"leads_new_this_month": 10, "leads_won_this_month": 3, "first_order_revenue": 50000000},
            "farmer_kpis": {"repeat_order_revenue": 30000000, "sleeping_customers_90d": 5},
            "ar_task_summary": {"total_receivable": 200000000, "overdue_invoices": 3, "due_within_7d": 2},
            "top_alerts": [{"message": "SLA breach"}],
        })
        result = format_morning_brief(data)
        assert "MORNING BRIEF" in result
        assert "Hunter" in result
        assert "Farmer" in result
        assert "Công nợ" in result

    def test_empty_data(self):
        result = format_morning_brief("{}")
        # Empty dict is falsy in _safe_json → returns "Không có dữ liệu"
        assert "MORNING BRIEF" in result

    def test_no_data(self):
        result = format_morning_brief('""')
        assert "Không có dữ liệu" in result


class TestFormatRevenueToday:
    def test_with_breakdown(self):
        data = json.dumps({
            "date": "2026-03-15",
            "total_revenue": 125000000,
            "breakdown": [
                {"team": "Hunter", "amount": 80000000, "count": 5},
                {"team": "Farmer", "amount": 45000000, "count": 3},
            ],
        })
        result = format_revenue_today(data)
        assert "Doanh số hôm nay" in result
        assert "Hunter" in result
        assert "Farmer" in result

    def test_zero_revenue(self):
        data = json.dumps({"date": "2026-03-15", "total_revenue": 0, "breakdown": []})
        result = format_revenue_today(data)
        assert "Chưa có dữ liệu" in result


class TestFormatKpi:
    def test_all_fields(self):
        data = json.dumps({
            "monthly_revenue": 500000000,
            "pipeline_value": 1200000000,
            "total_debt": 300000000,
            "new_leads": 15,
        })
        result = format_kpi(data)
        assert "KPI" in result
        assert "500" in result or "triệu" in result

    def test_no_matching_fields(self):
        result = format_kpi('{"unknown_field": 42}')
        assert "KPI" in result
        # Should show defaults
        assert "0" in result


class TestFormatPipeline:
    def test_stages(self):
        data = json.dumps({"stages": [
            {"stage": "New", "count": 5, "value": 50000000},
            {"stage": "Won", "count": 2, "value": 100000000},
        ]})
        result = format_pipeline(data)
        assert "PIPELINE" in result
        assert "New" in result
        assert "Tổng" in result

    def test_empty_pipeline(self):
        result = format_pipeline('{"stages": []}')
        assert "Không có dữ liệu" in result


class TestFormatCongno:
    def test_overdue(self):
        data = json.dumps({
            "records": [
                {"partner": "ABC Corp", "amount_residual": 50000000, "days_overdue": 15, "name": "INV/001"},
            ],
            "total_amount": 50000000,
        })
        result = format_congno(data, "overdue")
        assert "QUÁ HẠN" in result
        assert "ABC Corp" in result

    def test_due_soon(self):
        result = format_congno('{"records": [], "total_amount": 0}', "due_soon")
        assert "ĐẾN HẠN" in result


class TestFormatTaskOverdue:
    def test_with_tasks(self):
        data = json.dumps({"records": [
            {"name": "Follow up client", "days_overdue": 3, "project_id": [1, "Sales"]},
        ]})
        result = format_task_overdue(data)
        assert "TASK QUÁ HẠN" in result
        assert "Follow up client" in result
        assert "Sales" in result

    def test_no_tasks(self):
        result = format_task_overdue('{"records": []}')
        assert "Không có task quá hạn" in result

    def test_project_as_string(self):
        data = json.dumps({"records": [
            {"name": "Task 1", "days_overdue": 5, "project": "Marketing"},
        ]})
        result = format_task_overdue(data)
        assert "Marketing" in result or "Task 1" in result


class TestFormatCredit:
    def test_customers_list(self):
        data = json.dumps([
            {"name": "ABC", "credit_limit": 100000000, "outstanding_debt": 150000000, "credit_available": -50000000},
        ])
        result = format_credit(data)
        assert "CREDIT LIMIT" in result
        assert "ABC" in result

    def test_no_customers(self):
        result = format_credit('{"customers": []}')
        assert "Không có khách" in result


class TestFormatPendingApprovals:
    def test_with_requests(self):
        data = json.dumps({
            "pending_count": 1,
            "requests": [{
                "name": "APR/0001",
                "sale_order_id": [1, "S00001"],
                "partner_id": [14, "ABC Tech"],
                "amount_total": 5000000,
                "outstanding_debt": 25000000,
                "new_total_debt": 30000000,
            }],
        })
        result = format_pending_approvals(data)
        assert "PHÊ DUYỆT" in result
        assert "APR/0001" in result
        assert "ABC Tech" in result

    def test_empty(self):
        result = format_pending_approvals('{"pending_count": 0, "requests": []}')
        assert "Không có yêu cầu" in result
