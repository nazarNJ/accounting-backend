import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

conn = sqlite3.connect('accounting.db', check_same_thread=False)
c = conn.cursor()

# إنشاء الجداول
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
        buyer_name TEXT,
        buyer_address TEXT,
        buyer_ust_id TEXT,
        invoice_number TEXT NOT NULL,
        date TEXT NOT NULL,
        net_amount REAL NOT NULL,
        vat_rate REAL NOT NULL,
        vat_amount REAL NOT NULL,
        gross_amount REAL NOT NULL,
        status TEXT DEFAULT 'Unpaid'
    )
''')

for col, col_type in [
    ("buyer_name", "TEXT"),
    ("buyer_address", "TEXT"),
    ("buyer_ust_id", "TEXT"),
    ("status", "TEXT DEFAULT 'Unpaid'")
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

# تعديل الكمية إلى REAL لدعم الأوزان والأرقام العشرية
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
    supplier_id: int = 1
    buyer_name: str
    buyer_address: str
    buyer_ust_id: str = ""
    invoice_number: str
    date: str
    net_amount: float
    vat_rate: float
    status: str = "Unpaid"

class InvoiceUpdate(BaseModel):
    supplier_id: int = 1
    buyer_name: str
    buyer_address: str
    buyer_ust_id: str = ""
    invoice_number: str
    date: str
    net_amount: float
    vat_rate: float
    status: str

class InvoiceFromInventoryCreate(BaseModel):
    supplier_id: int
    inventory_item_id: int
    quantity: float
    invoice_number: str
    date: str
    vat_rate: float
    status: str = "Unpaid"

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
    c.execute("SELECT id, supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status FROM invoices")
    return [{
        "id": r[0], "supplier_id": r[1], "buyer_name": r[2], "buyer_address": r[3], "buyer_ust_id": r[4],
        "invoice_number": r[5], "date": r[6], "net_amount": r[7], "vat_rate": r[8], "vat_amount": r[9], "gross_amount": r[10], "status": r[11]
    } for r in c.fetchall()]

@app.post("/invoices/")
def create_invoice(inv: InvoiceCreate):
    vat_amount = inv.net_amount * inv.vat_rate
    gross_amount = inv.net_amount + vat_amount
    c.execute("""
        INSERT INTO invoices (supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (inv.supplier_id, inv.buyer_name, inv.buyer_address, inv.buyer_ust_id, inv.invoice_number, inv.date, inv.net_amount, inv.vat_rate, vat_amount, gross_amount, inv.status))
    conn.commit()
    return {"message": "German § 14 Invoice created successfully"}

@app.put("/invoices/{invoice_id}")
def update_invoice(invoice_id: int, inv: InvoiceUpdate):
    vat_amount = inv.net_amount * inv.vat_rate
    gross_amount = inv.net_amount + vat_amount
    c.execute("""
        UPDATE invoices SET supplier_id=?, buyer_name=?, buyer_address=?, buyer_ust_id=?, invoice_number=?, date=?, net_amount=?, vat_rate=?, vat_amount=?, gross_amount=?, status=?
        WHERE id=?
    """, (inv.supplier_id, inv.buyer_name, inv.buyer_address, inv.buyer_ust_id, inv.invoice_number, inv.date, inv.net_amount, inv.vat_rate, vat_amount, gross_amount, inv.status, invoice_id))
    conn.commit()
    return {"message": "Invoice updated successfully"}

@app.post("/invoices/from-inventory/")
def create_invoice_from_inventory(data: InvoiceFromInventoryCreate):
    c.execute("SELECT name, quantity, unit_price FROM inventory WHERE id=?", (data.inventory_item_id,))
    item = c.fetchone()
    if not item:
        return {"error": "Inventory item not found"}
    
    item_name, stock_qty, unit_price = item
    if stock_qty < data.quantity:
        return {"error": "Not enough stock available"}
    
    net_amount = unit_price * data.quantity
    vat_amount = net_amount * data.vat_rate
    gross_amount = net_amount + vat_amount
    
    c.execute("""
        INSERT INTO invoices (supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (data.supplier_id, "Standard Buyer", "Germany", "", data.invoice_number, data.date, net_amount, data.vat_rate, vat_amount, gross_amount, data.status))
    
    new_qty = stock_qty - data.quantity
    c.execute("UPDATE inventory SET quantity=? WHERE id=?", (new_qty, data.inventory_item_id))
    conn.commit()
    
    return {"message": "Invoice created from inventory and stock updated successfully"}

@app.get("/invoices/{invoice_id}/erechnung-xml")
def export_erechnung_xml(invoice_id: int):
    c.execute("SELECT id, supplier_id, buyer_name, buyer_address, buyer_ust_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount, status FROM invoices WHERE id=?", (invoice_id,))
    row = c.fetchone()
    if not row:
        return {"error": "Invoice not found"}
    
    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                         xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100">
    <rsm:ExchangedDocument>
        <ram:ID>{row[5]}</ram:ID>
        <ram:IssueDateTime>{row[6]}</ram:IssueDateTime>
    </rsm:ExchangedDocument>
    <rsm:SupplyChainTradeTransaction>
        <ram:ApplicableHeaderTradeAgreement>
            <ram:BuyerTradeParty>
                <ram:Name>{row[2]}</ram:Name>
                <ram:PostalTradeAddress><ram:LineOne>{row[3]}</ram:LineOne></ram:PostalTradeAddress>
                <ram:SpecifiedTaxRegistration><ram:ID>{row[4]}</ram:ID></ram:SpecifiedTaxRegistration>
            </ram:BuyerTradeParty>
        </ram:ApplicableHeaderTradeAgreement>
        <ram:ApplicableHeaderTradeSettlement>
            <ram:SpecifiedTradeSettlementMonetarySummation>
                <ram:LineTotalAmount>{row[7]}</ram:LineTotalAmount>
                <ram:TaxBasisTotalAmount>{row[7]}</ram:TaxBasisTotalAmount>
                <ram:TaxTotalAmount>{row[9]}</ram:TaxTotalAmount>
                <ram:GrandTotalAmount>{row[10]}</ram:GrandTotalAmount>
            </ram:SpecifiedTradeSettlementMonetarySummation>
        </ram:ApplicableHeaderTradeSettlement>
    </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>"""
    return {
        "invoice_number": row[5], 
        "buyer": row[2],
        "standard": "ZUGFeRD / XRechnung (EN 16931)", 
        "status": row[11],
        "xml_data": xml_content
    }

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
