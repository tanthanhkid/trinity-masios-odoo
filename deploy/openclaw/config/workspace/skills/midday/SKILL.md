---
name: midday
description: Flash report giữa ngày — tóm tắt nhanh
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "☀️", "requires": { "bins": ["mcporter"] } } }
---

# Flash Report Giữa Ngày

## Workflow
1. Chạy ngay odoo_flash_report report_type=midday — KHÔNG hỏi gì thêm
2. Tóm tắt tiến độ nửa ngày: doanh số, leads, tasks
3. So sánh với target ngày

## Commands

### Lấy Midday Flash
```bash
mcporter call odoo.odoo_flash_report report_type=midday
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format ngắn gọn, dễ scan trên Telegram
