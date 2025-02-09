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
    cursor.execute(
        """CREATE TABLE IF NOT EXISTS grocery_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        )"""
    )
    conn.commit()
    conn.close()

init_db()

def save_to_db(item_name):
    """Insert grocery items if they don't exist already (prevents duplicates)."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        cursor.execute("INSERT INTO grocery_items (name) VALUES (?)", (item_name,))
    except sqlite3.IntegrityError:
        pass  # Prevent duplicates

    conn.commit()
    conn.close()

@app.post("/scan_receipt")
async def scan_receipt(file: UploadFile = File(...)):
    """Processes receipt images and extracts grocery items."""
    try:
        contents = await file.read()
        np_arr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            raise HTTPException(status_code=400, detail="Invalid image file. Could not decode.")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        ocr_result = pytesseract.image_to_string(gray)

        # Simple filtering to remove non-food items
        cleaned_items = [line.strip() for line in ocr_result.split("\n") if len(line) > 2]

        for item in cleaned_items:
            save_to_db(item)

        return {"current_pantry": cleaned_items}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/pantry")
def get_pantry():
    """Returns the list of pantry items properly formatted."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM grocery_items")
    items = [{"name": row[0]} for row in cursor.fetchall()]
    conn.close()
    
    return {"pantry": items}

@app.post("/clear_pantry")
def clear_pantry():
    """Clears all items from the pantry database."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM grocery_items")
    conn.commit()
    conn.close()
    
    return {"message": "Pantry cleared successfully."}


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


