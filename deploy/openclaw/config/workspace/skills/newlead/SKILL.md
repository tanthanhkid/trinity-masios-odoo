---
name: newlead
description: Tạo lead CRM mới — hỏi thông tin rồi tạo luôn
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🎯", "requires": { "bins": ["mcporter"] } } }
---

# Tạo Lead Mới

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="newlead"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Hỏi user ngay 4 thông tin:
   - Tên lead (bắt buộc)
   - Tên khách hàng
   - Email hoặc Phone
   - Ghi chú (nếu có)
2. Tạo lead bằng mcporter
3. Báo kết quả: ID, tên lead, stage

## Commands

### Tạo lead
```bash
mcporter call odoo.odoo_create model=crm.lead 'values={"name":"TÊN_LEAD","contact_name":"TÊN_KH","email_from":"EMAIL","phone":"PHONE","description":"GHI_CHÚ"}'
```

### Kiểm tra lead vừa tạo
```bash
mcporter call odoo.odoo_search_read model=crm.lead 'domain=[["id","=",ID]]' fields=id,name,contact_name,email_from,phone,stage_id limit=1
```

## Lưu ý
- Trả lời bằng tiếng Việt
- Tạo xong báo ngay kết quả, format đẹp
