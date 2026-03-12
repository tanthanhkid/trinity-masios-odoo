---
name: hunter_quotes
description: Báo giá đang chờ > 3 ngày — cần follow up
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📝", "requires": { "bins": ["mcporter"] } } }
---

# Báo Giá Đang Chờ

## Workflow
1. Chạy ngay odoo_hunter_today section=quotes — KHÔNG hỏi gì thêm
2. Liệt kê báo giá pending > 3 ngày
3. Hiển thị: khách hàng, giá trị, số ngày chờ

## Commands

### Lấy Pending Quotes
```bash
mcporter call odoo.odoo_hunter_today section=quotes
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo số ngày chờ giảm dần
