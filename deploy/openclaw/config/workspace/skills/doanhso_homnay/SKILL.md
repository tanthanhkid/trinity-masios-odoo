---
name: doanhso_homnay
description: Doanh số hôm nay — Hunter vs Farmer
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "💰", "requires": { "bins": ["mcporter"] } } }
---

# Doanh Số Hôm Nay

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="doanhso_homnay"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_revenue_today — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. So sánh doanh số Hunter vs Farmer
3. Hiển thị tổng + breakdown theo team

## Commands

### Lấy doanh số hôm nay
```bash
mcporter call odoo.odoo_revenue_today
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Format bảng so sánh Hunter vs Farmer

## Drill-down & Điều hướng
Sau khi hiển thị báo cáo, LUÔN thêm:

🔍 Drill-down:
/brief_hunter — Doanh thu Hunter chi tiết
/brief_farmer — Doanh thu Farmer chi tiết

🔙 /morning_brief ← Quay lại | /masi ← Menu chính
