---
name: farmer_reorder
description: Khách hàng cần reorder — đến hạn mua lại
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🔄", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng Cần Reorder

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_reorder"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_today section=reorder — KHÔNG hỏi gì thêm
2. Liệt kê khách đến hạn mua lại
3. Hiển thị: tên, ngày mua cuối, chu kỳ, nhân viên

## Commands

### Lấy Reorder Due List
```bash
mcporter call odoo.odoo_farmer_today section=reorder
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo mức độ ưu tiên

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- tao_task "Gọi lại KH <tên>" <partner_id> — Tạo task chăm sóc

🔙 /farmer_today ← Quay lại | /masi ← Menu chính
