---
name: brief_farmer
description: Báo cáo team Farmer — KPIs và hiệu suất
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌾", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Team Farmer

## Workflow
1. Chạy ngay odoo_brief_farmer — KHÔNG hỏi gì thêm
2. Hiển thị KPIs chính: retention, reorder, doanh số
3. Format bullet rõ ràng

## Commands

### Lấy Farmer KPIs
```bash
mcporter call odoo.odoo_brief_farmer
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight số liệu nổi bật bằng emoji
