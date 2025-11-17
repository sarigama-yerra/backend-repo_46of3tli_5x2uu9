"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List

# Example schemas (replace with your own):

class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Quran app schemas

class QuranSurah(BaseModel):
    """
    Quran Surah metadata
    Collection name: "quransurah"
    """
    number: int = Field(..., description="Surah number (1-114)")
    name: str = Field(..., description="Arabic name")
    englishName: str = Field(..., description="English name")
    englishNameTranslation: Optional[str] = Field(None, description="English translation of the name")
    revelationType: Optional[str] = Field(None, description="Meccan or Medinan")
    numberOfAyahs: int = Field(..., description="Total ayahs in the surah")

class QuranAyah(BaseModel):
    """
    Quran Ayah content per surah
    Collection name: "quranayah"
    """
    surah_number: int = Field(..., description="Parent surah number")
    ayah_number: int = Field(..., description="Ayah number within the surah")
    text_ar: str = Field(..., description="Arabic text")
    text_en: Optional[str] = Field(None, description="English translation text")
    audio_url: Optional[str] = Field(None, description="Audio URL for recitation if available")

# Add your own schemas here:
# --------------------------------------------------

# Note: The Flames database viewer will automatically:
# 1. Read these schemas from GET /schema endpoint
# 2. Use them for document validation when creating/editing
# 3. Handle all database operations (CRUD) directly
# 4. You don't need to create any database endpoints!
