from flask import Flask, jsonify, request
import json

app = Flask(__name__)

# Load your JSON file once at startup
with open('programs_cleaned.json', 'r') as f:
    programs = json.load(f)

@app.route('/programs', methods=['GET'])
def get_programs():
    # Optional search with ?q=yoursearch
    query = request.args.get('q', '').strip().lower()
    if query:
        filtered = [
            {
                "Program Title": p["Program Title"],
                "Full URL": p["Full URL"]
            }
            for p in programs
            if query in p["Program Title"].lower()
        ]
        return jsonify(filtered)
    # Return all programs if no query
    return jsonify([
        {
            "Program Title": p["Program Title"],
            "Full URL": p["Full URL"]
        }
        for p in programs
    ])

@app.route('/', methods=['GET'])
def root():
    return jsonify({"message": "PEMF Healing App API is online. Use /programs to access data."})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
