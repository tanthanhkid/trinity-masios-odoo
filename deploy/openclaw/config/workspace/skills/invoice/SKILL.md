---
name: invoice
description: Tạo hóa đơn từ đơn hàng — hỏi mã SO, tạo + gửi PDF tự động
allowed-tools: Bash
metadata:
  { "openclaw": { "emoji": "🧾", "requires": { "bins": ["mcporter"] } } }
---

# Tạo Hóa Đơn

## Workflow
1. Hỏi user: mã đơn hàng (SO number hoặc ID)
2. Tìm đơn hàng trong hệ thống
3. Tạo hóa đơn từ SO
4. Tự động gửi PDF qua Telegram (không hỏi)

## Commands

### Tìm đơn hàng theo tên
```bash
mcporter call odoo.odoo_search_read model=sale.order 'domain=[["name","ilike","SO_NUMBER"]]' fields=id,name,partner_id,state,amount_total limit=5
```

### Tạo hóa đơn từ SO
```bash
mcporter call odoo.odoo_create_invoice_from_so order_id=ID
```

### Gửi PDF tự động (chạy ngay sau khi tạo thành công)
```bash
mcporter call odoo.odoo_invoice_pdf invoice_id=INVOICE_ID > /tmp/pdf_result.json 2>/dev/null
python3 /home/openclaw/.openclaw/workspace/send_pdf.py CHAT_ID < /tmp/pdf_result.json
rm -f /tmp/pdf_result.json
```

## Lưu ý
- CHAT_ID: lấy từ session name `telegram:direct:CHAT_ID`
- Trả lời bằng tiếng Việt
- Tạo xong → gửi PDF ngay, không hỏi
