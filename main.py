import os
import re
import sqlite3
import cv2
import numpy as np
import pytesseract
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from dotenv import load_dotenv
from PIL import Image
import requests

# Load environment variables
load_dotenv()
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")

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

# Set the correct Tesseract path
pytesseract.pytesseract.tesseract_cmd = "/usr/local/bin/tesseract"  # Adjust if needed

# Define non-food terms to filter out
NON_FOOD_TERMS = {
    "total", "subtotal", "balance", "tax", "visa", "amex", "mastercard",
    "debit", "credit", "store", "amount", "cash", "change", "receipt",
    "transaction", "sales", "discount", "city", "street", "address",
    "due", "items", "qty", "price", "subtotal", "payment", "paid",
    "checkout", "order", "processing fee", "service fee", "delivery",
    "gratuity", "rounding", "supermarket", "san diego", "dreamstime"
}

def clean_text(text):
    """Cleans OCR output by removing garbage text and formatting correctly."""
    text = text.strip().lower()

    # Remove any standalone numbers or weird symbols
    text = re.sub(r"[^a-zA-Z\s]", "", text)  # Keep only letters and spaces

    # Ignore non-food terms
    if len(text) < 3 or any(term in text for term in NON_FOOD_TERMS):
        return None

    return text.title()  # Capitalize for better readability

@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Processes receipt images and extracts only food-related grocery items using Tesseract OCR."""
    try:
        print(f"🔹 Received file: {file.filename}")

        # Convert file to OpenCV format
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image format.")

        print("🔹 Image successfully loaded. Running OCR...")

        # Convert to grayscale and apply thresholding
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        gray = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)

        # Apply dilation and erosion to remove noise
        kernel = np.ones((1, 1), np.uint8)
        gray = cv2.dilate(gray, kernel, iterations=1)
        gray = cv2.erode(gray, kernel, iterations=1)

        # Run OCR with improved preprocessing
        ocr_results = pytesseract.image_to_string(gray, lang="eng")
        print("🔹 OCR Raw Output:", ocr_results)

        if not ocr_results.strip():
            raise HTTPException(status_code=500, detail="OCR failed to detect text. Try a clearer receipt image.")

        # Split lines, clean, and format
        lines = ocr_results.split("\n")
        cleaned_items = []

        for line in lines:
            cleaned = clean_text(line)
            if cleaned:
                cleaned_items.append(cleaned)

        print("🔹 Final Cleaned Pantry Items:", cleaned_items)

        # Save extracted food items to database
        if cleaned_items:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()
            for item in cleaned_items:
                cursor.execute("INSERT OR IGNORE INTO grocery_items (name) VALUES (?)", (item,))
            conn.commit()
            conn.close()
            print("🔹 Pantry Updated in Database!")

        return {"extracted_items": cleaned_items}

    except Exception as e:
        print(f"🔹 Error processing receipt: {e}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")

@app.get("/pantry")
def get_pantry():
    """Retrieves all grocery items from the pantry database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    items = [row[0] for row in cursor.fetchall()]
    conn.close()

    print(f"🔹 Pantry Items Sent to Frontend: {items}")  # Debugging log

    return {"pantry_items": items}


@app.post("/clear_pantry")
def clear_pantry():
    """Deletes all items from the pantry database."""
    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM grocery_items")  # ✅ Clears all items
        conn.commit()
        conn.close()
        print("🔹 Pantry cleared successfully!")
        return {"message": "Pantry cleared!"}
    except Exception as e:
        print(f"🔹 DEBUG: Error clearing pantry - {e}")
        raise HTTPException(status_code=500, detail="Failed to clear pantry.")

@app.get("/recipes")
def get_recipes():
    """Fetch recipes based on pantry items."""
    try:
        # Fetch pantry items
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM grocery_items")
        pantry_items = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not pantry_items:
            raise HTTPException(status_code=400, detail="No pantry items found.")

        print(f"🔹 Searching recipes for: {', '.join(pantry_items)}")

        # Call Spoonacular API
        url = "https://api.spoonacular.com/recipes/findByIngredients"
        params = {
            "ingredients": ",".join(pantry_items),
            "number": 5,
            "apiKey": SPOONACULAR_API_KEY
        }

        response = requests.get(url, params=params)
        response.raise_for_status()  # Raise an error if request fails

        recipes = response.json()
        print("🔹 Spoonacular API Response:", recipes)  # Debug log

        if not recipes:
            return {"message": "No recipes found."}

        structured_recipes = [
            {
                "title": recipe["title"],
                "image": recipe["image"],
                "sourceUrl": f"https://spoonacular.com/recipes/{recipe['id']}"
            }
            for recipe in recipes
        ]

        return structured_recipes

    except requests.exceptions.RequestException as e:
        print(f"🔹 API Request Error: {e}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Error fetching recipes: {str(e)}")

    except Exception as e:
        print(f"🔹 General Error in get_recipes: {e}")  # Debug print
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

