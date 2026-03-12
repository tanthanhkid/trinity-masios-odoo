---
name: task_quahan
description: Task quá hạn — phân theo team
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📌", "requires": { "bins": ["mcporter"] } } }
---

# Task Quá Hạn

## Workflow
1. Chạy ngay odoo_task_overdue — KHÔNG hỏi gì thêm
2. Phân nhóm task quá hạn theo team/nhân viên
3. Hiển thị: task, người phụ trách, số ngày quá hạn

## Commands

### Lấy Overdue Tasks
```bash
mcporter call odoo.odoo_task_overdue
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Sắp xếp theo mức độ quá hạn giảm dần
