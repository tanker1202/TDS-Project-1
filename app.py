from flask import Flask, request, render_template, jsonify
from flask_cors import CORS  
from scrape_utils import scrape_text_from_url, extract_text
import requests
from dotenv import load_dotenv
import difflib
import base64
from PIL import Image
import pytesseract
import io

load_dotenv()
OPENAI_API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJlbWFpbCI6IjIzZjIwMDE2OTFAZHMuc3R1ZHkuaWl0bS5hYy5pbiJ9.bytu_vnkiC5Fkn0lhzLRzgCjMRSBxOU5rwOoVxT6hzs"
OPENAI_URL = "https://aipipe.org/openai/v1/chat/completions"

app = Flask(__name__)
CORS(app)

def extract_text_from_image(base64_str):
    try:
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"[Image text extraction failed: {str(e)}]"

def retrieve_live_context(query: str):
    try:
        sources = [
            ("Course Site", "https://tds.s-anand.net/#/2025-01/"),
            ("Discourse", "https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34"),
        ]

        all_links = []
        context_texts = []

        for source_name, url in sources:
            html = scrape_text_from_url(url)
            text = extract_text(html)
            lines = text.splitlines()
            matches = difflib.get_close_matches(query, lines, n=5, cutoff=0.3)
            for match in matches:
                all_links.append({"url": url, "text": match})
            context_texts.extend(matches)

        return "\n".join(context_texts), all_links

    except Exception as e:
        return f"Error during scraping: {str(e)}", []

def get_openai_response(question: str, context: str) -> str:
    headers = {
        "Authorization": OPENAI_API_KEY,
        "Content-Type": "application/json"
    }

    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful TA. Use the course and forum context to answer the student question."},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}
        ],
        "temperature": 0.5
    }

    response = requests.post(OPENAI_URL, headers=headers, json=payload, timeout=25)
    return response.json()["choices"][0]["message"]["content"]

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        question = request.form.get("question", "")
        context, _ = retrieve_live_context(question)
        answer = get_openai_response(question, context)
        return render_template("index.html", question=question, answer=answer)
    return render_template("index.html")

@app.route("/api", methods=["POST"])
def api():
    try:
        if not request.is_json:
            return jsonify({"error": "Request content-type must be application/json"}), 400

        data = request.get_json()
        question = data.get("question", "")
        image_b64 = data.get("image", "")

        if not question and not image_b64:
            return jsonify({"error": "Missing 'question' or 'image' field"}), 400

        if image_b64:
            image_text = extract_text_from_image(image_b64)
            question += f"\n\nImage Context:\n{image_text}"

        context, links = retrieve_live_context(question)
        answer = get_openai_response(question, context)

        return jsonify({"answer": answer, "links": links})
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Internal server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(debug=True)
