import { useState, useEffect } from "react";
import axios from "axios";
import "./styles.css"; // Import updated styles

export default function App() {
  const [file, setFile] = useState(null);
  const [pantry, setPantry] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("pantry"); // Default to Pantry Tab

  // Fetch pantry items on load
  useEffect(() => {
    fetchPantry();
  }, []);

  // Handle file selection
  const handleFileChange = (event) => {
    setFile(event.target.files[0]);
  };

  // Upload receipt for OCR
  const uploadReceipt = async () => {
    if (!file) return alert("Please select a receipt image.");
    setLoading(true);

    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post("http://127.0.0.1:8000/scan_receipt", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      alert("Receipt processed successfully!");
      fetchPantry();
    } catch (error) {
      console.error("Error uploading receipt:", error);
      alert("Failed to process receipt.");
    }
    setLoading(false);
  };

  // Fetch pantry items
  const fetchPantry = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/pantry");
      setPantry(response.data.pantry);
    } catch (error) {
      console.error("Error fetching pantry:", error);
    }
  };

  // Fetch recipes
  const fetchRecipes = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/recipes");
      if (Array.isArray(response.data)) {
        setRecipes(response.data);
      } else {
        console.error("Unexpected recipe data format:", response.data);
        setRecipes([]);
      }
    } catch (error) {
      console.error("Error fetching recipes:", error);
    }
  };

  return (
    <div className="container">
      <h1>MealMaster 🥘</h1>

      {/* Upload Section */}
      <div className="upload-section">
        <input type="file" onChange={handleFileChange} />
        <button onClick={uploadReceipt} disabled={loading}>
          {loading ? "Processing..." : "Upload Receipt"}
        </button>
      </div>

      {/* Tab Navigation */}
      <div className="tabs">
        <div className={`tab ${activeTab === "pantry" ? "active" : ""}`} onClick={() => setActiveTab("pantry")}>
          🛒 Pantry
        </div>
        <div className={`tab ${activeTab === "recipes" ? "active" : ""}`} onClick={() => setActiveTab("recipes")}>
          🍽️ Recipes
        </div>
      </div>

      {/* Pantry Tab Content */}
      <div className={`tab-content ${activeTab === "pantry" ? "active" : ""}`}>
        <ul className="pantry-list">
          {pantry.length === 0 ? (
            <p>No items in pantry yet.</p>
          ) : (
            pantry.map((item, index) => (
              <li key={index}>{item.name}</li>
            ))
          )}
        </ul>
      </div>

      {/* Recipes Tab Content */}
      <div className={`tab-content ${activeTab === "recipes" ? "active" : ""}`}>
        <button className="get-recipes-btn" onClick={fetchRecipes}>Get Recipes</button>
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
                  <a href={recipe.sourceUrl} target="_blank" rel="noopener noreferrer">View Recipe</a>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}

