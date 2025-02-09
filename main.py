import os
import sqlite3
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, File, UploadFile, HTTPException
import uvicorn
import pytesseract
import cv2
import numpy as np
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Retrieve Spoonacular API key securely
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")

if not SPOONACULAR_API_KEY:
    raise ValueError("Spoonacular API key is missing. Add it to the .env file.")

SPOONACULAR_URL = "https://api.spoonacular.com/recipes/findByIngredients"

# Initialize FastAPI app
app = FastAPI()

# Enable CORS to allow frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database setup
DB_FILE = "pantry.db"

def init_db():
    """Creates the database if it doesn’t exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS grocery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL
        )"""
    )
    conn.commit()
    conn.close()

init_db()  # Initialize database

def save_to_db(item_name):
    """Insert grocery items if they don't exist already."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM grocery_items WHERE name=?", (item_name,))
    existing_item = cursor.fetchone()

    if not existing_item:
        cursor.execute("INSERT INTO grocery_items (name) VALUES (?)", (item_name,))
    
    conn.commit()
    conn.close()

def get_pantry_items():
    """Fetch all items from the pantry."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    items = [{"name": row[0]} for row in cursor.fetchall()]
    conn.close()
    return items

@app.get("/")
def read_root():
    return {"message": "Welcome to MealMaster!"}

@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Processes receipt images, extracts grocery items using OCR, and saves them."""
    try:
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ocr_result = pytesseract.image_to_string(gray)

        structured_data = parse_receipt_text(ocr_result)

        for item in structured_data:
            save_to_db(item["item"])

        return {
            "raw_text": ocr_result,
            "structured_data": structured_data,
            "current_pantry": get_pantry_items()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def parse_receipt_text(ocr_text: str):
    """Extracts structured grocery data from receipt text."""
    items = []
    for line in ocr_text.split("\n"):
        line = line.strip()
        if line:
            items.append({"item": line})  # Store item names only

    return items

@app.get("/pantry")
def get_pantry():
    """Returns the list of pantry items."""
    return {"pantry": get_pantry_items()}

@app.get("/recipes")
def get_recipes():
    """Fetches recipe suggestions based on available pantry ingredients using Spoonacular API."""
    pantry_items = get_pantry_items()
    ingredients = [item["name"] for item in pantry_items]

    if not ingredients:
        return {"message": "No ingredients found in pantry"}

    # Get basic recipe list from Spoonacular
    response = requests.get(SPOONACULAR_URL, params={
        "ingredients": ",".join(ingredients),
        "apiKey": SPOONACULAR_API_KEY,
        "number": 5
    })

    recipe_data = response.json()

    structured_recipes = []

    for recipe in recipe_data:
        recipe_id = recipe.get("id")
        
        # Fetch full recipe details
        recipe_details = requests.get(
            f"https://api.spoonacular.com/recipes/{recipe_id}/information",
            params={"apiKey": SPOONACULAR_API_KEY}
        ).json()

        structured_recipes.append({
            "title": recipe.get("title", "No Title"),
            "image": recipe.get("image", ""),
            "sourceUrl": recipe_details.get("sourceUrl", "https://google.com")  # Ensures valid link
        })

    return structured_recipes

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

