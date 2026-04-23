from fastapi import APIRouter
from pydantic import BaseModel
from sentiment_logic import analyze_message # This links to Step 2

router = APIRouter()

# This defines what the "Input" should look like
class ChatInput(BaseModel):
    message: str

# This is the "Endpoint" your website will talk to
@router.post("/analyze")
async def get_sentiment(data: ChatInput):
    result = analyze_message(data.message)
    return result