from dotenv import load_dotenv
import os, json

load_dotenv(".env")
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

schema = types.Schema(
    type=types.Type.OBJECT,
    properties={
        "classification": types.Schema(type=types.Type.STRING, enum=["sql", "rag", "sql+rag", "none"]),
        "question": types.Schema(type=types.Type.STRING),
    },
    required=["classification", "question"],
)

for model in ("gemini-3-flash-preview", "gemini-3.8-flash"):
    try:
        r = client.models.generate_content(
            model=model,
            contents="¿Cuántos libros tiene la biblioteca?",
            config=types.GenerateContentConfig(
                temperature=0,
                response_mime_type="application/json",
                response_schema=schema,
            ),
        )
        print(model, "->", json.dumps(json.loads(r.text), ensure_ascii=False))
    except Exception as e:
        print(model, "->", type(e).__name__, str(e)[:160])
