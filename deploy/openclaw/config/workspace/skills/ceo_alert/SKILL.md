---
name: ceo_alert
description: Cảnh báo khẩn cấp cho CEO — top 3-5 vấn đề
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🚨", "requires": { "bins": ["mcporter"] } } }
---

# Cảnh Báo CEO

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="ceo_alert"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay odoo_ceo_alert — KHÔNG hỏi gì thêm
   ⚠️ Kiểm tra data_quality: Nếu MCP tool trả về data_quality = "issue" hoặc "warning", PHẢI hiển thị phần DATA ISSUE trước báo cáo:
   "⚠️ DATA ISSUE: [liệt kê data_issues]. Số liệu dưới đây có thể chưa đầy đủ."
2. Hiển thị top 3-5 vấn đề critical nhất
3. Mỗi alert: mức độ + mô tả + action cần làm

## Commands

### Lấy CEO Alerts
```bash
mcporter call odoo.odoo_ceo_alert
```

## Drill-down
Sau khi hiển thị, LUÔN thêm:

🔍 Drill-down theo vấn đề:
/hunter_sla — SLA lead chi tiết
/congno_quahan — Công nợ quá hạn
/farmer_sleeping — Khách ngủ đông
/task_quahan — Task quá hạn

🔙 /morning_brief ← Quay lại | /masi ← Menu chính

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi, không hỏi thêm
- Ưu tiên hiển thị vấn đề nghiêm trọng nhất trước
