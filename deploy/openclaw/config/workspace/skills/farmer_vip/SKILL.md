---
name: farmer_vip
description: Trạng thái khách VIP — rủi ro và cơ hội
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "👑", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng VIP

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="farmer_vip"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_farmer_today section=vip — KHÔNG hỏi gì thêm
2. Hiển thị trạng thái VIP: active, at risk, churned
3. Highlight rủi ro mất khách VIP

## Commands

### Lấy VIP Status
```bash
mcporter call odoo.odoo_farmer_today section=vip
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Ưu tiên hiển thị VIP đang at risk

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- tao_task "Chăm VIP <tên>" <partner_id> — Tạo task ưu tiên
- escalate res.partner <ID> — Báo cáo cấp trên

🔙 /farmer_today ← Quay lại | /masi ← Menu chính
