import sqlite3
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

conn = sqlite3.connect('accounting.db', check_same_thread=False)
c = conn.cursor()

# إنشاء جداول النظام الأساسية
c.execute('''
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_number TEXT NOT NULL,
        account_name TEXT NOT NULL,
        account_type TEXT NOT NULL,
        balance REAL NOT NULL
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT NOT NULL,
        ust_id TEXT NOT NULL
    )
''')

c.execute("SELECT COUNT(*) FROM suppliers")
if c.fetchone()[0] == 0:
    c.execute("INSERT INTO suppliers (name, address, ust_id) VALUES (?, ?, ?)", ("General / عام", "Germany", "DE000000000"))
    conn.commit()

# جدول بيانات الشركة لتعديلها يدوياً
c.execute('''
    CREATE TABLE IF NOT EXISTS company_settings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT,
        address TEXT,
        phone TEXT,
        email TEXT,
        website TEXT,
        iban TEXT,
        bic TEXT,
        ust_id TEXT,
        hrb TEXT,
        amtsgericht TEXT,
        director TEXT,
        payment_terms TEXT
    )
''')

c.execute("SELECT COUNT(*) FROM company_settings")
if c.fetchone()[0] == 0:
    c.execute('''
        INSERT INTO company_settings (company_name, address, phone, email, website, iban, bic, ust_id, hrb, amtsgericht, director, payment_terms)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        "Darnieto GmbH",
        "Terofalstr. 69, 80689 München",
        "+49 171 3277770",
        "N.zehrawi@web.de",
        "www.darnieto.com",
        "DE68 7009 1500 0000 3545 03",
        "GENODEF1DCA",
        "DE 356285202",
        "HRB 279740",
        "München",
        "Nazira Zehrawi",
        "Bitte überweisen Sie den Rechnungsbetrag innerhalb von 7 Tagen ab Rechnungsdatum auf unser unten genanntes Konto."
    ))
    conn.commit()

c.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        buyer_name TEXT,
        buyer_address TEXT,
        buyer_ust_id TEXT,
        invoice_number TEXT NOT NULL,
        date TEXT NOT NULL,
        net_amount REAL NOT NULL,
        vat_rate REAL NOT NULL,
        vat_amount REAL NOT NULL,
        gross_amount REAL NOT NULL,
        status TEXT DEFAULT 'Unpaid',
        payment_method TEXT DEFAULT 'Bank'
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS invoice_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id INTEGER,
        inventory_item_id INTEGER,
        item_name TEXT,
        quantity REAL,
        unit_price REAL,
        net_total REAL
    )
''')

for col, col_type in [
    ("buyer_name", "TEXT"),
    ("buyer_address", "TEXT"),
    ("buyer_ust_id", "TEXT"),
    ("status", "TEXT DEFAULT 'Unpaid'"),
    ("payment_method", "TEXT DEFAULT 'Bank'")
]:
    try:
        c.execute(f"ALTER TABLE invoices ADD COLUMN {col} {col_type}")
        conn.commit()
    except sqlite3.OperationalError:
        pass

c.execute('''
    CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        debit_account_id INTEGER NOT NULL,
        credit_account_id INTEGER NOT NULL,
        amount REAL NOT NULL
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS receipts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        vendor TEXT NOT NULL,
        net_amount REAL NOT NULL,
        vat_amount REAL NOT NULL,
        gross_amount REAL NOT NULL
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        name TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity REAL NOT NULL,
        unit_price REAL NOT NULL
    )
''')
conn.commit()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CompanySettingsUpdate(BaseModel):
    company_name: str
    address: str
    phone: str
    email: str
    website: str
    iban: str
    bic: str
    ust_id: str
    hrb: str
    amtsgericht: str
    director: str
    payment_terms: str

class AccountCreate(BaseModel):
    account_number: str
    account_name: str
    account_type: str
    balance: float

class SupplierCreate(BaseModel):
    name: str
    address: str
    ust_id: str

class CartItem(BaseModel):
    inventory_item_id: int
    quantity: float

class MultiItemInvoiceCreate(BaseModel):
    buyer_name: str
    buyer_address: str
    buyer_ust_id: str = ""
    invoice_number: str
    date: str
    vat_rate: float
    status: str = "Unpaid"
    payment_method: str = "Bank"
    items: list[CartItem]

class JournalEntryCreate(BaseModel):
    date: str
    description: str
    debit_account_id: int
    credit_account_id: int
    amount: float

class ReceiptCreate(BaseModel):
    date: str
    vendor: str
    net_amount: float
    vat_rate: float = 0.19

class InventoryItemCreate(BaseModel):
    supplier_id: int
    name: str
    sku: str
    quantity: float
    unit_price: float

class InventoryItemUpdate(BaseModel):
    supplier_id: int
    name: str
    sku: str
    quantity: float
    unit_price: float

@app.get("/")
def read_root():
    return {"message": "ERP Accounting Backend is running successfully!"}

@app.get("/company/")
def get_company_settings():
    c.execute("SELECT company_name, address, phone, email, website, iban, bic, ust_id, hrb, amtsgericht, director, payment_terms FROM company_settings WHERE id=1")
    row = c.fetchone()
    if not row:
        return {}
    return {
        "company_name": row[0], "address": row[1], "phone": row[2], "email": row[3],
        "website": row[4], "iban": row[5], "bic": row[6], "ust_id": row[7],
        "hrb": row[8], "amtsgericht": row[9], "director": row[10], "payment_terms": row[11]
    }

@app.put("/company/")
def update_company_settings(data: CompanySettingsUpdate):
    c.execute("""
        UPDATE company_settings 
        setItem company_name=?, address=?, phone=?, email=?, website=?, iban=?, bic=?, ust_id=?, hrb=?, amtsgericht=?, director=?, payment_terms=?
        WHERE id=1
    """, (
        data.company_name, data.address, data.phone, data.email, data.website,
        data.iban, data.bic, data.ust_id, data.hrb, data.amtsgericht, data.director, data.payment_terms
    ))
    conn.commit()
    return {"message": "Company settings updated successfully"}

@app.get("/accounts/")
def get_accounts():
    c.execute("SELECT id, account_number, account_name, account_type, balance FROM accounts")
    return [{"id": r[0], "account_number": r[1], "account_name": r[2], "account_type": r[3], "balance": r[4]} for r in c.fetchall()]

@app.post("/accounts/")
def create_account(acc: AccountCreate):
    c.execute("INSERT INTO accounts (account_number, account_name, account_type, balance) VALUES (?, ?, ?, ?)",
              (acc.account_number, acc.account_name, acc.account_type, acc.balance))
    conn.commit()
    return {"message": "Account created successfully"}

@app.put("/accounts/{account_id}")
def update_account(account_id: int, acc: AccountCreate):
    c.execute("UPDATE accounts SET account_number=?, account_name=?, account_type=?, balance=? WHERE id=?",
              (acc.account_number, acc.account_name, acc.account_type, acc.balance, account_id))
    conn.commit()
    return {"message": "Account updated successfully"}

@app.delete("/accounts/{account_id}")
def delete_account(account_id: int):
    c.execute("DELETE FROM accounts WHERE id=?", (account_id,))
    conn.commit()
    return {"message": "Account deleted successfully"}

@app.get("/suppliers/")
def get_suppliers():
    c.execute("SELECT id, name, address, ust_id FROM suppliers")
    return [{"id": r[0], "name": r[1], "address": r[2], "ust_id": r[3]} for r in c.fetchall()]

@app.post("/suppliers/")
def create_supplier(sup: SupplierCreate):
    c.execute("INSERT INTO suppliers (name, address, ust_id) VALUES (?, ?, ?)",
              (sup.name, sup.address, sup.ust_id))
    conn.commit()
    return {"message": "Supplier added successfully"}

@app.get("/invoices/")
def get_invoices():
    c.execute("SELECT id, supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method FROM invoices")
    invoices = []
    for r in c.fetchall():
        inv_id = r[0]
        c.execute("SELECT item_name, quantity, unit_price, net_total FROM invoice_items WHERE invoice_id=?", (inv_id,))
        items = [{"name": i[0], "quantity": i[1], "unit_price": i[2], "net_total": i[3]} for i in c.fetchall()]
        invoices.append({
            "id": inv_id, "supplier_id": r[1], "buyer_name": r[2], "buyer_address": r[3], "buyer_ust_id": r[4],
            "invoice_number": r[5], "date": r[6], "net_amount": r[7], "vat_rate": r[8], "vat_amount": r[9], 
            "gross_amount": r[10], "status": r[11], "payment_method": r[12], "items": items
        })
    return invoices

@app.patch("/invoices/{invoice_id}/toggle-status")
def toggle_invoice_status(invoice_id: int):
    c.execute("SELECT status FROM invoices WHERE id=?", (invoice_id,))
    row = c.fetchone()
    if not row:
        return {"error": "Invoice not found"}
    current_status = row[0]
    new_status = "Unpaid" if current_status == "Paid" else "Paid"
    c.execute("UPDATE invoices SET status=? WHERE id=?", (new_status, invoice_id))
    conn.commit()
    return {"message": "Status toggled successfully", "status": new_status}

@app.post("/invoices/multi-item/")
def create_multi_item_invoice(data: MultiItemInvoiceCreate):
    if not data.items:
        return {"error": "No items selected for invoice"}
    
    total_net = 0.0
    processed_items = []
    
    for cart_item in data.items:
        c.execute("SELECT name, quantity, unit_price, supplier_id FROM inventory WHERE id=?", (cart_item.inventory_item_id,))
        inv_row = c.fetchone()
        if not inv_row:
            return {"error": f"Inventory item ID {cart_item.inventory_item_id} not found"}
        
        name, stock_qty, unit_price, sup_id = inv_row
        if stock_qty < cart_item.quantity:
            return {"error": f"Not enough stock for {name}. Available: {stock_qty}"}
        
        item_net = unit_price * cart_item.quantity
        total_net += item_net
        processed_items.append({
            "id": cart_item.inventory_item_id,
            "name": name,
            "quantity": cart_item.quantity,
            "unit_price": unit_price,
            "net_total": item_net,
            "supplier_id": sup_id or 1
        })
    
    vat_amount = total_net * data.vat_rate
    gross_amount = total_net + vat_amount
    first_supplier_id = processed_items[0]["supplier_id"] if processed_items else 1
    
    c.execute("""
        INSERT INTO invoices (supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (first_supplier_id, data.buyer_name, data.buyer_address, data.buyer_ust_id, data.invoice_number, data.date, total_net, data.vat_rate, vat_amount, gross_amount, data.status, data.payment_method))
    
    invoice_id = c.lastrowid
    
    for p in processed_items:
        c.execute("""
            INSERT INTO invoice_items (invoice_id, inventory_item_id, item_name, quantity, unit_price, net_total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (invoice_id, p["id"], p["name"], p["quantity"], p["unit_price"], p["net_total"]))
        
        new_qty = c.execute("SELECT quantity FROM inventory WHERE id=?", (p["id"],)).fetchone()[0] - p["quantity"]
        c.execute("UPDATE inventory SET quantity=? WHERE id=?", (new_qty, p["id"]))
    
    conn.commit()
    return {"message": "Multi-item invoice created successfully and stock updated!"}

@app.get("/invoices/{invoice_id}/print-html", response_class=HTMLResponse)
def print_invoice_html(invoice_id: int):
    c.execute("SELECT id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method FROM invoices WHERE id=?", (invoice_id,))
    inv = c.fetchone()
    if not inv:
        return "<h1>Invoice not found</h1>", 404
    
    c.execute("SELECT company_name, address, phone, email, website, iban, bic, ust_id, hrb, amtsgericht, director, payment_terms FROM company_settings WHERE id=1")
    comp = c.fetchone()
    comp_name = comp[0] if comp else "Darnieto GmbH"
    comp_addr = comp[1] if comp else "Terofalstr. 69, 80689 München"
    comp_phone = comp[2] if comp else ""
    comp_email = comp[3] if comp else ""
    comp_web = comp[4] if comp else ""
    comp_iban = comp[5] if comp else ""
    comp_bic = comp[6] if comp else ""
    comp_ust = comp[7] if comp else ""
    comp_hrb = comp[8] if comp else ""
    comp_amts = comp[9] if comp else ""
    comp_dir = comp[10] if comp else ""
    comp_terms = comp[11] if comp else "Bitte überweisen Sie den Rechnungsbetrag innerhalb von 7 Tagen ab Rechnungsdatum auf unser unten genanntes Konto."

    c.execute("SELECT item_name, quantity, unit_price, net_total FROM invoice_items WHERE invoice_id=?", (invoice_id,))
    items = c.fetchall()
    
    items_html = "".join([f"<tr><td style='text-align:center;'>{idx+1}</td><td>{i[0]}</td><td style='text-align:center;'>{i[1]}</td><td style='text-align:center;'>Karton</td><td style='text-align:right;'>{i[2]:.2f} €</td><td style='text-align:right;'>{i[3]:.2f} €</td></tr>" for idx, i in enumerate(items)])
    vat_percent = int(inv[7] * 100)
    pay_method = "Überweisung" if inv[11] == "Bank" else "Barzahlung"

    html_content = f"""
    <!DOCTYPE html>
    <html lang="de">
    <head>
        <meta charset="UTF-8">
        <title>Rechnung Nr. {inv[4]}</title>
        <style>
            body {{ font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; margin: 30px; color: #1e293b; background: #fff; font-size: 13px; }}
            .container {{ max-width: 800px; margin: auto; border: 1px solid #cbd5e1; padding: 40px; border-radius: 6px; position: relative; min-height: 1050px; box-sizing: border-box; }}
            .top-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 40px; }}
            .logo-area {{ background: #dc2626; color: white; padding: 10px 20px; font-weight: bold; font-size: 20px; border-radius: 4px; display: inline-block; font-style: italic; }}
            .invoice-meta {{ text-align: right; font-size: 13px; line-height: 1.6; }}
            .invoice-meta table {{ width: auto; margin-left: auto; border: none; }}
            .invoice-meta td {{ border: none; padding: 2px 8px; }}
            .addresses {{ display: flex; justify-content: space-between; margin-bottom: 30px; font-size: 13px; line-height: 1.5; }}
            .sender-line {{ font-size: 10px; text-decoration: underline; color: #475569; margin-bottom: 10px; }}
            table.items-table {{ width: 100%; border-collapse: collapse; margin-bottom: 25px; }}
            table.items-table th, table.items-table td {{ border: 1px solid #94a3b8; padding: 8px 10px; font-size: 13px; }}
            table.items-table th {{ background-color: #f1f5f9; color: #0f172a; text-align: left; font-weight: bold; }}
            .totals-table {{ width: 350px; margin-left: auto; border-collapse: collapse; margin-bottom: 30px; }}
            .totals-table td {{ border: 1px solid #94a3b8; padding: 6px 10px; }}
            .payment-terms {{ font-size: 12px; line-height: 1.5; margin-bottom: 30px; color: #334155; }}
            .qr-section {{ display: flex; align-items: center; gap: 15px; margin-bottom: 40px; }}
            .qr-box {{ border: 1px solid #cbd5e1; padding: 10px; width: 80px; height: 80px; text-align: center; font-size: 10px; background: #f8fafc; }}
            .footer {{ position: absolute; bottom: 30px; left: 40px; right: 40px; display: flex; justify-content: space-between; font-size: 10px; color: #475569; border-top: 1px solid #cbd5e1; padding-top: 15px; line-height: 1.4; }}
            .footer div {{ flex: 1; }}
        </style>
    </head>
    <body onload="window.print()">
        <div class="container">
            <div class="top-header">
                <div>
                    <div class="logo-area">{comp_name}</div>
                </div>
                <div class="invoice-meta">
                    <h2 style="margin: 0 0 10px 0; font-size: 22px;">Rechnung</h2>
                    <table>
                        <tr><td>Rechnungsnr.:</td><td><strong>{inv[4]}</strong></td></tr>
                        <tr><td>Kundennr.:</td><td>10168</td></tr>
                        <tr><td>Datum:</td><td>{inv[5]}</td></tr>
                        <tr><td>Lieferdatum:</td><td>{inv[5]}</td></tr>
                    </table>
                </div>
            </div>

            <div class="sender-line">{comp_name}, {comp_addr}</div>

            <div class="addresses">
                <div>
                    <strong>{inv[1]}</strong><br>
                    {inv[2]}
                </div>
                <div style="text-align: right; font-size: 12px;">
                    {comp_name}<br>
                    {comp_addr.replace(', ', '<br>')}
                </div>
            </div>

            <table class="items-table">
                <thead>
                    <tr>
                        <th style="width: 40px; text-align: center;">Pos.</th>
                        <th>Bezeichnung</th>
                        <th style="width: 60px; text-align: center;">Menge</th>
                        <th style="width: 70px; text-align: center;">Einheit</th>
                        <th style="width: 90px; text-align: right;">Einzel €</th>
                        <th style="width: 90px; text-align: right;">Gesamt €</th>
                    </tr>
                </thead>
                <tbody>
                    {items_html}
                </tbody>
            </table>

            <table class="totals-table">
                <tr>
                    <td>Zwischensumme (netto)</td>
                    <td style="text-align: right;">{inv[6]:.2f} €</td>
                </tr>
                <tr>
                    <td>abzgl. Rabatt</td>
                    <td style="text-align: right;">0,00 €</td>
                </tr>
                <tr>
                    <td><strong>Gesamt (netto)</strong></td>
                    <td style="text-align: right;"><strong>{inv[6]:.2f} €</strong></td>
                </tr>
                <tr>
                    <td>Umsatzsteuer {vat_percent} %</td>
                    <td style="text-align: right;">{inv[8]:.2f} €</td>
                </tr>
                <tr style="background-color: #f1f5f9; font-size: 14px;">
                    <td><strong>Gesamtbetrag</strong></td>
                    <td style="text-align: right;"><strong>{inv[9]:.2f} €</strong></td>
                </tr>
            </table>

            <div class="payment-terms">
                Zahlungsart: {pay_method}<br>
                {comp_terms}<br><br>
                Nach Ablauf dieser Frist gerät der Kunde ohne weitere Mahnung in Verzug.<br>
                Es werden gesetzliche Verzugszinsen sowie Mahngebühren erhoben.<br>
                Für weitere Fragen stehen wir Ihnen gerne zur Verfügung.
            </div>

            <div class="qr-section">
                <div class="qr-box">
                    [ QR Code ]
                </div>
                <div style="font-size: 11px;">
                    <strong>Überweisen per Code</strong><br>
                    Ganz bequem Code mit der<br>Banking-App scannen.
                </div>
            </div>

            <div class="footer">
                <div>
                    {comp_name}<br>
                    {comp_addr.replace(', ', '<br>')}<br>
                    🌐 {comp_web}
                </div>
                <div>
                    📞 {comp_phone}<br>
                    ✉️ {comp_email}
                </div>
                <div>
                    Bankverbindung:<br>
                    IBAN: {comp_iban}<br>
                    BIC: {comp_bic}
                </div>
                <div>
                    UST.-ID: {comp_ust}<br>
                    {comp_hrb}<br>
                    Amtsgericht: {comp_amts}<br>
                    Geschäftsführer: {comp_dir}
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

@app.get("/journal-entries/")
def get_journal_entries():
    c.execute("SELECT id, date, description, debit_account_id, credit_account_id, amount FROM journal_entries")
    return [{"id": r[0], "date": r[1], "description": r[2], "debit_account_id": r[3], "credit_account_id": r[4], "amount": r[5]} for r in c.fetchall()]

@app.post("/journal-entries/")
def create_journal_entry(entry: JournalEntryCreate):
    c.execute("INSERT INTO journal_entries (date, description, debit_account_id, credit_account_id, amount) VALUES (?, ?, ?, ?, ?)",
              (entry.date, entry.description, entry.debit_account_id, entry.credit_account_id, entry.amount))
    conn.commit()
    return {"message": "Journal entry posted successfully"}

@app.get("/receipts/")
def get_receipts():
    c.execute("SELECT id, date, vendor, net_amount, vat_amount, gross_amount FROM receipts")
    return [{"id": r[0], "date": r[1], "vendor": r[2], "net_amount": r[3], "vat_amount": r[4], "gross_amount": r[5]} for r in c.fetchall()]

@app.post("/receipts/")
def create_receipt(receipt: ReceiptCreate):
    vat_amount = receipt.net_amount * receipt.vat_rate
    gross_amount = receipt.net_amount + vat_amount
    c.execute("INSERT INTO receipts (date, vendor, net_amount, vat_amount, gross_amount) VALUES (?, ?, ?, ?, ?)",
              (receipt.date, receipt.vendor, receipt.net_amount, vat_amount, gross_amount))
    conn.commit()
    return {"message": "Receipt saved successfully"}

@app.get("/inventory/")
def get_inventory():
    c.execute("""
        SELECT inv.id, inv.supplier_id, inv.name, inv.sku, inv.quantity, inv.unit_price, sup.name 
        FROM inventory inv 
        LEFT JOIN suppliers sup ON inv.supplier_id = sup.id
    """)
    return [{
        "id": r[0], "supplier_id": r[1], "name": r[2], "sku": r[3], 
        "quantity": r[4], "unit_price": r[5], "supplier_name": r[6] or "General"
    } for r in c.fetchall()]

@app.post("/inventory/")
def create_inventory_item(item: InventoryItemCreate):
    c.execute("""
        INSERT INTO inventory (supplier_id, name, sku, quantity, unit_price)
        VALUES (?, ?, ?, ?, ?)
    """, (item.supplier_id, item.name, item.sku, item.quantity, item.unit_price))
    conn.commit()
    return {"message": "Inventory item added successfully"}

@app.put("/inventory/{item_id}")
def update_inventory_item(item_id: int, item: InventoryItemUpdate):
    c.execute("""
        UPDATE inventory SET supplier_id=?, name=?, sku=?, quantity=?, unit_price=?
        WHERE id=?
    """, (item.supplier_id, item.name, item.sku, item.quantity, item.unit_price, item_id))
    conn.commit()
    return {"message": "Inventory item updated successfully"}

@app.delete("/inventory/{item_id}")
def delete_inventory_item(item_id: int):
    c.execute("DELETE FROM inventory WHERE id=?", (item_id,))
    conn.commit()
    return {"message": "Inventory item deleted successfully"}
