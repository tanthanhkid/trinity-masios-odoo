---
name: eod
description: Báo cáo cuối ngày — tổng kết EOD
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌙", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Cuối Ngày (EOD)

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
