---
name: farmer_ar
description: Công nợ phải thu team Farmer
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💳", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Team Farmer

## Workflow
1. Chạy ngay odoo_farmer_ar — KHÔNG hỏi gì thêm
2. Hiển thị AR aging theo khách hàng Farmer
3. Highlight khách nợ quá hạn

## Commands

### Lấy Farmer AR
```bash
mcporter call odoo.odoo_farmer_ar
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng aging dễ đọc trên Telegram
