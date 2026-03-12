---
name: brief_farmer
description: Báo cáo team Farmer — KPIs và hiệu suất
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🌾", "requires": { "bins": ["mcporter"] } } }
---

# Báo Cáo Team Farmer

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="brief_farmer"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_brief_farmer — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị KPIs chính: retention, reorder, doanh số
3. Format bullet rõ ràng

## Commands

### Lấy Farmer KPIs
```bash
mcporter call odoo.odoo_brief_farmer
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Highlight số liệu nổi bật bằng emoji

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/farmer_today — Chi tiết hôm nay
/farmer_reorder — Khách cần tái đặt
/farmer_sleeping — Khách ngủ đông
/farmer_vip — Khách VIP
/farmer_ar — Công nợ Farmer

🔙 /morning_brief ← Quay lại | /masi ← Menu chính
