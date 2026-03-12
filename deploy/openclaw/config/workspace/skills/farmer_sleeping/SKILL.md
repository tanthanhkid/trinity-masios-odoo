---
name: farmer_sleeping
description: Khách hàng ngủ đông — phân theo bucket thời gian
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "😴", "requires": { "bins": ["mcporter"] } } }
---

# Khách Hàng Ngủ Đông

## Workflow
1. Chạy ngay odoo_farmer_today section=sleeping — KHÔNG hỏi gì thêm
2. Phân theo bucket: 30-60, 60-90, >90 ngày không mua
3. Hiển thị số lượng và danh sách theo bucket

## Commands

### Lấy Sleeping Customers
```bash
mcporter call odoo.odoo_farmer_today section=sleeping
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight khách ngủ đông lâu nhất
