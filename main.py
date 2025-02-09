import os
import sqlite3
import requests
from fastapi import FastAPI, File, UploadFile, HTTPException
import uvicorn
import pytesseract
import cv2
import numpy as np
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

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

@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Processes receipt images and extracts grocery items."""
    contents = await file.read()
    np_arr = np.frombuffer(contents, np.uint8)
    img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    ocr_result = pytesseract.image_to_string(gray)
    cleaned_items = [line.strip() for line in ocr_result.split("\n") if len(line) > 2]

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    for item in cleaned_items:
        cursor.execute("INSERT OR IGNORE INTO grocery_items (name) VALUES (?)", (item,))
    conn.commit()
    conn.close()

    return {"current_pantry": cleaned_items}

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

