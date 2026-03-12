---
name: pipeline
description: Xem pipeline CRM — chạy ngay, không hỏi gì thêm
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📈", "requires": { "bins": ["mcporter"] } } }
---

# Xem Pipeline CRM

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="pipeline"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Chạy ngay 2 lệnh — KHÔNG hỏi gì thêm
2. Format kết quả: pipeline theo stage + danh sách lead mới nhất
3. Hiển thị: số deal, giá trị, tỷ lệ chuyển đổi

## Commands

### Lấy pipeline theo giai đoạn
```bash
mcporter call odoo.odoo_pipeline_by_stage
```

### Lấy danh sách lead
```bash
mcporter call odoo.odoo_crm_lead_summary
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Chạy NGAY khi user gọi /pipeline, không hỏi thêm
- Format bảng dễ đọc trên Telegram
