from transformers import pipeline as hf_pipeline

# ── Lazy pipeline — only loads on first classify call ─────────────────────────
_classifier = None

def get_classifier():
    global _classifier
    if _classifier is None:
        print("[emotion_service] Loading HuggingFace model...")
        _classifier = hf_pipeline(
            "text-classification",
            model="j-hartmann/emotion-english-distilroberta-base",
            top_k=1
        )
        print("[emotion_service] Model loaded ✅")
    return _classifier


EMO_MAP = {
    "joy":      "happy",
    "anger":    "angry",
    "sadness":  "sad",
    "fear":     "fearful",
    "surprise": "surprised",
    "neutral":  "neutral",
    "disgust":  "angry",
}

def get_intensity(score):
    if score >= 0.80: return "high"
    if score >= 0.55: return "medium"
    return "low"

def classify_emotion(text: str) -> dict:
    try:
        result = get_classifier()(text[:512])[0][0]
        label  = result["label"].lower()
        score  = result["score"]
        return {
            "emotion":    EMO_MAP.get(label, "neutral"),
            "intensity":  get_intensity(score),
            "confidence": round(score, 2),
        }
    except Exception as e:
        print(f"[emotion_service] Error: {e}")
        return {"emotion":"neutral","intensity":"low","confidence":0.5}