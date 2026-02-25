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
import fitz  # PyMuPDF für die PDF-Verarbeitung

# Lade die geheimen Daten aus der .env Datei
load_dotenv()
API_KEY = os.getenv("GOOGLE_VISION_API_KEY")

app = FastAPI()

# Ordner erstellen, falls sie noch nicht existieren
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# STATISCHE ORDNER FREIGEBEN
# Damit die Download-Buttons funktionieren:
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
# Damit die index.html auf die style.css zugreifen kann:
app.mount("/static", StaticFiles(directory="static"), name="static")

# Startseite: Liefert die index.html aus dem static-Ordner
@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/upload/")
async def upload_image(file: UploadFile = File(...)):
    # 1. Datei im uploads-Ordner speichern
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    # 2. PDF-Check & Konvertierung
    # Falls es ein PDF ist, wandeln wir die erste Seite in ein Bild um
    if file.filename.lower().endswith('.pdf'):
        pdf_dokument = fitz.open(file_location)
        # Wir nehmen die erste Seite (Index 0)
        erste_seite = pdf_dokument.load_page(0)
        # Erzeuge ein Bild (Pixmap) der Seite
        bild_von_seite = erste_seite.get_pixmap()
        image_content = bild_von_seite.tobytes("png")
        base64_image = base64.b64encode(image_content).decode("utf-8")
        pdf_dokument.close()
    else:
        # Wenn es ein normales Bild ist (jpg/png), direkt einlesen
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
    except (KeyError, IndexError):
        erkannter_text = "Es konnte kein Text auf der Datei gefunden werden."

    # 5. Dateinamen für PDF und Word vorbereiten
    dateiname_ohne_endung = os.path.splitext(file.filename)[0]
    pdf_pfad = f"outputs/{dateiname_ohne_endung}.pdf"
    word_pfad = f"outputs/{dateiname_ohne_endung}.docx"

    # 6. PDF Dokument erstellen
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    # Sonderzeichen-Fix für FPDF
    sicherer_text = erkannter_text.encode('latin-1', 'replace').decode('latin-1')
    pdf.multi_cell(0, 10, text=sicherer_text)
    pdf.output(pdf_pfad)

    # 7. Word Dokument erstellen
    doc = Document()
    doc.add_paragraph(erkannter_text)
    doc.save(word_pfad)

    # 8. Antwort an das Frontend zurückgeben
    return {
        "nachricht": "Erfolgreich erkannt und konvertiert!", 
        "dateiname": file.filename,
        "erkannter_text": erkannter_text,
        "erstelltes_pdf": pdf_pfad,
        "erstelltes_word": word_pfad
    }