---
name: hunter_quotes
description: Báo giá đang chờ > 3 ngày — cần follow up
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📝", "requires": { "bins": ["mcporter"] } } }
---

# Báo Giá Đang Chờ

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="hunter_quotes"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_hunter_today section=quotes — KHÔNG hỏi gì thêm
2. Liệt kê báo giá pending > 3 ngày
3. Hiển thị: khách hàng, giá trị, số ngày chờ

## Commands

### Lấy Pending Quotes
```bash
mcporter call odoo.odoo_hunter_today section=quotes
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo số ngày chờ giảm dần

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- tao_task "Follow-up báo giá <SO number>" <partner_id> — Tạo task theo dõi

🔙 /hunter_today ← Quay lại | /masi ← Menu chính
