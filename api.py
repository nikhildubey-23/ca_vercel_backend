from fastapi import FastAPI, Depends, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import requests

load_dotenv()

# Config
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///taxpilot.db')
JWT_SECRET = os.environ.get('JWT_SECRET', 'taxpilot-secret-key')
JWT_ALGORITHM = "HS256"
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '')
GROQ_MODEL = os.environ.get('GROQ_MODEL', 'llama-3.1-70b-versatile')

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security
security = HTTPBearer()

# FastAPI app
app = FastAPI(title="TaxPilot API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory DB (for demo - use real DB in production)
users_db = {}
folders_db = []
documents_db = []
next_user_id = 1
next_folder_id = 1
next_doc_id = 1

# Models
class User(BaseModel):
    email: str
    name: str
    password: str
    pan: str = None
    phone: str = None

class Login(BaseModel):
    email: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"

# Helper functions
def create_token(user_id: int) -> str:
    expire = datetime.utcnow() + timedelta(hours=24)
    to_encode = {"sub": str(user_id), "exp": expire}
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str) -> int:
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return int(payload.get("sub"))
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_current_user(request: Request):
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    token = auth_header.split(" ")[1]
    user_id = verify_token(token)
    for u in users_db.values():
        if u["id"] == user_id:
            return u
    raise HTTPException(status_code=401, detail="User not found")

# Routes
@app.get("/api/health")
def health():
    return {"status": "ok", "message": "TaxPilot API Running"}

@app.post("/api/auth/register")
def register(user: User):
    global next_user_id
    if any(u["email"] == user.email for u in users_db.values()):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    new_user = {
        "id": next_user_id,
        "email": user.email,
        "name": user.name,
        "password_hash": pwd_context.hash(user.password),
        "pan": user.pan,
        "phone": user.phone,
        "role": "user"
    }
    users_db[next_user_id] = new_user
    next_user_id += 1
    
    token = create_token(new_user["id"])
    return {
        "message": "User registered successfully",
        "user": {k: v for k, v in new_user.items() if k != "password_hash"},
        "access_token": token
    }

@app.post("/api/auth/login")
def login(credentials: Login):
    for u in users_db.values():
        if u["email"] == credentials.email:
            if not pwd_context.verify(credentials.password, u["password_hash"]):
                raise HTTPException(status_code=401, detail="Invalid credentials")
            token = create_token(u["id"])
            return {
                "message": "Login successful",
                "user": {k: v for k, v in u.items() if k != "password_hash"},
                "access_token": token
            }
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.get("/api/auth/profile")
def profile(user = Depends(get_current_user)):
    return {"user": user}

@app.get("/api/folders")
def get_folders(user = Depends(get_current_user)):
    user_folders = [f for f in folders_db if f["owner_id"] == user["id"] or f.get("is_shared")]
    return {"folders": user_folders}

@app.post("/api/folders")
def create_folder(data: dict, user = Depends(get_current_user)):
    global next_folder_id
    folder = {
        "id": next_folder_id,
        "name": data.get("name"),
        "description": data.get("description", ""),
        "owner_id": user["id"],
        "is_shared": data.get("is_shared", True)
    }
    folders_db.append(folder)
    next_folder_id += 1
    return {"message": "Folder created", "folder": folder}

@app.get("/api/folders/{folder_id}/documents")
def folder_documents(folder_id: int, user = Depends(get_current_user)):
    docs = [d for d in documents_db if d["folder_id"] == folder_id and d["owner_id"] == user["id"]]
    return {"documents": docs}

@app.get("/api/documents")
def get_documents(user = Depends(get_current_user)):
    user_docs = [d for d in documents_db if d["owner_id"] == user["id"]]
    return {"documents": user_docs}

@app.post("/api/documents/upload")
def upload_document(data: dict, user = Depends(get_current_user)):
    global next_doc_id
    doc = {
        "id": next_doc_id,
        "name": data.get("name", "untitled"),
        "document_type": data.get("document_type", "general"),
        "folder_id": data.get("folder_id"),
        "owner_id": user["id"]
    }
    documents_db.append(doc)
    next_doc_id += 1
    return {"message": "Document uploaded", "document": doc}

@app.delete("/api/documents/{doc_id}")
def delete_document(doc_id: int, user = Depends(get_current_user)):
    global documents_db
    doc = next((d for d in documents_db if d["id"] == doc_id and d["owner_id"] == user["id"]), None)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    documents_db = [d for d in documents_db if d["id"] != doc_id]
    return {"message": "Document deleted"}

@app.get("/api/documents/types")
def document_types():
    return {"types": ["general", "form16", "form26as", "investment", "receipt", "other"]}

def calc_tax(income, deductions, age='general'):
    taxable = max(0, income - deductions)
    exempt = 500000 if age == 'super_senior' else (300000 if age == 'senior' else 250000)
    taxable = max(0, taxable - exempt)
    if taxable <= 0: return {'taxable_income': taxable, 'tax_before_cess': 0, 'cess': 0, 'total_tax': 0}
    tax = 0
    if taxable <= 500000: tax = taxable * 0.05
    elif taxable <= 1000000: tax = 25000 + (taxable - 500000) * 0.20
    elif taxable <= 1500000: tax = 25000 + 100000 + (taxable - 1000000) * 0.20
    elif taxable <= 2000000: tax = 25000 + 100000 + 100000 + (taxable - 1500000) * 0.30
    else: tax = 25000 + 100000 + 100000 + 150000 + (taxable - 2000000) * 0.30
    return {'taxable_income': taxable, 'tax_before_cess': tax, 'cess': tax * 0.04, 'total_tax': tax * 1.04}

@app.post("/api/tax/calculate")
def tax_calculate(data: dict, user = Depends(get_current_user)):
    return {"result": calc_tax(float(data.get('income', 0)), float(data.get('deductions', 0)), data.get('age', 'general'))}

@app.get("/api/tax/slabs")
def tax_slabs():
    return {"slabs": [
        {"range": "0 - 2,50,000", "rate": "NIL"},
        {"range": "2,50,001 - 5,00,000", "rate": "5%"},
        {"range": "5,00,001 - 10,00,000", "rate": "20%"},
        {"range": "Above 10,00,000", "rate": "30%"}
    ]}

@app.get("/api/tax/suggestions")
def tax_suggestions():
    return {"suggestions": [
        "Maximize 80C deductions (PPF, ELSS, Life Insurance)",
        "Invest in NPS for 80CCD(1B) extra deduction",
        "Health Insurance premium under 80D"
    ]}

@app.post("/api/chatbot/query")
def chatbot(data: dict):
    message = data.get("message", "")
    if not message:
        raise HTTPException(status_code=400, detail="Message required")
    if not GROQ_API_KEY:
        return {"response": "Chatbot not configured. Set GROQ_API_KEY."}
    try:
        resp = requests.post('https://api.groq.com/openai/v1/chat/completions',
            headers={'Authorization': f'Bearer {GROQ_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': GROQ_MODEL, 'messages': [
                {"role": "system", "content": "You are an Indian tax assistant."},
                {"role": "user", "content": message}
            ], 'temperature': 0.7}, timeout=30)
        if resp.status_code == 200:
            return {"response": resp.json()['choices'][0]['message']['content']}
        return {"response": "Error from API", "error": resp.text}
    except Exception as e:
        return {"response": "Chatbot unavailable", "error": str(e)}

@app.get("/api/chatbot/topics")
def chatbot_topics():
    return {"topics": ["Income Tax Basics", "ITR Filing", "Section 80C", "Section 80D"]}

@app.get("/api/chatbot/quick-actions")
def chatbot_actions():
    return {"actions": [
        {"action": "Calculate Tax", "icon": "calculator"},
        {"action": "File ITR", "icon": "document"}
    ]}

# Admin Panel (Static files)
@app.get("/admin")
@app.get("/admin/{filename}")
def admin_panel(filename: str = "index.html"):
    return FileResponse(f"public/admin/{filename}")

@app.get("/")
def root():
    return FileResponse("public/index.html")

# Create admin user on startup
admin_user = {
    "id": next_user_id,
    "email": "admin@taxpilot.com",
    "name": "Admin",
    "password_hash": pwd_context.hash("admin123"),
    "pan": None,
    "phone": None,
    "role": "admin"
}
users_db[next_user_id] = admin_user
next_user_id += 1
