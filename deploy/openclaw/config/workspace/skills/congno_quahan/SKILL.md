---
name: congno_quahan
description: Công nợ quá hạn — cần thu ngay
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🔴", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Quá Hạn

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="congno_quahan"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_congno mode=overdue — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Liệt kê hóa đơn đã quá hạn thanh toán
3. Hiển thị: khách hàng, số tiền, số ngày quá hạn

## Commands

### Lấy AR Overdue
```bash
mcporter call odoo.odoo_congno mode=overdue
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight khoản nợ lớn và quá hạn lâu nhất

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- da_nhac_no <ID> — Đánh dấu đã nhắc nợ
- gan_dispute <ID> "lý do" — Gắn tranh chấp
- escalate account.move <ID> — Báo cáo cấp trên

🔙 /brief_ar ← Quay lại | /masi ← Menu chính
