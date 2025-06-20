import os
import pytz
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event
from dotenv import load_dotenv

load_dotenv()

tz = pytz.timezone("Europe/Berlin")
lat, lon = 54.3726, 8.6489
ics_path = "docs/fotozeiten-westerhever.ics"

def get_weather_alerts(lat, lon, api_key):
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "exclude": "current,minutely,hourly,daily"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        alerts = data.get("alerts", [])
        return [
            f"{alert.get('event', 'Warnung')}\n{alert.get('description', '')}"
            for alert in alerts
        ]
    except Exception as e:
        print(f"⚠️ Fehler bei Wetterwarnung: {e}")
        return []

def update_ics_with_alerts(alerts):
    cal = Calendar()

    # Bestehende Datei einlesen, falls vorhanden
    if os.path.exists(ics_path):
        with open(ics_path, "rb") as f:
            cal = Calendar.from_ical(f.read())

    now = datetime.now(tz)
    existing_uid = "wetterwarnung@westerhever"

    # Entferne alten Eintrag mit gleicher UID
    cal.subcomponents = [
        c for c in cal.subcomponents
        if not (isinstance(c, Event) and str(c.get("uid")) == existing_uid)
    ]

    if not alerts:
        print("ℹ️ Keine aktuellen Wetterwarnungen.")
        return

    # Füge neuen Eintrag hinzu
    event = Event()
    event.add("summary", "⚠️ Wetterwarnungen")
    event.add("description", "\n\n".join(alerts))
    event.add("dtstart", now)
    event.add("dtend", now + timedelta(hours=1))
    event.add("dtstamp", now)
    event.add("uid", existing_uid)
    cal.add_component(event)

    # Speichern
    os.makedirs(os.path.dirname(ics_path), exist_ok=True)
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())
    print("✅ Wetterwarnung in Kalender ergänzt.")
