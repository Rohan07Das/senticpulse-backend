import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

# Load the MONGODB_URL from your .env file
load_dotenv()

MONGO_URL = os.getenv("MONGODB_URL")

# Connect to MongoDB
client = AsyncIOMotorClient(MONGO_URL)

# Access the database 'senticpulse_db'
db = client.senticpulse_db

# Collections (Think of these as tables)
users_collection = db.get_collection("users")