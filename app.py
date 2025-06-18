from flask import Flask, request, render_template, jsonify
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

def extract_text_from_image(base64_str):
    try:
        image_data = base64.b64decode(base64_str)
        image = Image.open(io.BytesIO(image_data))
        return pytesseract.image_to_string(image)
    except Exception as e:
        return f"[Image text extraction failed: {str(e)}]"

def retrieve_live_context(query: str) -> str:
    try:
        # Live scrape both sites
        html1 = scrape_text_from_url("https://tds.s-anand.net/#/2025-01/")
        html2 = scrape_text_from_url("https://discourse.onlinedegree.iitm.ac.in/c/courses/tds-kb/34")

        text1 = extract_text(html1)
        text2 = extract_text(html2)

        lines1 = text1.splitlines()
        lines2 = text2.splitlines()

        matches1 = difflib.get_close_matches(query, lines1, n=5, cutoff=0.3)
        matches2 = difflib.get_close_matches(query, lines2, n=5, cutoff=0.3)

        context = "Course Site:\n" + "\n".join(matches1) + "\n\nDiscourse Posts:\n" + "\n".join(matches2)
        return context
    except Exception as e:
        return f"Error during scraping: {str(e)}"

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
        question = request.form["question"]
        context = retrieve_live_context(question)
        answer = get_openai_response(question, context)
        return render_template("index.html", question=question, answer=answer)
    return render_template("index.html")

@app.route("/api", methods=["POST"])
def api():
    data = request.get_json()
    question = data.get("question", "")
    image_b64 = data.get("image", "")

    # If image is given, extract text from it and append to question
    if image_b64:
        image_text = extract_text_from_image(image_b64)
        question += f"\n\nImage Context:\n{image_text}"

    context = retrieve_live_context(question)
    answer = get_openai_response(question, context)

    return jsonify({"answer": answer})

if __name__ == "__main__":
    app.run(debug=True)
