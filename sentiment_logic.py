from transformers import pipeline

# This loads the "Brain" of your sentiment AI
# It's a pre-trained model that knows 58 million tweets
print("⌛ Loading SenticPulse AI Model...")
pulse_model = pipeline(
    "sentiment-analysis", 
    model="cardiffnlp/twitter-roberta-base-sentiment"
)

def analyze_message(text):
    # Mapping the AI's internal labels to what you need
    mapping = {'LABEL_0': 'Negative (-ve)', 'LABEL_1': 'Neutral', 'LABEL_2': 'Positive (+ve)'}
    
    # The AI looks at your text here
    prediction = pulse_model(text)[0]
    
    return {
        "sentiment": mapping[prediction['label']],
        "confidence": round(prediction['score'] * 100, 2)
    }