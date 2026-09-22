import os
import re
import sqlite3
import requests
import pytesseract
import cv2
import numpy as np
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from fuzzywuzzy import process
from spellchecker import SpellChecker

# Load environment variables
load_dotenv()
SPOONACULAR_API_KEY = os.getenv("SPOONACULAR_API_KEY")

# Initialize FastAPI app
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

# Initialize SQLite database
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS grocery_items (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)"
    )
    conn.commit()
    conn.close()


init_db()

# Initialize SpellChecker for OCR correction
spell = SpellChecker()

# Common non-food terms to remove
NON_FOOD_TERMS = {
    "total", "subtotal", "balance", "tax", "visa", "amex", "mastercard",
    "debit", "credit", "store", "amount", "cash", "change", "receipt",
    "transaction", "sales", "discount", "city", "street", "address",
    "due", "items", "qty", "price", "payment", "paid",
    "checkout", "order", "processing fee", "service fee",
    "delivery", "gratuity", "rounding", "thank",
    "card", "date", "invoice", "@", "$/kg", "$/ka",
    "$/kq", "$/lb", "$/g",
    # Non-food items
    "baby wipes", "toilet paper",
    # Store-related terms
    "dreamstimecom", "supermarket"
}

# Common food-related keywords for verification
FOOD_KEYWORDS = {
    # Fruits and vegetables
    "apple", "banana", "grape", "orange",
    # Dairy products
    "milk", "cheese", "yogurt",
    # Proteins and meat products
    "chicken breast", "tuna",
    # Snacks and baked goods
    "cookies", "crackers"
}

# Function to check if an item is likely a food item
def is_food_item(text):
    text = text.lower().strip()

    # Remove very short items (likely junk)
    if len(text) < 3:
        return False

    # Ignore standalone numbers and symbols
    if re.match(r"^\d+(\.\d{1,2})?$", text) or re.match(r"^[\W_]+$", text):
        return False

    # Ignore lines with weights or prices (e.g., '0.218kg net @ $14.99/kg')
    if re.search(r"\d+(?:\.\d+)?(kg|lb|g|ka|kq|@|\$)", text):
        return False

    # Ignore common non-food words or phrases
    if any(term in text for term in NON_FOOD_TERMS):
        return False

    # Verify against food-related keywords (must match at least one)
    if not any(keyword in text for keyword in FOOD_KEYWORDS):
        return False

    return True  # Keep as a valid food item


# Function to correct OCR errors using spell-checking and fuzzy matching
def correct_ocr_errors(item):
    # Split the item into words and correct each word using SpellChecker
    corrected_words = []
    
    for word in item.split():
        corrected_word = spell.correction(word)  # Correct spelling errors
        corrected_words.append(corrected_word if corrected_word else word)

    corrected_item = ' '.join(corrected_words)

    # Use fuzzy matching to verify against known food keywords (if applicable)
    best_match, score = process.extractOne(corrected_item, FOOD_KEYWORDS)
    
    if score > 80:  # Only accept matches with high confidence (>80%)
        return best_match

    return corrected_item


@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    try:
        print(f"🔹 Received file: {file.filename}")

        # Read the file and convert it to a NumPy array
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            print("🔹 ERROR: Image decoding failed.")
            raise HTTPException(status_code=400, detail="Invalid image format.")

        print("🔹 Image successfully loaded. Running OCR...")

        # Convert image to grayscale for better OCR accuracy
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Use PyTesseract OCR to extract text from the image
        ocr_text = pytesseract.image_to_string(gray)

        # Split into lines and filter out non-food items
        ocr_lines = ocr_text.split("\n")

        cleaned_items = []
        temp_item = []

        for line in ocr_lines:
            item = line.strip().lower()

            # Skip empty lines or invalid items based on filtering rules
            if not item or not is_food_item(item):
                continue

            # Remove price information (e.g., '$4.66' or '$1.32')
            item = re.sub(r"\$\d+(\.\d{1,2})?", "", item).strip()

            # Remove extra spaces or special characters at the start/end of the line
            item = re.sub(r"[^a-z\s]", "", item).strip()

            # Correct OCR errors in the item using spell-checking and fuzzy matching
            corrected_item = correct_ocr_errors(item)

            # Group short words with previous items (if applicable)
            if len(corrected_item.split()) == 1 and len(corrected_item) < 5:
                temp_item.append(corrected_item)
            else:
                if temp_item:
                    corrected_item = f"{' '.join(temp_item)} {corrected_item}"
                    temp_item = []
                cleaned_items.append(corrected_item)

        # Add any remaining grouped words as an item
        if temp_item:
            cleaned_items.append(" ".join(temp_item))

        print("🔹 Final Cleaned Pantry Items:", cleaned_items)

        # Store in database (only unique items)
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.executemany(
            "INSERT OR IGNORE INTO grocery_items (name) VALUES (?)",
            [(item,) for item in cleaned_items],
        )
        conn.commit()
        conn.close()

        return {"message": f"Pantry updated successfully with {len(cleaned_items)} items!"}

    except Exception as e:
        print(f"🔹 Error processing receipt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")


@app.get("/pantry")
def get_pantry():
    """Retrieves all pantry items from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    pantry_items = [row[0] for row in cursor.fetchall()]
    conn.close()

    print("🔹 Pantry Items Sent to Frontend:", pantry_items)
    return {"pantry_items": pantry_items}


@app.post("/clear_pantry")
def clear_pantry():
    """Clears all pantry items from the database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM grocery_items")
    conn.commit()
    conn.close()
    return {"message": "Pantry cleared!"}


@app.get("/recipes")
async def get_recipes():
    try:
        # Fetch pantry items from the database
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM grocery_items")
        pantry_items = [row[0] for row in cursor.fetchall()]
        conn.close()

        if not pantry_items:
            return {"message": "No items in pantry to generate recipes."}

        # Convert list to Spoonacular format (comma-separated string of ingredients)
        query = ",".join(pantry_items)

        # Spoonacular API request to fetch recipes based on ingredients
        api_url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={query}&number=10&apiKey={SPOONACULAR_API_KEY}"
        
        response = requests.get(api_url)
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Error fetching recipes from Spoonacular.")

        recipes = response.json()

        # Ensure recipes are valid and include fallback for missing URLs
        structured_recipes = [
            {
                "title": r["title"],
                "image": r["image"],
                "sourceUrl": r.get("sourceUrl") or f"https://spoonacular.com/recipes/{r['id']}",
                "usedIngredients": [i["name"] for i in r.get("usedIngredients", [])],
                "missedIngredients": [i["name"] for i in r.get("missedIngredients", [])],
            }
            for r in recipes if r.get("title") and r.get("image")
        ]

        return {"recipes": structured_recipes} if structured_recipes else {"message": "No valid recipes found."}

    except requests.exceptions.RequestException as e:
        print(f"🔹 API Request Error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching recipes: {str(e)}")

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)

