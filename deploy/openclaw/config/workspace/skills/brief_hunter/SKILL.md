---
name: brief_hunter
description: Báo cáo team Hunter — KPIs và hiệu suất
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🎯", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Team Hunter

## Workflow
1. Chạy ngay odoo_brief_hunter — KHÔNG hỏi gì thêm
2. Hiển thị KPIs chính: leads mới, conversion, doanh số
3. Format bullet rõ ràng

## Commands

### Lấy Hunter KPIs
```bash
mcporter call odoo.odoo_brief_hunter
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight số liệu nổi bật bằng emoji
