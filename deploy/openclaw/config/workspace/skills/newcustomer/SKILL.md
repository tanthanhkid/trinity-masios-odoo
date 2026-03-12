---
name: newcustomer
description: Tạo khách hàng mới — hỏi thông tin rồi tạo luôn
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "👤", "requires": { "bins": ["mcporter"] } } }
---

# Tạo Khách Hàng Mới

## Workflow
1. Hỏi user ngay 4 thông tin:
   - Tên khách hàng (bắt buộc)
   - Số điện thoại
   - Email
   - Loại: company hay person (mặc định: person)
2. Tạo KH bằng mcporter
3. Báo kết quả: ID, tên, loại

## Commands

### Tạo khách hàng
```bash
mcporter call odoo.odoo_create_customer name="TÊN" phone=SDT email=EMAIL company_type=person
```

### Kiểm tra KH vừa tạo
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["id","=",ID]]' fields=id,name,phone,email,company_type,customer_classification limit=1
```

## Lưu ý
- Trả lời bằng tiếng Việt
- company_type: `company` = công ty, `person` = cá nhân
- Tạo xong báo ngay kết quả
