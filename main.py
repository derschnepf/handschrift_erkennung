from fastapi import FastAPI, File, UploadFile, Form
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import shutil
import os
import requests
import base64
from dotenv import load_dotenv
from fpdf import FPDF
from docx import Document
import fitz

# Lade die geheimen Daten aus der .env Datei
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

app = FastAPI()

# Ordner erstellen, falls sie noch nicht existieren
os.makedirs("uploads", exist_ok=True)
os.makedirs("outputs", exist_ok=True)

# Statische Ordner freigeben (für Downloads und CSS)
app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def read_root():
    return FileResponse("static/index.html")

@app.post("/upload/")
async def upload_image(
    file: UploadFile = File(...), 
    custom_filename: str = Form(None)
):
    # 1. Datei im uploads-Ordner speichern
    file_location = f"uploads/{file.filename}"
    with open(file_location, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    mime_type = "image/jpeg"
    
    # 2. PDF-Check & Bildkonvertierung
    if file.filename.lower().endswith('.pdf'):
        pdf_dokument = fitz.open(file_location)
        erste_seite = pdf_dokument.load_page(0)
        bild_von_seite = erste_seite.get_pixmap()
        image_content = bild_von_seite.tobytes("png")
        base64_image = base64.b64encode(image_content).decode("utf-8")
        pdf_dokument.close()
        mime_type = "image/png"
    else:
        with open(file_location, "rb") as image_file:
            image_content = image_file.read()
            base64_image = base64.b64encode(image_content).decode("utf-8")
        if file.filename.lower().endswith('.png'):
            mime_type = "image/png"
    
    # 3. Anfrage an Gemini 1.5 Flash senden
    gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"
    
    prompt_text = (
        "Lies den gesamten Text auf diesem Bild. "
        "Wandle alle mathematischen Formeln zwingend in LaTeX um. "
        "Gib nur den erkannten Text und die Formeln zurück, schreibe keine Einleitung oder Begrüßung."
    )
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text},
                    {
                        "inlineData": { 
                            "mimeType": mime_type, 
                            "data": base64_image
                        }
                    }
                ]
            }
        ]
    }
    
    response = requests.post(gemini_url, json=payload)
    result = response.json()
    
    # (Optional) Zur Fehlersuche im Terminal drucken
    print("\n--- GEMINI ANTWORT ---")
    print(result)
    print("----------------------\n")
    
    # 4. Text aus der Antwort auslesen oder Fehler abfangen
    erkannter_text = ""
    try:
        erkannter_text = result["candidates"][0]["content"]["parts"][0]["text"]
    except KeyError:
        fehlermeldung = result.get("error", {}).get("message", "Unbekannter Fehler bei Gemini")
        erkannter_text = f"FEHLER: Es konnte kein Text erkannt werden. Google sagt: {fehlermeldung}"

    # 5. Dateinamen Logik anwenden
    original_name = os.path.splitext(file.filename)[0]
    
    if custom_filename and custom_filename.strip():
        # Eigener Name (ohne Endung)
        basis_name = os.path.splitext(custom_filename.strip())[0]
    else:
        # Standard Name
        basis_name = original_name

    pdf_pfad = f"outputs/{basis_name}.pdf"
    word_pfad = f"outputs/{basis_name}.docx"

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

    # 8. Antwort zurückgeben
    return {
        "nachricht": "Erfolgreich erkannt und konvertiert!", 
        "dateiname": file.filename,
        "erkannter_text": erkannter_text,
        "erstelltes_pdf": pdf_pfad,
        "erstelltes_word": word_pfad
    }