---
name: task_quahan
description: Task quá hạn — phân theo team
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📌", "requires": { "bins": ["mcporter"] } } }
---

# Task Quá Hạn

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="task_quahan"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

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

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- xong <ID> — Đánh dấu hoàn thành
- doi_owner project.task <ID> <user_id> — Đổi người phụ trách
- escalate project.task <ID> — Báo cáo cấp trên

🔙 /midday hoặc /eod ← Báo cáo | /masi ← Menu chính
