import { useState, useEffect } from "react";
import axios from "axios";
import "./styles.css"; // Import updated styles

export default function App() {
  const [file, setFile] = useState(null);
  const [pantry, setPantry] = useState([]);
  const [recipes, setRecipes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("pantry");

  useEffect(() => {
    fetchPantry();
  }, []);

  const handleFileChange = (event) => setFile(event.target.files[0]);

  const uploadReceipt = async () => {
    if (!file) return alert("Please select a receipt image.");
    setLoading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      await axios.post("http://127.0.0.1:8000/scan_receipt", formData);
      alert("Receipt processed successfully!");
      fetchPantry();
    } catch (error) {
      console.error("Error uploading receipt:", error);
      alert("Failed to process receipt.");
    }
    setLoading(false);
  };

  const fetchPantry = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/pantry");
      setPantry(response.data.pantry);
    } catch (error) {
      console.error("Error fetching pantry:", error);
    }
  };

  const fetchRecipes = async () => {
    try {
      const response = await axios.get("http://127.0.0.1:8000/recipes");
      setRecipes(response.data);
    } catch (error) {
      console.error("Error fetching recipes:", error);
    }
  };

  return (
    <div className="container">
      <h1>MealMaster 🥘</h1>

      <div className="tabs">
        <div className={`tab ${activeTab === "pantry" ? "active" : ""}`} onClick={() => setActiveTab("pantry")}>
          🛒 Pantry
        </div>
        <div className={`tab ${activeTab === "recipes" ? "active" : ""}`} onClick={() => setActiveTab("recipes")}>
          🍽️ Recipes
        </div>
      </div>

      <div className={`tab-content ${activeTab === "recipes" ? "active" : ""}`}>
        <button className="get-recipes-btn" onClick={fetchRecipes}>Get New Recipes</button>
        <ul className="recipes-list">
          {recipes.map((recipe, index) => (
            <li key={index} className="recipe-item">
              <img src={recipe.image} alt={recipe.title} className="recipe-img" />
              <div>
                <strong>{recipe.title}</strong>
                <br />
                <a href={recipe.sourceUrl} target="_blank" rel="noopener noreferrer">View Recipe</a>
              </div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

