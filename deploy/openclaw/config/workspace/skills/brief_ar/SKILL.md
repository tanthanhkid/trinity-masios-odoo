---
name: brief_ar
description: Tổng hợp công nợ phải thu (AR aging)
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📋", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Công Nợ Phải Thu

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="brief_ar"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_brief_ar — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị AR aging: current, 1-30, 31-60, 61-90, >90 ngày
3. Tổng số dư và phân bổ theo bucket

## Commands

### Lấy AR Summary
```bash
mcporter call odoo.odoo_brief_ar
```

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/congno_denhan — Công nợ đến hạn
/congno_quahan — Công nợ quá hạn
/farmer_ar — Công nợ theo Farmer

📌 Hành động nhanh:
- da_nhac_no <ID> — Đã nhắc nợ
- gan_dispute <ID> "lý do" — Gắn tranh chấp

🔙 /morning_brief ← Quay lại | /masi ← Menu chính

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng aging dễ đọc trên Telegram
