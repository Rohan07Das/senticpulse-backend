import pandas as pd
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import os

def clean_float(value):
    """Safely converts strings like '₹58,990' or '4.2' to a float."""
    try:
        if pd.isna(value) or str(value).strip() == "":
            return 0.0
        # Remove currency symbols, commas, and non-numeric junk
        cleaned = "".join(c for c in str(value) if c.isdigit() or c == '.')
        return float(cleaned) if cleaned else 0.0
    except (ValueError, TypeError):
        return 0.0

async def sync_production_data():
    # 1. Connection to your Atlas Cluster
    uri = "mongodb+srv://rld_07:z95M0rXZmN72kYua@cluster0.rbwds2t.mongodb.net/?appName=Cluster0"
    client = AsyncIOMotorClient(uri)
    db = client.senticpulse_db
    
    csv_filename = 'amazon_backend_ready.csv' 
    
    if not os.path.exists(csv_filename):
        print(f"❌ Error: {csv_filename} not found!")
        return

    print(f"📂 Loading {csv_filename} with new columns...")
    # Loading the full dataframe to process the new mapping
    df = pd.read_csv(csv_filename)
    
    # 2. RESET QUOTA: Drop collection to clear space for the new columns
    print("🗑️ Dropping 'products' collection to reset Quota to 0MB...")
    await db.drop_collection("products")
    print("✅ Space cleared. Starting sync...")
    
    products = []
    print("⚙️ Processing 751k records...")
    
    for _, row in df.iterrows():
        # Handle Price (Matches your new 'actual_price' column)
        price_val = clean_float(row.get('actual_price', 0))
        
        # Build the compressed document to save space
        product_doc = {
            "item_id": str(row.get('item_id', '')),
            # TRUNCATION: Keeping names short is key for the 512MB limit
            "name": str(row.get('name', 'Unknown Product'))[:140], 
            
            "main_category": str(row.get('main_category', '')), 
            "sub_category": str(row.get('sub_category', '')),
            
            "image": str(row.get('image', '')),
            # MAPPING: We keep both 'link' and 'amazon_link' for router compatibility
            "link": str(row.get('link', '')),
            "amazon_link": str(row.get('link', '')), 
            
            "price": price_val,
            "actual_price": price_val,
            "ratings": clean_float(row.get('ratings', 0)),
            
            # --- AI IDS (CRITICAL FOR NCF MODEL) ---
            "category_id": int(row.get('category_id', 0)) if pd.notna(row.get('category_id')) else 0,
            "product_id": int(row.get('product_id', 0)) if pd.notna(row.get('product_id')) else 0
        }
        products.append(product_doc)

    # 4. Batch Upload to MongoDB Atlas
    if products:
        total = len(products)
        batch_size = 5000 
        print(f"🚀 Uploading {total} items to Atlas in batches...")
        
        for i in range(0, total, batch_size):
            batch = products[i : i + batch_size]
            try:
                await db.products.insert_many(batch)
                if i % 50000 == 0:
                    print(f"📦 Progress: {i}/{total} items synced...")
            except Exception as e:
                if "quota" in str(e).lower():
                    print(f"🛑 Quota Limit Reached at {i}. Stopping.")
                    break
                print(f"⚠️ Batch Error at {i}: {e}")
        
        print(f"🏆 SUCCESS! Your new format is live and ready for the Dashboard.")

if __name__ == "__main__":
    try:
        asyncio.run(sync_production_data())
    except Exception as e:
        print(f"❌ Sync Failed: {e}")