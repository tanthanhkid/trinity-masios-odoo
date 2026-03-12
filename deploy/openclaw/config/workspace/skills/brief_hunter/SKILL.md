---
name: brief_hunter
description: Báo cáo team Hunter — KPIs và hiệu suất
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🎯", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Team Hunter

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="brief_hunter"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_brief_hunter — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị KPIs chính: leads mới, conversion, doanh số
3. Format bullet rõ ràng

## Commands

### Lấy Hunter KPIs
```bash
mcporter call odoo.odoo_brief_hunter
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight số liệu nổi bật bằng emoji

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/hunter_today — Chi tiết hôm nay
/hunter_sla — SLA phản hồi
/hunter_quotes — Báo giá chờ
/hunter_first_orders — Đơn đầu tiên
/hunter_sources — Nguồn lead

🔙 /morning_brief ← Quay lại | /masi ← Menu chính
