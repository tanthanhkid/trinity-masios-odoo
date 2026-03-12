---
name: farmer_today
description: Tổng quan Farmer hôm nay — tất cả sections
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌿", "requires": { "bins": ["mcporter"] } } }
---

# Farmer Hôm Nay — Tổng Quan

## Workflow
1. Chạy ngay odoo_farmer_today section=all — KHÔNG hỏi gì thêm
2. Hiển thị: reorder, sleeping, VIP, retention
3. Format từng section rõ ràng

## Commands

### Lấy Farmer Overview
```bash
mcporter call odoo.odoo_farmer_today section=all
```

## Drill-down
Sau khi hiển thị, gợi ý: "Gõ /farmer_reorder để xem tái đặt hàng, /farmer_sleeping để xem khách ngủ đông, /farmer_vip để xem khách VIP"

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format dễ đọc trên Telegram
