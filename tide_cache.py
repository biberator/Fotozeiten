import os
import json
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("WORLDTIDES_API_KEY")
LAT = 54.3726
LON = 8.6489

CACHE_FILE = "tide_cache.json"
CACHE_DURATION = timedelta(days=7)  # Cache 7 Tage gültig

def get_tides():
    """
    Lädt Gezeitendaten entweder aus dem Cache oder von der WorldTides API.
    Der Cache wird 7 Tage lang genutzt, danach erfolgt eine neue API-Abfrage.
    Abgefragt werden 28 Tage Gezeiten ab aktuellem Datum.
    """
    now = datetime.now()

    # Prüfen, ob Cache existiert und gültig ist
    if os.path.exists(CACHE_FILE):
        mtime = datetime.fromtimestamp(os.path.getmtime(CACHE_FILE))
        if now - mtime < CACHE_DURATION:
            try:
                with open(CACHE_FILE, "r") as f:
                    print("📥 Lade Gezeiten aus Cache")
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Fehler beim Lesen des Cache: {e}")

    # Falls Cache ungültig oder nicht lesbar -> API abfragen
    print("🌊 Lade Gezeiten von WorldTides API")
    url = "https://www.worldtides.info/api/v2"
    params = {
        "extremes": "",
        "lat": LAT,
        "lon": LON,
        "length": 60*60*24*28,  # 28 Tage in Sekunden
        "key": API_KEY
    }

    try:
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json()

        # Cache speichern
        with open(CACHE_FILE, "w") as f:
            json.dump(data, f)

        return data
    except requests.RequestException as e:
        print(f"❌ Fehler bei API-Abfrage: {e}")

        # Falls Cache noch vorhanden, trotzdem laden
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    print("⚠️ Nutze alten Cache trotz API-Fehler")
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Fehler beim Laden alten Cache: {e}")

        # Kein Cache verfügbar -> leere Daten zurückgeben
        return {"extremes": []}
