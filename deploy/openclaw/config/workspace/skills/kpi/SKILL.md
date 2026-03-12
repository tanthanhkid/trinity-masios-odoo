---
name: kpi
description: Xem KPI dashboard — chạy ngay, không hỏi gì thêm
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📊", "requires": { "bins": ["mcporter"] } } }
---

# Xem KPI Dashboard

## Workflow
1. Chạy ngay odoo_dashboard_kpis — KHÔNG hỏi gì thêm
2. Format kết quả đẹp: bảng/bullet, có emoji
3. Hiển thị: doanh thu, đơn hàng, hóa đơn, công nợ, leads

## Commands

### Lấy KPI
```bash
mcporter call odoo.odoo_dashboard_kpis
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi /kpi, không hỏi thêm
- Format dễ đọc trên Telegram
