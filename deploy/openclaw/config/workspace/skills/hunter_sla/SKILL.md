---
name: hunter_sla
description: Leads vi phạm SLA — cần xử lý gấp
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "⏰", "requires": { "bins": ["mcporter"] } } }
---

# Hunter SLA — Leads Vi Phạm

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="hunter_sla"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_hunter_sla_details — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Liệt kê từng lead vi phạm SLA: tên, thời gian, nhân viên
3. Gợi ý action cần làm cho mỗi lead

## Commands

### Lấy SLA Details
```bash
mcporter call odoo.odoo_hunter_sla_details
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight leads quá hạn lâu nhất

## Hành động & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

📌 Hành động nhanh:
- da_lien_he <ID> — Đánh dấu đã liên hệ
- doi_owner lead <ID> <user_id> — Đổi người phụ trách
- escalate crm.lead <ID> — Báo cáo cấp trên

🔙 /hunter_today ← Quay lại | /masi ← Menu chính
