---
name: morning_brief
description: Báo cáo buổi sáng CEO — Hunter/Farmer/AR/Alerts
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌅", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Buổi Sáng

## Workflow
1. Chạy ngay odoo_morning_brief — KHÔNG hỏi gì thêm
2. Format thành 4 block: Hunter | Farmer | AR | Alerts
3. Mỗi block có emoji + số liệu chính

## Commands

### Lấy Morning Brief
```bash
mcporter call odoo.odoo_morning_brief
```

## Drill-down
Sau khi hiển thị, gợi ý: "Gõ /ceo_alert để xem chi tiết vấn đề, /brief_hunter để xem Hunter, /brief_farmer để xem Farmer, /brief_ar để xem công nợ"

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format 4 block rõ ràng cho Telegram
