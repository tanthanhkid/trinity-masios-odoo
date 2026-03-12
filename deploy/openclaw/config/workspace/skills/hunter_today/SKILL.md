---
name: hunter_today
description: Tổng quan Hunter hôm nay — tất cả sections
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🏹", "requires": { "bins": ["mcporter"] } } }
---

# Hunter Hôm Nay — Tổng Quan

## Workflow
1. Chạy ngay odoo_hunter_today section=all — KHÔNG hỏi gì thêm
2. Hiển thị tổng quan: leads, quotes, first orders, sources
3. Format từng section rõ ràng

## Commands

### Lấy Hunter Overview
```bash
mcporter call odoo.odoo_hunter_today section=all
```

## Drill-down
Sau khi hiển thị, gợi ý: "Gõ /hunter_sla để xem SLA, /hunter_quotes để xem báo giá, /hunter_first_orders để xem đơn đầu tiên"

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format dễ đọc trên Telegram
