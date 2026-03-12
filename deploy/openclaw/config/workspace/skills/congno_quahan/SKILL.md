---
name: congno_quahan
description: Công nợ quá hạn — cần thu ngay
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🔴", "requires": { "bins": ["mcporter"] } } }
---

# Công Nợ Quá Hạn

## Workflow
1. Chạy ngay odoo_congno mode=overdue — KHÔNG hỏi gì thêm
2. Liệt kê hóa đơn đã quá hạn thanh toán
3. Hiển thị: khách hàng, số tiền, số ngày quá hạn

## Commands

### Lấy AR Overdue
```bash
mcporter call odoo.odoo_congno mode=overdue
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight khoản nợ lớn và quá hạn lâu nhất
