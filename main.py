import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import requests
from database import db, create_document

app = FastAPI(title="Quran API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SyncResponse(BaseModel):
    surahs_imported: int
    ayahs_imported: int
    already_present: bool


@app.get("/")
def read_root():
    return {"message": "Quran API running"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# ---------------------- Quran Data Endpoints ----------------------

ALQURAN_BASE = "https://api.alquran.cloud/v1"
AR_EDITION = "quran-uthmani"  # Arabic text
EN_EDITION = "en.asad"        # English translation
AUDIO_EDITION = "ar.alafasy"   # Mishary Alafasy audio


def surah_collection():
    return db["quransurah"]


def ayah_collection():
    return db["quranayah"]


@app.post("/api/sync", response_model=SyncResponse)
def sync_quran(force: bool = False):
    """
    Sync Quran metadata and ayahs from AlQuran Cloud API into MongoDB.
    By default, only runs if data is not present. Use force=true to re-import.
    """
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")

    # Check existing
    existing_surahs = surah_collection().count_documents({})
    existing_ayahs = ayah_collection().count_documents({})
    if existing_surahs > 0 and existing_ayahs > 0 and not force:
        return SyncResponse(surahs_imported=0, ayahs_imported=0, already_present=True)

    # Optionally clear when force
    if force:
        surah_collection().delete_many({})
        ayah_collection().delete_many({})

    # Fetch surah list
    surah_resp = requests.get(f"{ALQURAN_BASE}/surah")
    if surah_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch surah list")
    surahs = surah_resp.json().get("data", [])

    # Insert surah metadata
    to_insert_surahs = []
    for s in surahs:
        to_insert_surahs.append({
            "number": s.get("number"),
            "name": s.get("name"),
            "englishName": s.get("englishName"),
            "englishNameTranslation": s.get("englishNameTranslation"),
            "revelationType": s.get("revelationType"),
            "numberOfAyahs": s.get("numberOfAyahs"),
        })
    if to_insert_surahs:
        surah_collection().insert_many(to_insert_surahs)

    # Fetch and insert ayahs per surah (Arabic + English + audio URL)
    total_ayahs = 0
    for s in surahs:
        number = s.get("number")
        # Arabic text
        ar_resp = requests.get(f"{ALQURAN_BASE}/surah/{number}/{AR_EDITION}")
        en_resp = requests.get(f"{ALQURAN_BASE}/surah/{number}/{EN_EDITION}")
        audio_resp = requests.get(f"{ALQURAN_BASE}/surah/{number}/{AUDIO_EDITION}")
        if not (ar_resp.status_code == 200 and en_resp.status_code == 200 and audio_resp.status_code == 200):
            continue
        ar_ayahs = ar_resp.json().get("data", {}).get("ayahs", [])
        en_ayahs = en_resp.json().get("data", {}).get("ayahs", [])
        audio_ayahs = audio_resp.json().get("data", {}).get("ayahs", [])

        docs = []
        for idx in range(len(ar_ayahs)):
            ar = ar_ayahs[idx]
            en = en_ayahs[idx] if idx < len(en_ayahs) else {}
            au = audio_ayahs[idx] if idx < len(audio_ayahs) else {}
            docs.append({
                "surah_number": number,
                "ayah_number": ar.get("numberInSurah"),
                "text_ar": ar.get("text"),
                "text_en": en.get("text"),
                "audio_url": au.get("audio"),
            })
        if docs:
            ayah_collection().insert_many(docs)
            total_ayahs += len(docs)

    return SyncResponse(surahs_imported=len(to_insert_surahs), ayahs_imported=total_ayahs, already_present=False)


@app.get("/api/surah")
def list_surahs():
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    surahs = list(surah_collection().find({}, {"_id": 0}).sort("number", 1))
    return {"data": surahs}


@app.get("/api/surah/{number}")
def get_surah(number: int):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    s = surah_collection().find_one({"number": number}, {"_id": 0})
    if not s:
        raise HTTPException(status_code=404, detail="Surah not found")
    return s


@app.get("/api/surah/{number}/ayahs")
def get_surah_ayahs(number: int, q: Optional[str] = None, limit: int = 0):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    query = {"surah_number": number}
    if q:
        # Simple text search in Arabic or English fields
        query = {"surah_number": number, "$or": [
            {"text_ar": {"$regex": q, "$options": "i"}},
            {"text_en": {"$regex": q, "$options": "i"}},
        ]}
    cursor = ayah_collection().find(query, {"_id": 0}).sort("ayah_number", 1)
    if limit and limit > 0:
        cursor = cursor.limit(int(limit))
    ayahs = list(cursor)
    return {"data": ayahs}


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
