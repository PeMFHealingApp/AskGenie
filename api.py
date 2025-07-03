from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# Load JSON data once at startup
with open("programs_cleaned.json", "r") as f:
    programs = json.load(f)

@app.route("/programs", methods=["GET"])
def get_programs():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])

    results = []
    for p in programs:
        title = p.get("Program Title", "").lower()
        category = p.get("Category", "").lower()
        if query in title or query in category:
            results.append({
                "Program Title": p.get("Program Title", ""),
                "Full URL": p.get("Full URL", ""),
                "Category": p.get("Category", "")
            })

    return jsonify(results)
