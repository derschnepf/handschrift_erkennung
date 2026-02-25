from fastapi import FastAPI

# Wir erstellen unsere App-Instanz
app = FastAPI()

# Wir definieren eine "Route" (einen Pfad). 
# Wenn jemand die Hauptseite ("/") aufruft, passiert Folgendes:
@app.get("/")
def read_root():
    return {"Nachricht": "Hallo! Mein Backend funktioniert!"}