from fastapi import APIRouter, HTTPException, Request, BackgroundTasks, Query
from pydantic import BaseModel, EmailStr
from email_validator import validate_email, EmailNotValidError
import smtplib
from email.message import EmailMessage
from typing import List, Any, Optional
import os
from datetime import datetime

router = APIRouter()

# --- MODELS ---

class AuthData(BaseModel):
    name: Optional[str] = None
    email: EmailStr
    password: str
    role: str = "user"  # Captured from frontend toggle

class OrderItem(BaseModel):
    name: str
    price: Any
    image: str

class OrderData(BaseModel):
    email: EmailStr
    name: str
    items: List[OrderItem]
    total: Any

# --- EMAIL UTILITIES ---

def send_welcome_email(user_email: str, user_name: str, sender: str, password: str):
    msg = EmailMessage()
    msg["Subject"] = "Identity Established | SenticPulse AI"
    msg["From"] = f"SenticPulse AI <{sender}>"
    msg["To"] = user_email
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; background-color: #0a0a0a; border-radius: 20px; overflow: hidden; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .banner-container {{ width: 100%; line-height: 0; }}
            .banner-img {{ width: 100%; height: auto; display: block; border-bottom: 3px solid #b3ffe2; }}
            .content {{ padding: 40px 30px; text-align: center; background-color: #0a0a0a; }}
            h1 {{ color: #ffffff; font-size: 22px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; }}
            p {{ color: #94a3b8; line-height: 1.8; font-size: 15px; margin: 10px 0; }}
            .highlight {{ color: #b3ffe2; font-weight: bold; }}
            .btn-wrapper {{ margin-top: 30px; }}
            .btn {{ display: inline-block; padding: 16px 35px; background-color: #b3ffe2; color: #000000 !important; text-decoration: none; border-radius: 12px; font-weight: 900; font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px; }}
            .footer {{ padding: 25px; text-align: center; color: #475569; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; background-color: #050505; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="banner-container">
                <img src="https://media.licdn.com/dms/image/v2/D5612AQHi4VTMRTMfPQ/article-cover_image-shrink_720_1280/article-cover_image-shrink_720_1280/0/1727292037363?e=2147483647&v=beta&t=SXl_xCTeCdkCE1fFpD1JRU1xF2zyMC3ea02f5fVmMbI" alt="SenticPulse AI Banner" class="banner-img">
            </div>
            <div class="content">
                <h1>Identity Established</h1>
                <p>Hi <span class="highlight">{user_name}</span>,</p>
                <p>Welcome to SenticPulse AI! 🚀</p>
                <p>Your neural profile has been synced with the SenticPulse Core. Access your dashboard below.</p>
                <div class="btn-wrapper">
                    <a href="https://senticpulse-frontend.vercel.app/dashboard" class="btn">Access Dashboard</a>
                </div>
            </div>
            <div class="footer">SenticPulse Neural Core v2.1.0 // Rourkela, Odisha</div>
        </div>
    </body>
    </html>
    """
    msg.set_content(f"Welcome {user_name}! Login here: https://senticpulse-frontend.vercel.app/register")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
    except Exception as e: print(f"Welcome Email Error: {e}")

def send_order_receipt(order: OrderData, sender: str, password: str):
    msg = EmailMessage()
    msg["Subject"] = f"Neural Receipt: Order Confirmed #{os.urandom(2).hex().upper()}"
    msg["From"] = f"SenticPulse AI <{sender}>"
    msg["To"] = order.email

    item_rows = ""
    for item in order.items:
        item_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b;"><img src="{item.image}" width="50" style="border-radius: 8px;"></td>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b; color: #ffffff; font-size: 13px;">{item.name}</td>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b; color: #b3ffe2; font-weight: bold; text-align: right;">₹{item.price}</td>
        </tr>
        """

    html_content = f"""
    <html>
    <body style="background-color: #000; font-family: sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #0a0a0a; border: 1px solid #b3ffe230; border-radius: 24px; overflow: hidden;">
            <div style="background-color: #b3ffe2; padding: 20px; text-align: center; color: #000;">
                <h2 style="margin: 0; text-transform: uppercase; letter-spacing: 2px;">Order Established</h2>
            </div>
            <div style="padding: 30px;">
                <p style="color: #94a3b8;">Hi {order.name}, your order has been confirmed.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">{item_rows}</table>
                <div style="margin-top: 30px; text-align: right;">
                    <p style="color: #94a3b8; font-size: 12px;">TOTAL INVESTMENT</p>
                    <h2 style="color: #ffffff; margin: 0; font-size: 28px;">₹{order.total}</h2>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    msg.set_content(f"Order confirmed! Total: ₹{order.total}")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
    except Exception as e: print(f"Receipt Error: {e}")

# --- AUTH ENDPOINTS ---

@router.post("/register")
async def register(request: Request, user: AuthData, background_tasks: BackgroundTasks):
    users_collection = request.app.db.users
    if not user.name: raise HTTPException(status_code=400, detail="Name required")
    
    try:
        valid = validate_email(user.email, check_deliverability=False)
        normalized_email = valid.email
    except EmailNotValidError as e: raise HTTPException(status_code=400, detail=str(e))
    
    if await users_collection.find_one({"email": normalized_email}):
        raise HTTPException(status_code=400, detail="Identity already exists")

    user_dict = {
        "name": user.name,
        "email": normalized_email,
        "password": user.password,
        "role": user.role,
        "tier": "ENTERPRISE",
        "created_at": datetime.utcnow()
    }
    await users_collection.insert_one(user_dict)
    
    sender, pwd = request.app.state.EMAIL_SENDER, request.app.state.EMAIL_PASSWORD
    if sender and pwd: background_tasks.add_task(send_welcome_email, normalized_email, user.name, sender, pwd)
    
    return {"status": "success", "user": {"name": user.name, "email": normalized_email, "role": user.role}}

@router.post("/login")
async def login(request: Request, user: AuthData):
    db_user = await request.app.db.users.find_one({"email": user.email, "password": user.password})
    if not db_user: raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if db_user.get("role") != user.role:
        raise HTTPException(status_code=403, detail=f"Access Denied: Lacks {user.role.upper()} clearance.")
    
    return {
        "status": "success",
        "redirect_to": "/admin-stats" if db_user["role"] == "admin" else "/dashboard",
        "user": {"email": db_user["email"], "name": db_user.get("name", "User"), "role": db_user["role"]}
    }

@router.get("/user-profile/{email}")
async def get_user_profile(request: Request, email: str):
    db_user = await request.app.db.users.find_one({"email": email})
    if not db_user: raise HTTPException(status_code=404, detail="Identity not found")
    return {"email": db_user["email"], "name": db_user.get("name", "User"), "tier": db_user.get("tier", "ENTERPRISE"), "role": db_user.get("role", "user")}

# --- CART & ORDER ---

@router.post("/sync-cart")
async def sync_cart(request: Request, data: dict):
    email = data.get("email")
    if not email: raise HTTPException(status_code=400, detail="Email missing")
    await request.app.db.carts.update_one({"email": email}, {"$set": {"items": data.get("items"), "updated_at": datetime.utcnow()}}, upsert=True)
    return {"status": "success"}

@router.post("/save-order")
async def save_order(request: Request, order: OrderData):
    await request.app.db.orders.insert_one({**order.dict(), "status": "established", "created_at": datetime.utcnow()})
    return {"status": "success"}

@router.post("/send-receipt")
async def handle_receipt(request: Request, order: OrderData, background_tasks: BackgroundTasks):
    sender, pwd = request.app.state.EMAIL_SENDER, request.app.state.EMAIL_PASSWORD
    background_tasks.add_task(send_order_receipt, order, sender, pwd)
    return {"status": "success"}