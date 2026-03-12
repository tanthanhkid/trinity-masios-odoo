---
name: khachmoi_homnay
description: Đơn hàng khách mới hôm nay — first orders
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌟", "requires": { "bins": ["mcporter"] } } }
---

# Khách Mới Hôm Nay

## Workflow
1. Chạy ngay odoo_revenue_today — KHÔNG hỏi gì thêm
2. Lọc chỉ đơn hàng first_order (khách mới)
3. Hiển thị: tên khách, giá trị đơn, nhân viên phụ trách

## Commands

### Lấy doanh số hôm nay (filter first_order)
```bash
mcporter call odoo.odoo_revenue_today
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Chỉ hiển thị đơn hàng từ khách hàng MỚI
