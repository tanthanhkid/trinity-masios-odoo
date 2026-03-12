---
name: doanhso_homnay
description: Doanh số hôm nay — Hunter vs Farmer
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💰", "requires": { "bins": ["mcporter"] } } }
---

# Doanh Số Hôm Nay

## Workflow
1. Chạy ngay odoo_revenue_today — KHÔNG hỏi gì thêm
2. So sánh doanh số Hunter vs Farmer
3. Hiển thị tổng + breakdown theo team

## Commands

### Lấy doanh số hôm nay
```bash
mcporter call odoo.odoo_revenue_today
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng so sánh Hunter vs Farmer
