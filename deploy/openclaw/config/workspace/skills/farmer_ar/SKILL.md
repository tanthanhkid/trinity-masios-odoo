---
name: farmer_ar
description: Công nợ phải thu team Farmer
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💳", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Team Farmer

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_ar"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_ar — KHÔNG hỏi gì thêm
2. Hiển thị AR aging theo khách hàng Farmer
3. Highlight khách nợ quá hạn

## Commands

### Lấy Farmer AR
```bash
mcporter call odoo.odoo_farmer_ar
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng aging dễ đọc trên Telegram

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- da_nhac_no <ID> — Đánh dấu đã nhắc nợ
- gan_dispute <ID> "lý do" — Gắn tranh chấp

🔙 /farmer_today ← Quay lại | /brief_ar ← Tổng hợp AR | /masi ← Menu chính
