import { useState, useEffect } from "react";
import axios from "axios";
import "./styles.css";

export default function App() {
  const [file, setFile] = useState(null);
  const [pantry, setPantry] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [recipeLoading, setRecipeLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [activeTab, setActiveTab] = useState("pantry");

useEffect(() => {
  fetchPantry();  // Fetch pantry when component mounts
}, []);


  const handleFileChange = (event) => setFile(event.target.files[0]);

const uploadReceipt = async () => {
  if (!file) {
    alert("Please select a receipt image.");
    return;
  }
  setLoading(true);
  setErrorMessage("");

  const formData = new FormData();
  formData.append("file", file);

  try {
    const response = await axios.post("http://127.0.0.1:8000/scan_receipt", formData);
    alert("Receipt processed successfully!");
    fetchPantry(); // ✅ This will refresh the pantry list after scanning
  } catch (error) {
    console.error("Error uploading receipt:", error);
    setErrorMessage("Failed to process receipt. Please try again.");
  } finally {
    setLoading(false);
  }
};


const fetchPantry = async () => {
  try {
    console.log("🔹 Fetching pantry...");
    const response = await axios.get("http://127.0.0.1:8000/pantry");
    console.log("🔹 Pantry Response:", response.data);
    
    // ✅ Ensure pantry items update immediately
    setPantry(response.data.pantry_items ? [...response.data.pantry_items] : []);
  } catch (error) {
    console.error("Error fetching pantry:", error);
  }
};


const fetchRecipes = async () => {
    setRecipeLoading(true);
    setRecipes([]);

    try {
        const response = await axios.get("http://127.0.0.1:8000/recipes");

        if (response.data.message) {
            alert(response.data.message);
        } else if (!Array.isArray(response.data)) {
            alert("Unexpected response format from server.");
        } else {
            setRecipes(response.data);
        }
    } catch (error) {
        console.error("Error fetching recipes:", error);
        alert("Failed to fetch recipes. Please check the backend and try again.");
    } finally {
        setRecipeLoading(false);
    }
};


  const clearPantry = async () => {
    try {
      await axios.post("http://127.0.0.1:8000/clear_pantry");
      alert("Pantry cleared!");
      setPantry([]);
    } catch (error) {
      console.error("Error clearing pantry:", error);
    }
  };

  return (
    <div className="container">
      <h1>MealMaster 🥘</h1>

{/* Upload Form */}
<div className="upload-section">
  {/* Styled File Input Button */}
  <label htmlFor="file-upload" className="upload-label">
   📁 Browse..
  </label>
  <input
    id="file-upload"
    type="file"
    onChange={handleFileChange}
    style={{ display: "none" }} // Keeps the default input hidden
  />
  
  {/* Show Selected File Name */}
  {file && <p className="file-name">{file.name}</p>}

  {/* Upload Button */}
  <button className="upload-btn" onClick={uploadReceipt} disabled={loading || !file}>
    {loading ? "Processing..." : "Upload Receipt"}
  </button>
</div>


      {/* Tabs */}
      <div className="tabs">
        <div className={`tab ${activeTab === "pantry" ? "active" : ""}`} onClick={() => setActiveTab("pantry")}>
          🛒 Pantry
        </div>
        <div className={`tab ${activeTab === "recipes" ? "active" : ""}`} onClick={() => setActiveTab("recipes")}>
          🍽️ Recipes
        </div>
      </div>

      {/* Pantry Tab */}
      {activeTab === "pantry" && (
        <div className="tab-content active">
          <ul className="pantry-list">
            {pantry.length === 0 ? (
              <p>No items in pantry yet.</p>
            ) : (
              pantry.map((item, index) => <li key={index} className="pantry-item">{item}</li>)
            )}
          </ul>
          <button className="clear-btn" onClick={clearPantry}>Clear Pantry</button>
        </div>
      )}

      {/* Recipes Tab */}
      {activeTab === "recipes" && (
        <div className="tab-content active">
          <button className="get-recipes-btn" onClick={fetchRecipes} disabled={recipeLoading}>
            {recipeLoading ? "Fetching..." : "Get New Recipes"}
          </button>
          <ul className="recipes-list">
            {recipes.length === 0 ? (
              <p>No recipes found.</p>
            ) : (
              recipes.map((recipe, index) => (
                <li key={index} className="recipe-item">
                  <img src={recipe.image} alt={recipe.title} className="recipe-img" />
                  <div>
                    <strong>{recipe.title}</strong>
                    <br />
                    <a href={recipe.sourceUrl} target="_blank" rel="noopener noreferrer">
                      View Recipe
                    </a>
                  </div>
                </li>
              ))
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

