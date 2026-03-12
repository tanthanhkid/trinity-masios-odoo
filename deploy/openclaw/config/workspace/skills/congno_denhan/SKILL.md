---
name: congno_denhan
description: Công nợ sắp đến hạn — trong 7 ngày tới
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "⚠️", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Sắp Đến Hạn

## Workflow
1. Chạy ngay odoo_congno mode=due_soon — KHÔNG hỏi gì thêm
2. Liệt kê hóa đơn đến hạn trong 7 ngày
3. Hiển thị: khách hàng, số tiền, ngày đến hạn

## Commands

### Lấy AR Due Soon
```bash
mcporter call odoo.odoo_congno mode=due_soon
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo ngày đến hạn gần nhất
