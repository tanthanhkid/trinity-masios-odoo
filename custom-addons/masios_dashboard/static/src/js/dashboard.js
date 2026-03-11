document.addEventListener('DOMContentLoaded', function () {
    const dashboard = document.getElementById('ceo-dashboard');
    if (!dashboard) return;

    function fmt(n) {
        return new Intl.NumberFormat('vi-VN').format(Math.round(n));
    }

    function fmtCurrency(n) {
        return fmt(n) + ' ₫';
    }

    const STATE_LABELS = {
        'draft': 'Nháp',
        'sent': 'Đã gửi',
        'sale': 'Đã xác nhận',
        'done': 'Hoàn thành',
        'cancel': 'Đã hủy',
    };

    fetch('/dashboard/data')
        .then(r => r.json())
        .then(data => {
            // KPIs
            document.getElementById('kpi-pipeline').textContent = fmtCurrency(data.kpis.pipeline_value);
            document.getElementById('kpi-revenue').textContent = fmtCurrency(data.kpis.monthly_revenue);
            document.getElementById('kpi-debt').textContent = fmtCurrency(data.kpis.total_debt);
            document.getElementById('kpi-leads').textContent = data.kpis.new_leads;

            // Pipeline Chart
            const ctx = document.getElementById('pipeline-chart');
            if (ctx && data.pipeline.length > 0) {
                new Chart(ctx, {
                    type: 'bar',
                    data: {
                        labels: data.pipeline.map(s => s.stage),
                        datasets: [{
                            label: 'Số lượng leads',
                            data: data.pipeline.map(s => s.count),
                            backgroundColor: '#42a5f5',
                        }, {
                            label: 'Giá trị (triệu)',
                            data: data.pipeline.map(s => s.value / 1000000),
                            backgroundColor: '#66bb6a',
                        }]
                    },
                    options: {
                        responsive: true,
                        plugins: { legend: { position: 'bottom' } },
                        scales: { y: { beginAtZero: true } }
                    }
                });
            }

            // Recent Orders
            const ordersBody = document.querySelector('#orders-table tbody');
            data.recent_orders.forEach(o => {
                const stateClass = 'state-' + o.state;
                const stateLabel = STATE_LABELS[o.state] || o.state;
                ordersBody.innerHTML += `<tr>
                    <td>${o.name}</td>
                    <td>${o.partner}</td>
                    <td>${o.date}</td>
                    <td>${fmtCurrency(o.amount)}</td>
                    <td><span class="${stateClass}">${stateLabel}</span></td>
                </tr>`;
            });

            // Invoices
            const invBody = document.querySelector('#invoices-table tbody');
            data.invoices.forEach(inv => {
                let badge = '';
                if (inv.paid) {
                    badge = '<span class="badge badge-paid">Đã TT</span>';
                } else if (inv.days_overdue > 0) {
                    badge = `<span class="badge badge-overdue">Quá hạn ${inv.days_overdue}d</span>`;
                } else {
                    badge = '<span class="badge badge-unpaid">Chưa TT</span>';
                }
                invBody.innerHTML += `<tr>
                    <td>${inv.name}</td>
                    <td>${inv.partner}</td>
                    <td>${fmtCurrency(inv.amount)}</td>
                    <td>${fmtCurrency(inv.residual)}</td>
                    <td>${badge}</td>
                </tr>`;
            });

            // Credit Alerts
            const alertsBody = document.querySelector('#credit-alerts-table tbody');
            const noAlerts = document.getElementById('no-alerts');
            if (data.credit_alerts.length === 0) {
                noAlerts.style.display = 'block';
                document.getElementById('credit-alerts-table').style.display = 'none';
            } else {
                data.credit_alerts.forEach(a => {
                    alertsBody.innerHTML += `<tr class="exceeded">
                        <td>${a.name}</td>
                        <td>${fmtCurrency(a.credit_limit)}</td>
                        <td>${fmtCurrency(a.outstanding_debt)}</td>
                        <td>${fmtCurrency(a.exceeded_by)}</td>
                    </tr>`;
                });
            }
        })
        .catch(err => {
            console.error('Dashboard load error:', err);
            dashboard.innerHTML += '<div class="alert alert-danger mt-3">Không thể tải dữ liệu dashboard. Vui lòng thử lại.</div>';
        });
});
