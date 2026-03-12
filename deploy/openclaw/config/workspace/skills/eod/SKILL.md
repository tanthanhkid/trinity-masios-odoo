---
name: eod
description: Báo cáo cuối ngày — tổng kết EOD
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌙", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Cuối Ngày (EOD)

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="eod"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_flash_report report_type=eod — KHÔNG hỏi gì thêm
2. Tổng kết ngày: doanh số, đơn hàng, leads, tasks hoàn thành
3. Highlight thành tích và vấn đề tồn đọng

## Commands

### Lấy EOD Report
```bash
mcporter call odoo.odoo_flash_report report_type=eod
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format tổng kết rõ ràng cho Telegram

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/brief_hunter — Tổng hợp Hunter
/brief_farmer — Tổng hợp Farmer
/brief_ar — Tổng hợp công nợ

🔙 /masi ← Menu chính
