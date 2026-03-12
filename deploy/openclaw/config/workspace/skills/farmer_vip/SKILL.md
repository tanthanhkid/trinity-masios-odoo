---
name: farmer_vip
description: Trạng thái khách VIP — rủi ro và cơ hội
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "👑", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng VIP

## Workflow
1. Chạy ngay odoo_farmer_today section=vip — KHÔNG hỏi gì thêm
2. Hiển thị trạng thái VIP: active, at risk, churned
3. Highlight rủi ro mất khách VIP

## Commands

### Lấy VIP Status
```bash
mcporter call odoo.odoo_farmer_today section=vip
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Ưu tiên hiển thị VIP đang at risk
