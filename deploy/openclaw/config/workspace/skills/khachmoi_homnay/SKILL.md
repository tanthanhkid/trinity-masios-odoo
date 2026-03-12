---
name: khachmoi_homnay
description: Đơn hàng khách mới hôm nay — first orders
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌟", "requires": { "bins": ["mcporter"] } } }
---

# Khách Mới Hôm Nay

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="khachmoi_homnay"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

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

## Điều hướng
🔙 /hunter_today ← Quay lại | /masi ← Menu chính
