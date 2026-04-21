from fastapi import APIRouter, HTTPException, Query
import tensorflow as tf
import numpy as np
from motor.motor_asyncio import AsyncIOMotorClient
import os
import re
from datetime import datetime
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv()
router = APIRouter()

# --- DATABASE CONNECTION ---
MONGODB_URL = os.getenv("MONGODB_URL", "mongodb+srv://rld_07:z95M0rXZmN72kYua@cluster0.rbwds2t.mongodb.net/?appName=Cluster0")
client = AsyncIOMotorClient(MONGODB_URL)
db = client.senticpulse_db

# --- NCF MODEL LOADING ---
MODEL_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'senticpulse_ncf_model.keras')
model = None

try:
    if os.path.exists(MODEL_PATH):
        model = tf.keras.models.load_model(MODEL_PATH, compile=False)
        print(f"✅ SenticPulse Neural Core Active")
except Exception as e:
    print(f"❌ AI Load Error: {e}")

def sanitize_price(val):
    """Robust price cleaner: Removes ₹, commas, and handles various formats"""
    try:
        if val is None or val == "" or val == 0:
            return None
        if isinstance(val, str):
            # This regex keeps only digits and the decimal point
            cleaned = re.sub(r'[^\d.]', '', val)
            return float(cleaned) if cleaned else None
        return float(val)
    except:
        return None

# --- 1. NEURAL AI SUGGESTIONS ---
@router.get("/ai-suggest")
async def get_ai_suggest(category: str = Query("appliances")):
    try:
        # Improved Pool: Look for keyword in both Category and Name
        mongo_filter = {
            "$or": [
                {"main_category": {"$regex": category, "$options": "i"}},
                {"name": {"$regex": category, "$options": "i"}}
            ]
        }
        cursor = db.products.find(mongo_filter).limit(100) 
        cat_products = await cursor.to_list(length=100)
        
        if not cat_products:
            return {"recommendations": [], "message": "No items found"}

        results_to_return = []
        if model is None:
            results_to_return = cat_products[:4]
        else:
            try:
                target_cat_id = int(cat_products[0].get('category_id', 0))
                product_ids = [int(p.get('product_id', 0)) for p in cat_products]
                X_cat = np.full(len(product_ids), target_cat_id, dtype='int32')
                X_prod = np.array(product_ids, dtype='int32')
                preds = model.predict([X_cat, X_prod], verbose=0).flatten()
                
                for i, p in enumerate(cat_products):
                    p['ai_rating'] = round(float(max(1.0, min(5.0, preds[i]))), 2)
                
                cat_products.sort(key=lambda x: x.get('ai_rating', 0), reverse=True)
                results_to_return = cat_products[:4]
            except:
                results_to_return = cat_products[:4]

        for r in results_to_return:
            r["_id"] = str(r["_id"])
            raw_val = r.get("price") or r.get("actual_price") or r.get("discounted_price")
            r["price"] = sanitize_price(raw_val)
            r["amazon_link"] = r.get("amazon_link") or r.get("link", "#")

        return {"recommendations": results_to_return}
            
    except Exception as e:
        return {"recommendations": [], "error": str(e)}

# --- 2. DYNAMIC MARKET SEARCH (UNIFIED SIDEBAR + MAIN SEARCH) ---
@router.get("/search")
async def search_market(
    query: str = None, 
    category: str = None, 
    max_price: float = None,
    page: int = Query(1, ge=1)
):
    try:
        limit = 20
        skip = (page - 1) * limit
        filter_conditions = []

        # UNIFIED SEARCH TERM: Treat Sidebar clicks and Searchbar text the same way
        search_term = None
        if query:
            search_term = query
        elif category and category != "All":
            search_term = category

        if search_term:
            regex_query = {"$regex": search_term, "$options": "i"}
            
            # GLOBAL SEARCH: Check every relevant field to ensure items aren't missed
            filter_conditions.append({
                "$or": [
                    {"name": regex_query},
                    {"main_category": regex_query},
                    {"sub_category": regex_query},
                    {"category": regex_query},
                    {"description": regex_query}
                ]
            })
            
        if max_price:
            filter_conditions.append({
                "$or": [
                    {"price": {"$lte": max_price}},
                    {"actual_price": {"$lte": max_price}},
                    {"discounted_price": {"$lte": max_price}}
                ]
            })

        # Final query assembly
        mongo_filter = {"$and": filter_conditions} if filter_conditions else {}

        total_count = await db.products.count_documents(mongo_filter)
        cursor = db.products.find(mongo_filter).skip(skip).limit(limit)
        results = await cursor.to_list(length=limit)
        
        for r in results: 
            r["_id"] = str(r["_id"])
            # Flexible price detection logic
            raw_val = r.get("price") or r.get("actual_price") or r.get("discounted_price")
            r["price"] = sanitize_price(raw_val)
            r["amazon_link"] = r.get("amazon_link") or r.get("link", "#")
            
        return {
            "results": results,
            "total_records": total_count,
            "total_pages": (total_count // limit) + (1 if total_count % limit > 0 else 0)
        }
    except Exception as e:
        print(f"🚨 Neural Search Error: {e}")
        return {"results": [], "error": str(e)}

# --- 3. PRODUCT DETAIL (For dynamic preview page) ---
@router.get("/product/{product_id}")
async def get_product_details(product_id: str):
    try:
        product = await db.products.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404, detail="Item missing from Neural Core")
        
        product["_id"] = str(product["_id"])
        raw_val = product.get("price") or product.get("actual_price") or product.get("discounted_price")
        product["price"] = sanitize_price(raw_val)
        return product
    except:
        raise HTTPException(status_code=400, detail="Invalid Neural ID format")

# --- 4. PURCHASE LOGIC ---
@router.post("/buy/{product_id}")
async def process_purchase(product_id: str):
    try:
        product = await db.products.find_one({"_id": ObjectId(product_id)})
        if not product:
            raise HTTPException(status_code=404)

        order = {
            "product_id": product_id,
            "product_name": product.get("name"),
            "status": "Confirmed",
            "timestamp": datetime.utcnow()
        }
        await db.orders.insert_one(order)
        return {"status": "success"}
    except Exception:
        raise HTTPException(status_code=500)

# --- 5. USER PROFILE SYNC ---
@router.get("/user-profile/{email}")
async def get_user_profile(email: str):
    user = await db.users.find_one({"email": email})
    if not user:
        return {"email": email, "tier": "GUEST"}
    return {"email": user["email"], "tier": "ENTERPRISE"}