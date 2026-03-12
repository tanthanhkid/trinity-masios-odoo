---
name: quote
description: Tạo báo giá — tìm KH, chọn sản phẩm, tạo + gửi PDF tự động
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "📋", "requires": { "bins": ["mcporter"] } } }
---

# Tạo Báo Giá

## Bước 0: Kiểm tra quyền
1. Lấy telegram_id từ session
2. Gọi: `mcporter call odoo.odoo_telegram_check_permission telegram_id="<ID>" command="quote"`
3. Nếu allowed=false → hiển thị "🚫 {reason}" và DỪNG
4. Nếu allowed=true → tiếp tục các bước bên dưới

## Workflow
1. Hỏi tên khách hàng → tìm trong hệ thống
2. Liệt kê sản phẩm có sẵn → HỎI user chọn SP + số lượng (BẮT BUỘC)
3. Tạo báo giá
4. Tự động gửi PDF qua Telegram (không hỏi)

## Commands

### Tìm khách hàng
```bash
mcporter call odoo.odoo_search_read model=res.partner 'domain=[["name","ilike","KEYWORD"]]' fields=id,name,phone,email limit=10
```

### Liệt kê sản phẩm
```bash
mcporter call odoo.odoo_search_read model=product.product fields=id,name,list_price limit=20
```

### Tạo báo giá
```bash
mcporter call odoo.odoo_create_sale_order partner_id=ID 'order_lines=[{"product_id":PID,"quantity":SL}]'
```

### Gửi PDF tự động (chạy ngay sau khi tạo thành công)
```bash
mcporter call odoo.odoo_sale_order_pdf order_id=ORDER_ID > /tmp/pdf_result.json 2>/dev/null
python3 /home/openclaw/.openclaw/workspace/send_pdf.py CHAT_ID < /tmp/pdf_result.json
rm -f /tmp/pdf_result.json
```

## Lưu ý
- CHAT_ID: lấy từ session name `telegram:direct:CHAT_ID`
- Trả lời bằng tiếng Việt
- PHẢI hỏi user chọn SP trước khi tạo
- Tạo xong → gửi PDF ngay, không hỏi
