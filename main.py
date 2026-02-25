from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
import requests
import base64
from dotenv import load_dotenv
from fpdf import FPDF
from docx import Document

# Lade die geheimen Daten aus der .env Datei
load_dotenv()
API_KEY = os.getenv("GOOGLE_VISION_API_KEY")

app = FastAPI()

# Ordner erstellen, falls sie noch nicht existieren
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# Wir machen den outputs-Ordner öffentlich, damit die Download-Buttons funktionieren
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

# Wenn jemand die Startseite aufruft, schicken wir ihm die HTML-Webseite
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

# Der Pfad für den Datei-Upload und die Verarbeitung
@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    # 1. Bild im uploads-Ordner speichern
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. Bild für Google vorbereiten (in Base64 Text umwandeln)
    with open(file_location, "rb") as image_file:
        image_content = image_file.read()
        base64_image = base64.b64encode(image_content).decode("utf-8")
    
    # 3. Anfrage an Google Vision API senden
    google_url = f"https://vision.googleapis.com/v1/images:annotate?key={API_KEY}"
    payload = {
        "requests": [
            {
                "image": {"content": base64_image},
                "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                "imageContext": {"languageHints": ["de"]} 
            }
        ]
    }
    
    response = requests.post(google_url, json=payload)
    result = response.json()
    
    # 4. Text aus der Google-Antwort auslesen
    erkannter_text = ""
    try:
        erkannter_text = result["responses"][0]["fullTextAnnotation"]["text"]
    except KeyError:
        erkannter_text = "Es konnte kein Text auf dem Bild gefunden werden."

    # 5. Dateinamen für PDF und Word vorbereiten (aus "bild.jpg" wird "bild")
    dateiname_ohne_endung = os.path.splitext(file.filename)[0]
    pdf_pfad = f"outputs/{dateiname_ohne_endung}.pdf"
    word_pfad = f"outputs/{dateiname_ohne_endung}.docx"

    # 6. PDF Dokument erstellen
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    sicherer_text = erkannter_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, text=sicherer_text)
    pdf.output(pdf_pfad)

    # 7. Word Dokument erstellen
    doc = Document()
    doc.add_paragraph(erkannter_text)
    doc.save(word_pfad)

    # 8. Antwort an die Webseite (Frontend) zurückschicken
    return {
        "nachricht": "Erfolgreich erkannt und konvertiert!", 
        "dateiname": file.filename,
        "erkannter_text": erkannter_text,
        "erstelltes_pdf": pdf_pfad,
        "erstelltes_word": word_pfad
    }