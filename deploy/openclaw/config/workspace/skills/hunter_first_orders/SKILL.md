---
name: hunter_first_orders
description: Đơn hàng đầu tiên từ khách mới
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🆕", "requires": { "bins": ["mcporter"] } } }
---

# Đơn Hàng Đầu Tiên — Khách Mới

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="hunter_first_orders"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_hunter_today section=first_orders — KHÔNG hỏi gì thêm
2. Liệt kê đơn hàng đầu tiên từ khách hàng mới
3. Hiển thị: khách hàng, giá trị, ngày tạo

## Commands

### Lấy First Orders
```bash
mcporter call odoo.odoo_hunter_today section=first_orders
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format dễ đọc trên Telegram

## Điều hướng
🔙 /hunter_today ← Quay lại | /masi ← Menu chính
