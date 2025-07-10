import logging
from flask import Flask, jsonify, request
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logging.getLogger().setLevel(logging.WARNING)

app = Flask(__name__)

# Load the JSON data once on startup
with open("programs_cleaned.json", "r") as f:
    programs = json.load(f)

@app.route("/programs", methods=["GET"])
def get_programs():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    query_words = query.split()

    results = []
    for p in programs:
        title = p.get("Program Title", "").lower()
        category = p.get("Category", "").lower()

        if any(word in title or word in category for word in query_words):
            results.append({
                "Program Title": p.get("Program Title", ""),
                "Full URL": p.get("Full URL", ""),
                "Category": p.get("Category", "")
            })

    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)
