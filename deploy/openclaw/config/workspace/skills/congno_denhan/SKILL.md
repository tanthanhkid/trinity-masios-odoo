---
name: congno_denhan
description: Công nợ sắp đến hạn — trong 7 ngày tới
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "⚠️", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Sắp Đến Hạn

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="congno_denhan"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_congno mode=due_soon — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Liệt kê hóa đơn đến hạn trong 7 ngày
3. Hiển thị: khách hàng, số tiền, ngày đến hạn

## Commands

### Lấy AR Due Soon
```bash
mcporter call odoo.odoo_congno mode=due_soon
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo ngày đến hạn gần nhất

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- da_nhac_no <ID> — Đánh dấu đã nhắc nợ

🔙 /brief_ar ← Quay lại | /masi ← Menu chính
