import os
import re
import sqlite3
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException
import uvicorn
import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import easyocr

# Load environment variables
load_dotenv()
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")

print(f"🔹 DEBUG: Spoonacular API Key: {SPOONACULAR_API_KEY}")

app = FastAPI()

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "pantry.db"

def init_db():
    """Creates the database if it doesn’t exist."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS grocery_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    conn.commit()
    conn.close()

init_db()


reader = easyocr.Reader(['en'])  # Load EasyOCR with English language support

# List of common non-food words to ignore
NON_FOOD_TERMS = {
    "total", "subtotal", "balance", "tax", "visa", "amex", "mastercard",
    "debit", "credit", "store", "amount", "cash", "change", "receipt",
    "transaction", "sales", "discount", "city", "street", "address"
}

def is_food_item(text):
    """Determines if a scanned text is likely a food item."""
    text = text.lower().strip()

    # Ignore if it's in the NON_FOOD_TERMS list
    if any(term in text for term in NON_FOOD_TERMS):
        return False

    # Ignore if it contains mostly numbers or special characters
    if re.match(r"^\d+(\.\d{2})?$", text) or re.match(r"^[\W_]+$", text):
        return False

    # Ignore if it's very short (likely junk data)
    if len(text) < 3:
        return False

    return True  # Keep as a valid food item

@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Processes receipt images and extracts only food-related grocery items."""
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

    # Convert image to grayscale for better OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Use EasyOCR to extract text
    ocr_results = reader.readtext(gray, detail=0)  # Get raw text output

    # Filter results to remove non-food items
    cleaned_items = [line.strip() for line in ocr_results if is_food_item(line)]

    # Save extracted food items to database
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for item in cleaned_items:
        cursor.execute("INSERT OR IGNORE INTO grocery_items (name) VALUES (?)", (item,))
    conn.commit()
    conn.close()

    return {"extracted_items": cleaned_items}


@app.get("/pantry")
def get_pantry():
    """Returns the list of pantry items properly formatted."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    items = [{"name": row[0]} for row in cursor.fetchall()]
    conn.close()
    
    return {"pantry": items}

def get_pantry_items():
    """Fetch all items from the pantry database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    items = [{"name": row[0]} for row in cursor.fetchall()]
    conn.close()
    return items


@app.get("/recipes")
def get_recipes():
    """Fetches recipes based on pantry ingredients using Spoonacular API."""
    try:
        pantry_items = get_pantry_items()
        ingredients = [item["name"] for item in pantry_items]

        if not ingredients:
            return {"message": "No ingredients found in pantry"}

        if not SPOONACULAR_API_KEY:
            raise HTTPException(status_code=500, detail="Spoonacular API Key is missing!")

        response = requests.get("https://api.spoonacular.com/recipes/findByIngredients", params={
            "ingredients": ",".join(ingredients),
            "apiKey": SPOONACULAR_API_KEY,
            "number": 5
        })
        response.raise_for_status()

        recipe_data = response.json()
        structured_recipes = []

        for recipe in recipe_data:
            if "id" in recipe and "title" in recipe and "image" in recipe:
                recipe_id = recipe["id"]
                
                # Fetch full recipe details for valid URLs
                details_response = requests.get(
                    f"https://api.spoonacular.com/recipes/{recipe_id}/information",
                    params={"apiKey": SPOONACULAR_API_KEY}
                )
                details_response.raise_for_status()
                details = details_response.json()

                source_url = details.get("sourceUrl", "")
                if source_url:
                    structured_recipes.append({
                        "title": recipe["title"],
                        "image": recipe["image"],
                        "sourceUrl": source_url
                    })

        return structured_recipes if structured_recipes else {"message": "No valid recipes found."}

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Error fetching recipes: {str(e)}")

    except Exception as e:
        print(f"General Error in get_recipes: {e}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.post("/clear_pantry")
def clear_pantry():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM grocery_items")
    conn.commit()
    conn.close()
    return {"message": "Pantry cleared!"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

