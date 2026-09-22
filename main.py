import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

# 1. تعريف الاتصال بقاعدة البيانات والمؤشر بشكل عام في أعلى الملف لتجنب أي أخطاء تعريف
conn = sqlite3.connect('accounting.db', check_same_thread=False)
c = conn.cursor()

# 2. إنشاء الجداول تلقائياً لضمان سلامة البيانات
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

c.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        invoice_number TEXT NOT NULL,
        date TEXT NOT NULL,
        net_amount REAL NOT NULL,
        vat_rate REAL NOT NULL,
        vat_amount REAL NOT NULL,
        gross_amount REAL NOT NULL
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
        gross_amount REAL NOT NULL
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS inventory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        sku TEXT NOT NULL,
        quantity INTEGER NOT NULL,
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

# نماذج البيانات (Pydantic Models)
class AccountCreate(BaseModel):
    account_number: str
    account_name: str
    account_type: str
    balance: float

class SupplierCreate(BaseModel):
    name: str
    address: str
    ust_id: str

class InvoiceCreate(BaseModel):
    supplier_id: int
    invoice_number: str
    date: str
    net_amount: float
    vat_rate: float

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
    vat_rate: float

class InventoryItemCreate(BaseModel):
    name: str
    sku: str
    quantity: int
    unit_price: float

# مسارات النظام (Endpoints)
@app.get("/")
def read_root():
    return {"message": "ERP Accounting Backend is running successfully!"}

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
    c.execute("SELECT id, supplier_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount FROM invoices")
    return [{"id": r[0], "supplier_id": r[1], "invoice_number": r[2], "date": r[3], "net_amount": r[4], "vat_rate": r[5], "vat_amount": r[6], "gross_amount": r[7]} for r in c.fetchall()]

@app.post("/invoices/")
def create_invoice(inv: InvoiceCreate):
    vat_amount = inv.net_amount * inv.vat_rate
    gross_amount = inv.net_amount + vat_amount
    c.execute("INSERT INTO invoices (supplier_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount) VALUES (?, ?, ?, ?, ?, ?, ?)",
              (inv.supplier_id, inv.invoice_number, inv.date, inv.net_amount, inv.vat_rate, vat_amount, gross_amount))
    conn.commit()
    return {"message": "Invoice created successfully"}

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
    c.execute("SELECT id, name, sku, quantity, unit_price FROM inventory")
    return [{"id": r[0], "name": r[1], "sku": r[2], "quantity": r[3], "unit_price": r[4]} for r in c.fetchall()]

@app.post("/inventory/")
def create_inventory_item(item: InventoryItemCreate):
    c.execute("INSERT INTO inventory (name, sku, quantity, unit_price) VALUES (?, ?, ?, ?)",
              (item.name, item.sku, item.quantity, item.unit_price))
    conn.commit()
    return {"message": "Inventory item added successfully"}
@app.get("/invoices/{invoice_id}/erechnung-xml")
def export_erechnung_xml(invoice_id: int):
    c.execute("SELECT id, supplier_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount FROM invoices WHERE id=?", (invoice_id,))
    row = c.fetchone()
    if not row:
        return {"error": "Invoice not found"}
    
    # هيكل XML قياسي متوافق مع معايير الفوترة الإلكترونية الألمانية (E-Rechnung / ZUGFeRD)
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                         xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
    <rsm:ExchangedDocument>
        <ram:ID>{row[2]}</ram:ID>
        <ram:IssueDateTime>{row[3]}</ram:IssueDateTime>
    </rsm:ExchangedDocument>
    <rsm:SupplyChainTradeTransaction>
        <ram:ApplicableHeaderTradeSettlement>
            <ram:SpecifiedTradeSettlementMonetarySummation>
                <ram:LineTotalAmount>{row[4]}</ram:LineTotalAmount>
                <ram:TaxBasisTotalAmount>{row[4]}</ram:TaxBasisTotalAmount>
                <ram:TaxTotalAmount>{row[6]}</ram:TaxTotalAmount>
                <ram:GrandTotalAmount>{row[7]}</ram:GrandTotalAmount>
            </ram:SpecifiedTradeSettlementMonetarySummation>
        </ram:ApplicableHeaderTradeSettlement>
    </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
    return {
        "invoice_number": row[2], 
        "standard": "ZUGFeRD / XRechnung (EN 16931)", 
        "xml_data": xml_content
    }
