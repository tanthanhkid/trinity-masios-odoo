---
name: farmer_sleeping
description: Khách hàng ngủ đông — phân theo bucket thời gian
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "😴", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng Ngủ Đông

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_sleeping"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_today section=sleeping — KHÔNG hỏi gì thêm
2. Phân theo bucket: 30-60, 60-90, >90 ngày không mua
3. Hiển thị số lượng và danh sách theo bucket

## Commands

### Lấy Sleeping Customers
```bash
mcporter call odoo.odoo_farmer_today section=sleeping
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight khách ngủ đông lâu nhất

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- tao_task "Chăm khách ngủ đông <tên>" <partner_id> — Tạo task
- escalate res.partner <ID> — Báo cáo cấp trên

🔙 /farmer_today ← Quay lại | /masi ← Menu chính
