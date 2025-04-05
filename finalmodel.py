from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import requests
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# ---- Initialize FastAPI ----
app = FastAPI()

# ---- Enable CORS (Fixes React Connection Issue) ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust if needed (e.g., allow only React frontend URL)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Load Embedding Model ----
print("🔄 Loading embedding model...")
embedder = SentenceTransformer("BAAI/bge-small-en-v1.5")
print("✅ Embedding model loaded successfully!")

# ---- Connect to Pinecone ----
PINECONE_API_KEY = ""  # 🔴 REPLACE with your Pinecone API key
INDEX_NAME = "biobert-med"

pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(INDEX_NAME)
print(f"✅ Connected to Pinecone index: {INDEX_NAME}")

# ---- Groq API Setup ----
GROQ_API_KEY = ""  # 🔴 REPLACE with your Groq API key
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

# ---- Define Request Model ----
class QueryRequest(BaseModel):
    query: str

# ---- API Endpoint for Generating Response ----
@app.post("/generate-response")
async def generate_response(request: QueryRequest):
    user_query = request.query
    print(f"\n🔍 Received Query: {user_query}")

    # Convert query to embedding
    query_embedding = embedder.encode(user_query).tolist()

    # 🔎 Search in Pinecone
    print("🔄 Searching Pinecone for relevant context...")
    search_results = index.query(vector=query_embedding, top_k=1, include_metadata=True)

    # 🛠️ Check if results exist
    retrieved_input = "No relevant context found."
    if search_results and search_results.get("matches"):
        retrieved_input = search_results["matches"][0]["metadata"].get("text", "No relevant context found.")

    print(f"✅ Retrieved Context: {retrieved_input}")

    # 📝 Construct messages for Groq API
    messages = [
        {"role": "system", "content": "You are a knowledgeable AI assistant."},
        {"role": "user", "content": user_query},
        {"role": "assistant", "content": retrieved_input}
    ]

    # ---- Send Request to Groq API ----
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "mixtral-8x7b-32768",  # ✅ Updated to Groq-supported model
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.7
    }

    print("🔄 Sending request to Groq API...")
    response = requests.post(GROQ_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        error_msg = response.json().get("error", {}).get("message", "Unknown error")
        print(f"❌ Groq API Error: {error_msg}")
        raise HTTPException(status_code=500, detail=f"Groq API Error: {error_msg}")

    groq_response = response.json()
    ai_response = groq_response["choices"][0]["message"]["content"]

    print(f"✅ AI Response: {ai_response}")

    return {"context": retrieved_input, "response": ai_response}

# ---- Run API Locally ----
if __name__ == "__main__":
    import nest_asyncio
    import uvicorn
    nest_asyncio.apply()
    print("🚀 Running FastAPI server on http://127.0.0.1:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
