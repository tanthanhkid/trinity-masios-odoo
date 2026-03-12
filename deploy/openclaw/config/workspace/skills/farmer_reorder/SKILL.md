---
name: farmer_reorder
description: Khách hàng cần reorder — đến hạn mua lại
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🔄", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng Cần Reorder

## Workflow
1. Chạy ngay odoo_farmer_today section=reorder — KHÔNG hỏi gì thêm
2. Liệt kê khách đến hạn mua lại
3. Hiển thị: tên, ngày mua cuối, chu kỳ, nhân viên

## Commands

### Lấy Reorder Due List
```bash
mcporter call odoo.odoo_farmer_today section=reorder
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo mức độ ưu tiên
