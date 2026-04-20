from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel, EmailStr
from email_validator import validate_email, EmailNotValidError
import smtplib
from email.message import EmailMessage
from typing import List, Any
import os
from datetime import datetime

router = APIRouter()

# --- ORDER MODELS FOR RECEIPT & DATABASE ---
class OrderItem(BaseModel):
    name: str
    price: Any
    image: str

class OrderData(BaseModel):
    email: EmailStr
    name: str
    items: List[OrderItem]
    total: Any

# --- ORDER RECEIPT EMAIL FUNCTION ---
def send_order_receipt(order: OrderData, sender: str, password: str):
    msg = EmailMessage()
    msg["Subject"] = f"Neural Receipt: Order Confirmed #{os.urandom(2).hex().upper()}"
    msg["From"] = f"SenticPulse AI <{sender}>"
    msg["To"] = order.email

    item_rows = ""
    for item in order.items:
        display_price = str(item.price) 
        item_rows += f"""
        <tr>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b;">
                <img src="{item.image}" width="50" style="border-radius: 8px;">
            </td>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b; color: #ffffff; font-size: 13px;">
                {item.name}
            </td>
            <td style="padding: 15px; border-bottom: 1px solid #1e293b; color: #b3ffe2; font-weight: bold; text-align: right;">
                ₹{display_price}
            </td>
        </tr>
        """

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <body style="background-color: #000; font-family: sans-serif; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #0a0a0a; border: 1px solid #b3ffe230; border-radius: 24px; overflow: hidden;">
            <div style="background-color: #b3ffe2; padding: 20px; text-align: center; color: #000;">
                <h2 style="margin: 0; text-transform: uppercase; letter-spacing: 2px;">Order Established</h2>
            </div>
            <div style="padding: 30px;">
                <p style="color: #94a3b8;">Hi {order.name}, your neural hardware is being prepared for shipment.</p>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                    {item_rows}
                </table>
                <div style="margin-top: 30px; text-align: right;">
                    <p style="color: #94a3b8; font-size: 12px; margin-bottom: 5px;">TOTAL INVESTMENT</p>
                    <h2 style="color: #ffffff; margin: 0; font-size: 28px;">₹{order.total:,.2f}</h2>
                </div>
            </div>
            <div style="padding: 20px; text-align: center; background-color: #050505; color: #475569; font-size: 10px; letter-spacing: 2px;">
                SENTICPULSE AI // SECURE TRANSACTION
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
            print(f"✅ Receipt dispatched to: {order.email}")
    except Exception as e:
        print(f"🚨 Receipt Error: {e}")

# --- SYNC CART TO MONGODB ---
@router.post("/sync-cart")
async def sync_cart(request: Request, data: dict):
    email = data.get("email")
    items = data.get("items")
    if not email:
        raise HTTPException(status_code=400, detail="Email required for cart sync")
    
    await request.app.db.carts.update_one(
        {"email": email},
        {"$set": {"items": items, "updated_at": datetime.utcnow()}},
        upsert=True
    )
    return {"status": "success"}

# --- SAVE ORDER TO MONGODB ---
@router.post("/save-order")
async def save_order(request: Request, order: OrderData):
    order_doc = {
        "email": order.email,
        "name": order.name,
        "items": [item.dict() for item in order.items],
        "total": order.total,
        "status": "established",
        "created_at": datetime.utcnow()
    }
    await request.app.db.orders.insert_one(order_doc)
    return {"status": "success"}

# --- RECEIPT ENDPOINT ---
@router.post("/send-receipt")
async def handle_receipt(request: Request, order: OrderData, background_tasks: BackgroundTasks):
    sender = request.app.state.EMAIL_SENDER
    pwd = request.app.state.EMAIL_PASSWORD
    background_tasks.add_task(send_order_receipt, order, sender, pwd)
    return {"status": "success", "message": "Neural receipt dispatched"}

# --- NEW: VERIFIED USER PROFILE ENDPOINT ---
# This ensures layout.tsx always gets the latest name from MongoDB
@router.get("/user-profile/{email}")
async def get_user_profile(request: Request, email: str):
    db_user = await request.app.db.users.find_one({"email": email})
    if not db_user:
        raise HTTPException(status_code=404, detail="Identity not found in Cloud Core")
    
    return {
        "email": db_user["email"],
        "name": db_user.get("name", "User"),
        "tier": db_user.get("tier", "ENTERPRISE")
    }

# --- WELCOME EMAIL ---
def send_welcome_email(user_email: str, user_name: str, sender: str, password: str):
    msg = EmailMessage()
    msg["Subject"] = "Welcome to the Neural Network | SenticPulse AI"
    msg["From"] = f"SenticPulse AI <{sender}>"
    msg["To"] = user_email
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 0; }}
            .container {{ max-width: 600px; margin: 20px auto; background-color: #0a0a0a; border-radius: 20px; overflow: hidden; shadow: 0 10px 30px rgba(0,0,0,0.5); }}
            .banner-container {{ width: 100%; line-height: 0; }}
            .banner-img {{ width: 100%; height: auto; display: block; border-bottom: 3px solid #b3ffe2; }}
            .content {{ padding: 40px 30px; text-align: center; background-color: #0a0a0a; }}
            h1 {{ color: #ffffff; font-size: 22px; font-weight: 800; text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; }}
            p {{ color: #94a3b8; line-height: 1.8; font-size: 15px; margin: 10px 0; }}
            .highlight {{ color: #b3ffe2; font-weight: bold; }}
            .btn-wrapper {{ margin-top: 30px; }}
            .btn {{ display: inline-block; padding: 16px 35px; background-color: #b3ffe2; color: #000000 !important; text-decoration: none; border-radius: 12px; font-weight: 900; font-size: 13px; text-transform: uppercase; letter-spacing: 1.5px; transition: transform 0.2s; }}
            .footer {{ padding: 25px; text-align: center; color: #475569; font-size: 10px; text-transform: uppercase; letter-spacing: 2px; background-color: #050505; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="banner-container">
                <img src="https://media.licdn.com/dms/image/v2/D5612AQHi4VTMRTMfPQ/article-cover_image-shrink_720_1280/article-cover_image-shrink_720_1280/0/1727292037363?e=2147483647&v=beta&t=SXl_xCTeCdkCE1fFpD1JRU1xF2zyMC3ea02f5fVmMbI" 
                     alt="SenticPulse AI Banner" 
                     class="banner-img">
            </div>
            <div class="content">
                <h1>Identity Established</h1>
                <p>Hi <span class="highlight">{user_name}</span>,</p>
                <p>Welcome to SenticPulse AI! 🚀</p>
                <p>Your account has been successfully created. We're excited to help you harness SME intelligence with our Neural Core engine.</p>
                <div class="btn-wrapper">
                    <a href="https://senticpulse-frontend.vercel.app/dashboard" class="btn">Access Dashboard</a>
                </div>
                <p style="margin-top: 30px; font-size: 12px; opacity: 0.7;">
                    Login URL: <a href="https://senticpulse-frontend.vercel.app/register" style="color: #b3ffe2;">https://senticpulse-frontend.vercel.app/register</a>
                </p>
            </div>
            <div class="footer">
                SenticPulse Neural Core v2.1.0 // Rourkela, Odisha
            </div>
        </div>
    </body>
    </html>
    """
    msg.set_content(f"Hi {user_name}, Welcome to SenticPulse AI! Login here: https://senticpulse-frontend.vercel.app/register")
    msg.add_alternative(html_content, subtype='html')

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as server:
            server.starttls()
            server.login(sender, password)
            server.send_message(msg)
            print(f"✅ Professional HTML email sent to: {user_email}")
    except Exception as e:
        print(f"🚨 SMTP Error: {e}")

class AuthData(BaseModel):
    name: str = None
    email: EmailStr
    password: str

@router.post("/register")
async def register(request: Request, user: AuthData, background_tasks: BackgroundTasks):
    users_collection = request.app.db.users
    if not user.name:
        raise HTTPException(status_code=400, detail="Name is required for registration")
    try:
        valid = validate_email(user.email, check_deliverability=True)
        normalized_email = valid.email
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail=f"Neural Error: {str(e)}")
    
    if await users_collection.find_one({"email": normalized_email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_dict = user.dict()
    user_dict["email"] = normalized_email
    user_dict["tier"] = "ENTERPRISE" # Default tier
    
    await users_collection.insert_one(user_dict)
    
    sender = request.app.state.EMAIL_SENDER
    pwd = request.app.state.EMAIL_PASSWORD
    background_tasks.add_task(send_welcome_email, normalized_email, user.name, sender, pwd)
    
    # Return ONLY the verified data from the database process
    return {
        "status": "success",
        "message": "Registration successful!",
        "user": {"name": user.name, "email": normalized_email}
    }

@router.post("/login")
async def login(request: Request, user: AuthData):
    users_collection = request.app.db.users
    
    # Strictly pull the matching document from MongoDB
    db_user = await users_collection.find_one({"email": user.email, "password": user.password})
    
    if not db_user:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Return the verified name and email from the MongoDB document
    return {
        "status": "success",
        "redirect_to": "/dashboard",
        "user": {
            "email": db_user["email"],
            "name": db_user.get("name", "User") 
        }
    }