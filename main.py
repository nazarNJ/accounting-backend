from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Date
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from typing import List
import datetime

DATABASE_URL = "sqlite:///./accounting.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_number = Column(Integer, unique=True, index=True)
    account_name = Column(String, index=True)
    account_type = Column(String)
    balance = Column(Float, default=0.0)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, default=datetime.date.today)
    description = Column(String)
    lines = relationship("JournalEntryLine", back_populates="entry", cascade="all, delete-orphan")

class JournalEntryLine(Base):
    __tablename__ = "journal_entry_lines"
    id = Column(Integer, primary_key=True, index=True)
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id"))
    account_id = Column(Integer, ForeignKey("accounts.id"))
    debit = Column(Float, default=0.0)
    credit = Column(Float, default=0.0)
    
    entry = relationship("JournalEntry", back_populates="lines")
    account = relationship("Account")

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class AccountCreate(BaseModel):
    account_number: int
    account_name: str
    account_type: str
    balance: float = 0.0

@app.get("/accounts/")
def read_accounts(db: Session = Depends(get_db)):
    return db.query(Account).all()

@app.post("/accounts/")
def create_account(account: AccountCreate, db: Session = Depends(get_db)):
    existing = db.query(Account).filter(Account.account_number == account.account_number).first()
    if existing:
        raise HTTPException(status_code=400, detail="رقم الحساب موجود مسبقاً")
    db_account = Account(**account.dict())
    db.add(db_account)
    db.commit()
    db.refresh(db_account)
    return db_account

class JournalLineCreate(BaseModel):
    account_id: int
    debit: float = 0.0
    credit: float = 0.0

class JournalEntryCreate(BaseModel):
    date: datetime.date
    description: str
    lines: List[JournalLineCreate]

@app.post("/journal-entries/")
def create_journal_entry(entry: JournalEntryCreate, db: Session = Depends(get_db)):
    total_debit = sum(line.debit for line in entry.lines)
    total_credit = sum(line.credit for line in entry.lines)
    
    if abs(total_debit - total_credit) > 0.001:
        raise HTTPException(status_code=400, detail="القيد غير متوازن: إجمالي المدين يجب أن يساوي إجمالي الدائن")
    
    db_entry = JournalEntry(date=entry.date, description=entry.description)
    db.add(db_entry)
    db.commit()
    db.refresh(db_entry)
    
    for line in entry.lines:
        db_line = JournalEntryLine(
            journal_entry_id=db_entry.id,
            account_id=line.account_id,
            debit=line.debit,
            credit=line.credit
        )
        db.add(db_line)
        
        acc = db.query(Account).filter(Account.id == line.account_id).first()
        if acc:
            if acc.account_type in ["أصول", "مصروفات"]:
                acc.balance += (line.debit - line.credit)
            else:
                acc.balance += (line.credit - line.debit)
                
    db.commit()
    return {"message": "تم تسجيل القيد بنجاح، وهو متوازن!", "entry_id": db_entry.id}

@app.get("/journal-entries/")
def read_journal_entries(db: Session = Depends(get_db)):
    entries = db.query(JournalEntry).all()
    result = []
    for e in entries:
        lines_data = []
        for l in e.lines:
            acc_name = l.account.account_name if l.account else "حساب محذوف"
            lines_data.append({
                "account_id": l.account_id,
                "account_name": acc_name,
                "debit": l.debit,
                "credit": l.credit
            })
        result.append({
            "id": e.id,
            "date": str(e.date),
            "description": e.description,
            "lines": lines_data
        })
    return result

@app.get("/trial-balance/")
def trial_balance(db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    tb_data = []
    total_debit_sum = 0.0
    total_credit_sum = 0.0
    
    for acc in accounts:
        lines = db.query(JournalEntryLine).filter(JournalEntryLine.account_id == acc.id).all()
        tot_debit = sum(l.debit for l in lines)
        tot_credit = sum(l.credit for l in lines)
        
        tb_data.append({
            "account_number": acc.account_number,
            "account_name": acc.account_name,
            "total_debit": tot_debit,
            "total_credit": tot_credit,
            "current_balance": acc.balance
        })
        total_debit_sum += tot_debit
        total_credit_sum += tot_credit
        
    return {
        "accounts": tb_data,
        "total_debit": total_debit_sum,
        "total_credit": total_credit_sum,
        "is_balanced": abs(total_debit_sum - total_credit_sum) < 0.001
    }
@app.get("/income-statement/")
def income_statement(db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    revenues = [acc for acc in accounts if acc.account_type == "إيرادات"]
    expenses = [acc for acc in accounts if acc.account_type == "مصروفات"]
    
    total_revenue = sum(acc.balance for acc in revenues)
    total_expense = sum(acc.balance for acc in expenses)
    net_income = total_revenue - total_expense
    
    return {
        "revenues": [{"account_name": acc.account_name, "balance": acc.balance} for acc in revenues],
        "expenses": [{"account_name": acc.account_name, "balance": acc.balance} for acc in expenses],
        "total_revenue": total_revenue,
        "total_expense": total_expense,
        "net_income": net_income
    }

@app.get("/balance-sheet/")
def balance_sheet(db: Session = Depends(get_db)):
    accounts = db.query(Account).all()
    assets = [acc for acc in accounts if acc.account_type == "أصول"]
    liabilities = [acc for acc in accounts if acc.account_type == "خصوم"]
    equity = [acc for acc in accounts if acc.account_type == "حقوق ملكية"]
    
    total_assets = sum(acc.balance for acc in assets)
    total_liabilities = sum(acc.balance for acc in liabilities)
    total_equity = sum(acc.balance for acc in equity)
    
    return {
        "assets": [{"account_name": acc.account_name, "balance": acc.balance} for acc in assets],
        "liabilities": [{"account_name": acc.account_name, "balance": acc.balance} for acc in liabilities],
        "equity": [{"account_name": acc.account_name, "balance": acc.balance} for acc in equity],
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_equity": total_equity,
        "is_balanced": abs(total_assets - (total_liabilities + total_equity)) < 0.001
    }
# أضف هذه الجداول في قاعدة البيانات داخل main.py
c.execute('''
    CREATE TABLE IF NOT EXISTS suppliers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        address TEXT,
        ust_id TEXT
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS invoices (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        supplier_id INTEGER,
        invoice_number TEXT NOT NULL,
        date TEXT NOT NULL,
        net_amount REAL NOT NULL,
        vat_rate REAL NOT NULL, -- 0.19 أو 0.07
        vat_amount REAL NOT NULL,
        gross_amount REAL NOT NULL,
        FOREIGN KEY (supplier_id) REFERENCES suppliers (id)
    )
''')
conn.commit()

# أضف هذه الـ Endpoints للـ FastAPI:
from pydantic import BaseModel

class SupplierCreate(BaseModel):
    name: str
    address: str
    ust_id: str

class InvoiceCreate(BaseModel):
    supplier_id: int
    invoice_number: str
    date: str
    net_amount: float
    vat_rate: float # 0.19 أو 0.07

@app.get("/suppliers/")
def get_suppliers():
    c.execute("SELECT * FROM suppliers")
    return [{"id": row[0], "name": row[1], "address": row[2], "ust_id": row[3]} for row in c.fetchall()]

@app.post("/suppliers/")
def create_supplier(sup: SupplierCreate):
    c.execute("INSERT INTO suppliers (name, address, ust_id) VALUES (?, ?, ?)", 
              (sup.name, sup.address, sup.ust_id))
    conn.commit()
    return {"message": "Supplier created successfully"}

@app.get("/invoices/")
def get_invoices():
    c.execute("""
        SELECT i.id, s.name, i.invoice_number, i.date, i.net_amount, i.vat_rate, i.vat_amount, i.gross_amount 
        FROM invoices i JOIN suppliers s ON i.supplier_id = s.id
    """)
    return [{
        "id": row[0], "supplier_name": row[1], "invoice_number": row[2], 
        "date": row[3], "net_amount": row[4], "vat_rate": row[5], 
        "vat_amount": row[6], "gross_amount": row[7]
    } for row in c.fetchall()]

@app.post("/invoices/")
def create_invoice(inv: InvoiceCreate):
    vat_amount = inv.net_amount * inv.vat_rate
    gross_amount = inv.net_amount + vat_amount
    c.execute("""
        INSERT INTO invoices (supplier_id, invoice_number, date, net_amount, vat_rate, vat_amount, gross_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (inv.supplier_id, inv.invoice_number, inv.date, inv.net_amount, inv.vat_rate, vat_amount, gross_amount))
    conn.commit()
    return {"message": "Invoice created successfully", "gross_amount": gross_amount}
# أضف هذا الجدول في قاعدة البيانات داخل main.py
c.execute('''
    CREATE TABLE IF NOT EXISTS journal_entries (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        description TEXT NOT NULL,
        debit_account_id INTEGER,
        credit_account_id INTEGER,
        amount REAL NOT NULL,
        FOREIGN KEY (debit_account_id) REFERENCES accounts (id),
        FOREIGN KEY (credit_account_id) REFERENCES accounts (id)
    )
''')
conn.commit()

# أضف نموذج البيانات و الـ Endpoints الخاصة بالقيود:
class JournalEntryCreate(BaseModel):
    date: str
    description: str
    debit_account_id: int
    credit_account_id: int
    amount: float

@app.get("/journal-entries/")
def get_journal_entries():
    c.execute("""
        SELECT j.id, j.date, j.description, d.account_name, cr.account_name, j.amount 
        FROM journal_entries j
        JOIN accounts d ON j.debit_account_id = d.id
        JOIN accounts cr ON j.credit_account_id = cr.id
    """)
    return [{
        "id": row[0], "date": row[1], "description": row[2],
        "debit_account": row[3], "credit_account": row[4], "amount": row[5]
    } for row in c.fetchall()]

@app.post("/journal-entries/")
def create_journal_entry(entry: JournalEntryCreate):
    c.execute("""
        INSERT INTO journal_entries (date, description, debit_account_id, credit_account_id, amount)
        VALUES (?, ?, ?, ?, ?)
    """, (entry.date, entry.description, entry.debit_account_id, entry.credit_account_id, entry.amount))
    
    # تحديث أرصدة الحسابات تلقائياً (مدين يزيد، دائن ينقص)
    c.execute("UPDATE accounts SET balance = balance + ? WHERE id = ?", (entry.amount, entry.debit_account_id))
    c.execute("UPDATE accounts SET balance = balance - ? WHERE id = ?", (entry.amount, entry.credit_account_id))
    conn.commit()
    return {"message": "Journal entry created successfully"}
# أضف هذا الجدول في قاعدة البيانات داخل main.py
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

class InventoryItemCreate(BaseModel):
    name: str
    sku: str
    quantity: int
    unit_price: float

@app.get("/inventory/")
def get_inventory():
    c.execute("SELECT id, name, sku, quantity, unit_price FROM inventory")
    return [{
        "id": row[0], "name": row[1], "sku": row[2],
        "quantity": row[3], "unit_price": row[4]
    } for row in c.fetchall()]

@app.post("/inventory/")
def create_inventory_item(item: InventoryItemCreate):
    c.execute("""
        INSERT INTO inventory (name, sku, quantity, unit_price)
        VALUES (?, ?, ?, ?)
    """, (item.name, item.sku, item.quantity, item.unit_price))
    conn.commit()
    return {"message": "Inventory item added successfully"}
