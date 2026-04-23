from fastapi import FastAPI, Query, Request, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from routers import auth, recommendations
from motor.motor_asyncio import AsyncIOMotorClient
import os
import random 
import datetime 
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# --- Import Transformers for Sentiment ---
from transformers import pipeline

# 1. Load Environment Variables
load_dotenv()

# --- 2. DEFINE MODELS FIRST ---
class UserMessage(BaseModel):
    text: str
    email: str = "guest"  # Accepts email from frontend

# --- DATABASE CONNECTION & AI MODEL LIFESPAN ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # A. Connect to MongoDB
    uri = os.getenv("MONGODB_URL") 
    app.mongodb_client = AsyncIOMotorClient(uri)
    app.db = app.mongodb_client.senticpulse_db
    
    # B. Load Email Config
    app.state.EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    app.state.EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    
    # C. Load Sentiment AI Model (RoBERTa/BERT)
    # NOTE: This can take 1-2 minutes on Render's first boot.
    print("⌛ Loading SenticPulse AI Sentiment Weights...")
    try:
        app.state.sentiment_model = pipeline(
            "sentiment-analysis", 
            model="cardiffnlp/twitter-roberta-base-sentiment"
        )
        print("✅ Sentiment Engine Online.")
    except Exception as e:
        print(f"❌ AI Load Failed: {e}")
        # Fallback to avoid complete crash
        app.state.sentiment_model = None
    
    print(f"📧 Mailer Configured: {app.state.EMAIL_SENDER}")
    print("🚀 SenticPulse Neural Core: MongoDB Connected")
    yield
    # Shutdown
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

# --- UPDATED: ADMIN GLOBAL STATS ENDPOINT WITH REAL ORDER FETCH ---
@app.get("/api/admin/global-stats", tags=["Admin"])
async def get_admin_global_stats(request: Request, email: str = Query(...)):
    try:
        # ROLE FEATURE: Verify that the user exists and is an 'admin'
        user = await request.app.db.users.find_one({"email": email})
        
        if not user or user.get("role") != "admin":
            raise HTTPException(status_code=403, detail="Access Denied: Admin Neural clearance required.")

        # 1. Sentiment Totals (for Pie Chart)
        pos = await request.app.db.trends.count_documents({"sentiment": "Positive (+ve)"})
        neu = await request.app.db.trends.count_documents({"sentiment": "Neutral"})
        neg = await request.app.db.trends.count_documents({"sentiment": "Negative (-ve)"})

        # 2. Top Trending Categories (for Bar Chart)
        pipeline_agg = [
            {"$group": {"_id": "$keyword", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
            {"$limit": 5}
        ]
        category_data = await request.app.db.trends.aggregate(pipeline_agg).to_list(length=5)
        formatted_categories = [{"name": item["_id"], "total": item["count"]} for item in category_data]

        # 3. Feed (Sentiment Trends)
        cursor = request.app.db.trends.find().sort("timestamp", -1).limit(10)
        feed = await cursor.to_list(length=10)
        for item in feed: item["_id"] = str(item["_id"])

        # 4. NEW: Fetch Real Orders from MongoDB 'orders' collection
        orders_cursor = request.app.db.orders.find().sort("created_at", -1).limit(10)
        orders_list = await orders_cursor.to_list(length=10)
        real_orders = []
        for o in orders_list:
            real_orders.append({
                "email": o.get("email"),
                "name": o.get("name"),   
                "total": o.get("total"), 
                "status": o.get("status", "established")
            })

        return {
            "chartData": [
                {"name": "Positive", "value": pos, "color": "#10b981"},
                {"name": "Neutral", "value": neu, "color": "#64748b"},
                {"name": "Negative", "value": neg, "color": "#ef4444"}
            ],
            "categoryData": formatted_categories,
            "activityFeed": feed,
            "marketOrders": real_orders, 
            "totalAnalyzed": pos + neu + neg
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        return {"error": str(e)}

# --- LIVE CLUSTERS ENDPOINT ---
@app.get("/api/clusters", tags=["Analytics"])
async def get_live_clusters(request: Request):
    try:
        cursor = request.app.db.trends.find().sort("timestamp", -1).limit(10)
        recent_trends = await cursor.to_list(length=10)

        styles = {
            "Positive (+ve)": {"color": "text-emerald-600 dark:text-[#34A853]", "bg": "bg-emerald-50 dark:bg-[#34A853]/10"},
            "Neutral": {"color": "text-slate-500 dark:text-slate-400", "bg": "bg-slate-50 dark:bg-white/5"},
            "Negative (-ve)": {"color": "text-red-600 dark:text-red-500", "bg": "bg-red-50 dark:bg-red-500/10"}
        }

        final_trends = []
        seen = set()
        for t in recent_trends:
            if t['keyword'] not in seen and len(final_trends) < 3:
                clean_status = t['sentiment'].split()[0]
                final_trends.append({
                    "name": t['keyword'],
                    "status": clean_status,
                    **styles.get(t['sentiment'], styles["Neutral"])
                })
                seen.add(t['keyword'])

        if not final_trends:
            return [
                {"name": "Electronics_Pulse", "status": "Positive", **styles["Positive (+ve)"]},
                {"name": "Logistics_Chain", "status": "Neutral", **styles["Neutral"]},
                {"name": "Steel_Inventory", "status": "Negative", **styles["Negative (-ve)"]}
            ]
        return final_trends
    except Exception as e:
        return []

# --- ANALYZE AND SAVE TO DB (ACCOUNT WISE) ---
@app.post("/api/analyze", tags=["Sentiment"])
async def analyze_text(request: Request, message: UserMessage):
    if not request.app.state.sentiment_model:
        return {"error": "Sentiment engine is currently offline."}
        
    user_email = message.email
    mapping = {'LABEL_0': 'Negative (-ve)', 'LABEL_1': 'Neutral', 'LABEL_2': 'Positive (+ve)'}
    
    prediction = request.app.state.sentiment_model(message.text)[0]
    sentiment_label = mapping[prediction['label']]

    words = message.text.strip().split()
    keyword = "_".join(words[:2]) if len(words) >= 2 else words[0]
    
    try:
        await request.app.db.trends.insert_one({
            "email": user_email, 
            "full_text": message.text, 
            "keyword": keyword[:20],
            "sentiment": sentiment_label,
            "confidence": f"{round(prediction['score'] * 100, 2)}%",
            "timestamp": datetime.datetime.now(datetime.timezone.utc)
        })
    except Exception as e:
        print(f"⚠️ Save Failed: {e}")
    
    return {
        "text": message.text,
        "sentiment": sentiment_label, 
        "confidence": f"{round(prediction['score'] * 100, 2)}%"
    }

# --- GET CHAT HISTORY (ACCOUNT WISE) ---
@app.get("/api/chat/history", tags=["Sentiment"])
async def get_chat_history(request: Request, email: str = Query("guest")):
    try:
        cursor = request.app.db.trends.find({"email": email}).sort("timestamp", -1).limit(10)
        history = await cursor.to_list(length=10)
        
        formatted_history = []
        for item in reversed(history):
            formatted_history.append({"role": "user", "text": item.get("full_text")})
            formatted_history.append({
                "role": "agent", 
                "text": f"Neural Analysis: {item.get('sentiment')}",
                "confidence": item.get("confidence")
            })
        return formatted_history
    except Exception as e:
        return []

# --- CLEAR CHAT ENDPOINT ---
@app.delete("/api/chat/clear", tags=["Sentiment"])
async def clear_chat(request: Request):
    try:
        await request.app.db.trends.delete_many({}) 
        return {"message": "Chat history cleared successfully"}
    except Exception as e:
        return {"error": str(e)}

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

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)