from flask import Flask, render_template, request, jsonify
import pandas as pd
import os

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

file1 = os.path.join(BASE_DIR, "datasets", "recipes1.xlsx")
file2 = os.path.join(BASE_DIR, "datasets", "recipes2.csv")

df1 = pd.read_excel(file1)
df2 = pd.read_csv(file2)

# Merge datasets
df = pd.concat([df1, df2], ignore_index=True)

def normalize(ing):
    ing = ing.strip().lower()
    if ing.endswith('es'):
        return ing[:-2]
    elif ing.endswith('s'):
        return ing[:-1]
    return ing

df['Cleaned-Ingredients'] = df['Cleaned-Ingredients'].fillna('').apply(
    lambda x: [normalize(i) for i in x.lower().split(',') if i.strip()]
)

df['name'] = df['name'] if 'name' in df.columns else 'Recipe'
df['name'] = df['name'].fillna('Recipe')
df['instructions'] = df.get('instructions', 'Cook and enjoy').fillna('Cook and enjoy')
df['cuisine'] = df.get('cuisine', 'General').fillna('General')
df['totalTimeInMins'] = df.get('totalTimeInMins', 30).fillna(30)
df['servings'] = df.get('servings', 2).fillna(2)

def recommend_recipes(user_ingredients, max_time=None, cuisine=None, veg=None):
    user_ingredients = [i.lower().strip() for i in user_ingredients]

    results = []

    for _, row in df.iterrows():

        # 🔽 APPLY FILTERS FIRST
        if max_time:
            if int(row.get("totalTimeInMins", 999)) > int(max_time):
                continue

        if cuisine:
            if cuisine.lower() not in str(row.get("cuisine", "")).lower():
                continue

        if veg == "veg":
            if any(nonveg in row['Cleaned-Ingredients'] for nonveg in ["chicken", "mutton", "fish", "egg"]):
                continue
            
        elif veg == "nonveg":
            if not any(nonveg in row['Cleaned-Ingredients'] for nonveg in ["chicken", "mutton", "fish", "egg"]):
                continue

        recipe_ings = row['Cleaned-Ingredients']
        matches = len(set(user_ingredients) & set(recipe_ings))

        if matches > 0:
            base_score = matches / len(user_ingredients)
            # boost if strong match
            if matches == len(user_ingredients):
                score = min(base_score * 1.5, 1)
            else:
                score = base_score

            import re
            raw_steps = str(row.get("TranslatedInstructions", ""))
            steps = re.split(r'\.\s+|\n+', raw_steps)
            steps = [s.strip() for s in steps if len(s.strip()) > 10]

            results.append({
                "name": str(row.get("final_food_name", "Recipe")),
                "time": f"{int(row.get('totalTimeInMins', 30))} mins",
                "servings": int(row.get("servings", 2)),
                "difficulty": "Medium",
                "description": str(row.get("cuisine", "General")),
                "ingredients": recipe_ings,
                "steps": steps,
                "emoji": "🍲",
                "matchPercent": float(score * 100)
            })

    return sorted(results, key=lambda x: x["matchPercent"], reverse=True)[:50]


@app.route('/')
def home():
    return render_template('recipe-prodigy.html')


@app.route('/recommend', methods=['POST'])
def recommend():
    data = request.get_json()

    user_ingredients = data.get("ingredients", [])
    max_time = data.get("maxTime")
    cuisine = data.get("cuisine")
    veg = data.get("veg")

    recommendations = recommend_recipes(
        user_ingredients,
        max_time=max_time,
        cuisine=cuisine,
        veg=veg
    )

    return jsonify(recommendations)

@app.route("/recommend-by-category", methods=["POST"])
def recommend_by_category():
    data = request.get_json()
    category = data.get("category", "").lower()

    if not category:
        return jsonify([])

    # Map categories to keywords (you can tweak this)
    category_map = {
        "breakfast": ["bread", "egg", "toast", "pancake"],
        "lunch": ["rice", "dal", "curry", "roti"],
        "snacks": ["snack", "pakora", "chaat", "fries"],
        "dinner": ["curry", "rice", "noodle", "paneer"]
    }

    keywords = category_map.get(category, [])

    results = []

    for _, row in df.iterrows():
        recipe_ings = row['Cleaned-Ingredients']

        if any(any(k in ing for ing in recipe_ings) for k in keywords):
            steps = str(row.get("TranslatedInstructions", "")).split(".")
            steps = [s.strip() for s in steps if len(s.strip()) > 10]

            results.append({
                "name": str(row.get("final_food_name", "Recipe")),
                "time": f"{int(row.get('totalTimeInMins', 30))} mins",
                "servings": int(row.get("servings", 2)),
                "difficulty": "Medium",
                "description": str(row.get("cuisine", "General")),
                "ingredients": recipe_ings,
                "steps": steps,
                "emoji": "🍽",
                "matchPercent": 100
            })

    return jsonify(results[:50])

@app.route("/discover", methods=["GET"])
def discover():
    results = []

    valid_df = df[
        df["final_food_name"].notna() &
        df["TranslatedInstructions"].notna() &
        (df["final_food_name"].astype(str).str.strip() != "") &
        (df["TranslatedInstructions"].astype(str).str.strip() != "")
    ]

    sample_size = min(30, len(valid_df))

    import re

    for _, row in valid_df.sample(n=sample_size).iterrows():
        raw_steps = str(row.get("TranslatedInstructions", ""))

        steps = re.split(r'\.\s+|\n+|•|-', raw_steps)
        steps = [s.strip() for s in steps if len(s.strip()) > 15]

        cuisine = str(row.get("cuisine", "")).strip()
        
        if cuisine and cuisine.lower() != "general":
            description = f"{cuisine} • {int(row.get('totalTimeInMins', 30))} mins"
        else:
            description = f"{int(row.get('totalTimeInMins', 30))} mins recipe"

        results.append({
            "name": str(row.get("final_food_name", "Recipe")),
            "time": f"{int(row.get('totalTimeInMins', 30))} mins",
            "servings": int(row.get("servings", 2)),
            "difficulty": "Medium",
            "description": description,
            "ingredients": row['Cleaned-Ingredients'],
            "steps": steps[:20],
            "emoji": "✨",
            "matchPercent": 100
        })

    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True)
