import sqlite3
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os

conn = sqlite3.connect('accounting.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول الأساسية
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        identifier TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        name TEXT
    )
''')

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

# جدول العمال والموظفين
c.execute('''
    CREATE TABLE IF NOT EXISTS workers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        position TEXT,
        hourly_rate REAL DEFAULT 0.0,
        phone TEXT
    )
''')

# جدول مصروفات وأجور العمال
c.execute('''
    CREATE TABLE IF NOT EXISTS worker_expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        worker_id INTEGER,
        date TEXT NOT NULL,
        hours_worked REAL DEFAULT 0.0,
        amount REAL NOT NULL,
        description TEXT
    )
''')

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
        VALUES ('', '', '', '', '', '', '', '', '', '', '', '')
    ''')
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
        payment_method TEXT DEFAULT 'Bank',
        is_storno INTEGER DEFAULT 0,
        original_invoice_number TEXT DEFAULT ''
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
        gross_amount REAL NOT NULL,
        image_path TEXT DEFAULT ''
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

os.makedirs("uploads", exist_ok=True)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserRegister(BaseModel):
    identifier: str
    password: str
    name: str = ""

class UserLogin(BaseModel):
    identifier: str
    password: str

class WorkerCreate(BaseModel):
    name: str
    position: str = ""
    hourly_rate: float = 0.0
    phone: str = ""

class WorkerExpenseCreate(BaseModel):
    worker_id: int
    date: str
    hours_worked: float = 0.0
    amount: float
    description: str = ""

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
    return {"message": "ERP Accounting Backend with Workers is running successfully!"}

@app.post("/auth/register")
def register_user(data: UserRegister):
    try:
        c.execute("INSERT INTO users (identifier, password, name) VALUES (?, ?, ?)", (data.identifier, data.password, data.name))
        conn.commit()
        return {"message": "User registered successfully"}
    except sqlite3.IntegrityError:
        return {"error": "User with this email or mobile already exists"}

@app.post("/auth/login")
def login_user(data: UserLogin):
    c.execute("SELECT id, name, identifier FROM users WHERE identifier=? AND password=?", (data.identifier, data.password))
    row = c.fetchone()
    if not row:
        return {"error": "Invalid email/mobile or password"}
    return {"message": "Login successful", "user": {"id": row[0], "name": row[1], "identifier": row[2]}}

# إدارة العمال
@app.get("/workers/")
def get_workers():
    c.execute("SELECT id, name, position, hourly_rate, phone FROM workers")
    return [{"id": r[0], "name": r[1], "position": r[2], "hourly_rate": r[3], "phone": r[4]} for r in c.fetchall()]

@app.post("/workers/")
def create_worker(w: WorkerCreate):
    c.execute("INSERT INTO workers (name, position, hourly_rate, phone) VALUES (?, ?, ?, ?)",
              (w.name, w.position, w.hourly_rate, w.phone))
    conn.commit()
    return {"message": "Worker added successfully"}

@app.delete("/workers/{worker_id}")
def delete_worker(worker_id: int):
    c.execute("DELETE FROM workers WHERE id=?", (worker_id,))
    conn.commit()
    return {"message": "Worker deleted successfully"}

# مصروفات وأجور العمال
@app.get("/worker-expenses/")
def get_worker_expenses():
    c.execute("""
        SELECT we.id, we.worker_id, we.date, we.hours_worked, we.amount, we.description, w.name 
        FROM worker_expenses we 
        LEFT JOIN workers w ON we.worker_id = w.id
    """)
    return [{
        "id": r[0], "worker_id": r[1], "date": r[2], "hours_worked": r[3], 
        "amount": r[4], "description": r[5], "worker_name": r[6] or "Unknown"
    } for r in c.fetchall()]

@app.post("/worker-expenses/")
def create_worker_expense(we: WorkerExpenseCreate):
    c.execute("""
        INSERT INTO worker_expenses (worker_id, date, hours_worked, amount, description)
        VALUES (?, ?, ?, ?, ?)
    """, (we.worker_id, we.date, we.hours_worked, we.amount, we.description))
    conn.commit()
    return {"message": "Worker expense added successfully"}

@app.delete("/worker-expenses/{expense_id}")
def delete_worker_expense(expense_id: int):
    c.execute("DELETE FROM worker_expenses WHERE id=?", (expense_id,))
    conn.commit()
    return {"message": "Worker expense deleted successfully"}

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
        SET company_name=?, address=?, phone=?, email=?, website=?, iban=?, bic=?, ust_id=?, hrb=?, amtsgericht=?, director=?, payment_terms=?
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
    c.execute("SELECT id, supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method, is_storno, original_invoice_number FROM invoices")
    invoices = []
    for r in c.fetchall():
        inv_id = r[0]
        c.execute("SELECT item_name, quantity, unit_price, net_total FROM invoice_items WHERE invoice_id=?", (inv_id,))
        items = [{"name": i[0], "quantity": i[1], "unit_price": i[2], "net_total": i[3]} for i in c.fetchall()]
        invoices.append({
            "id": inv_id, "supplier_id": r[1], "buyer_name": r[2], "buyer_address": r[3], "buyer_ust_id": r[4],
            "invoice_number": r[5], "date": r[6], "net_amount": r[7], "vat_rate": r[8], "vat_amount": r[9], 
            "gross_amount": r[10], "status": r[11], "payment_method": r[12], "is_storno": r[13], "original_invoice_number": r[14], "items": items
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
        INSERT INTO invoices (supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method, is_storno, original_invoice_number)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, '')
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

@app.post("/invoices/{invoice_id}/storno")
def create_storno_invoice(invoice_id: int):
    c.execute("SELECT supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, payment_method FROM invoices WHERE id=?", (invoice_id,))
    inv = c.fetchone()
    if not inv:
        return {"error": "Original invoice not found"}
    
    orig_num = inv[4]
    storno_num = f"ST-{orig_num}"
    
    c.execute("SELECT id FROM invoices WHERE invoice_number=?", (storno_num,))
    if c.fetchone():
        return {"error": "Storno invoice already exists for this number"}

    net_amt = -inv[6]
    vat_amt = -inv[8]
    gross_amt = -inv[9]
    
    c.execute("""
        INSERT INTO invoices (supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status, payment_method, is_storno, original_invoice_number)
        VALUES (?, ?, ?, ?, ?, datetime('now', 'localtime'), ?, ?, ?, ?, 'Cancelled', ?, 1, ?)
    """, (inv[0], inv[1], inv[2], inv[3], storno_num, net_amt, inv[7], vat_amt, gross_amt, inv[10], orig_num))
    
    storno_id = c.lastrowid
    
    c.execute("SELECT inventory_item_id, item_name, quantity, unit_price, net_total FROM invoice_items WHERE invoice_id=?", (invoice_id,))
    items = c.fetchall()
    for item in items:
        inv_item_id, name, qty, price, net_tot = item
        c.execute("""
            INSERT INTO invoice_items (invoice_id, inventory_item_id, item_name, quantity, unit_price, net_total)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (storno_id, inv_item_id, name, qty, price, -net_tot))
        
        if inv_item_id:
            c.execute("UPDATE inventory SET quantity = quantity + ? WHERE id=?", (qty, inv_item_id))
            
    conn.commit()
    return {"message": "Storno invoice created successfully and inventory restored!", "storno_invoice_number": storno_num}

@app.get("/export/datev", response_class=PlainTextResponse)
def export_datev():
    c.execute("SELECT invoice_number, date, net_amount, vat_amount, gross_amount, buyer_name FROM invoices")
    rows = c.fetchall()
    csv_data = "Rechnungsnummer;Datum;Netto;Umsatzsteuer;Brutto;Kunde\n"
    for r in rows:
        csv_data += f"{r[0]};{r[1]};{r[2]:.2f};{r[3]:.2f};{r[4]:.2f};{r[5]}\n"
    return csv_data

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
    c.execute("SELECT id, date, vendor, net_amount, vat_amount, gross_amount, image_path FROM receipts")
    return [{"id": r[0], "date": r[1], "vendor": r[2], "net_amount": r[3], "vat_amount": r[4], "gross_amount": r[5], "image_path": r[6]} for r in c.fetchall()]

@app.post("/receipts/")
def create_receipt(receipt: BaseModel):
    # simple receipt endpoint matching frontend
    pass

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

@app.delete("/inventory/{item_id}")
def delete_inventory_item(item_id: int):
    c.execute("DELETE FROM inventory WHERE id=?", (item_id,))
    conn.commit()
    return {"message": "Inventory item deleted successfully"}
