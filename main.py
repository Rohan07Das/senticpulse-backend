from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from routers import auth, recommendations
from motor.motor_asyncio import AsyncIOMotorClient
import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 1. Load Environment Variables
load_dotenv()

# --- DATABASE CONNECTION LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Connect to MongoDB (Using the key from your .env)
    uri = os.getenv("MONGODB_URL") 
    app.mongodb_client = AsyncIOMotorClient(uri)
    app.db = app.mongodb_client.senticpulse_db
    
    # 2. Load Email Config
    app.state.EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    app.state.EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    
    # Debugging: This will print to your terminal when you start the server
    # to confirm the values are loaded (delete these prints later for security!)
    print(f"📧 Mailer Configured: {app.state.EMAIL_SENDER}")
    
    print("🚀 SenticPulse Neural Core: MongoDB Connected")
    yield
    # Shutdown: Close Connection
    app.mongodb_client.close()
    print("💤 SenticPulse Neural Core: MongoDB Connection Closed")

app = FastAPI(
    title="SenticPulse AI Backend",
    description="Neural Core API Gateway for Search and NCF Recommendations",
    version="2.1.0",
    lifespan=lifespan 
)

# --- Update this list in your main.py ---
origins = [
    "http://localhost:3000",
    "https://senticpulse-frontend.vercel.app", # Add your REAL Vercel URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # This tells the backend to trust your new site
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 3. ATTACH SPECIALIZED ROUTERS
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(recommendations.router, prefix="/api/recs", tags=["Recommendations"])

# 4. GLOBAL NAVBAR SEARCH
@app.get("/api/products/search", tags=["Global Search"])
async def search_products(request: Request, q: str = Query(..., min_length=1)):
    try:
        query = {"name": {"$regex": q, "$options": "i"}}
        cursor = request.app.db.products.find(query).limit(24)
        products = await cursor.to_list(length=24)
        
        for p in products:
            p["_id"] = str(p["_id"])
            raw_price = p.get("price") or p.get("actual_price") or 0
            p["price"] = float(raw_price)
            p["amazon_link"] = p.get("amazon_link") or p.get("link", "#")
            
        return products
    except Exception as e:
        print(f"🚨 Global Search Error: {e}")
        return {"error": str(e)}

# 5. SYSTEM HEALTH & UTILITIES
@app.get("/api/health", tags=["System"])
async def check_health(request: Request):
    try:
        await request.app.db.command("ping")
        return {
            "status": "Online",
            "db": "Connected",
            "neural_engine": "NCF-Model-Ready",
            "message": "SenticPulse Core is fully operational."
        }
    except Exception:
        return {"status": "Degraded", "db": "Disconnected"}

class UserMessage(BaseModel):
    text: str

@app.post("/api/analyze", tags=["Sentiment"])
def analyze_text(message: UserMessage):
    return {
        "text": message.text,
        "ai_status": "Sentiment Weights Active"
    }

if __name__ == "__main__":
    import uvicorn
    import os
    # Pull the port from Render's environment, or default to 8000 for local
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)