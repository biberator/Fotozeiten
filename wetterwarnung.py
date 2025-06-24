# wetterwarnung.py

import os
from datetime import datetime, timedelta
from pytz import timezone
from icalendar import Calendar, Event

from weather_alerts import check_sturmflut

# Standort: Westerhever, Deutschland
LAT = 54.375  # Breitengrad
LON = 8.642   # Längengrad
TZ = timezone("Europe/Berlin")
OUTPUT_FILE = "docs/fotozeiten-westerhever.ics"

def schreibe_warnung_ins_ics(warntext, pfad):
    cal = Calendar()
    cal.add("prodid", "-//Fotozeiten//Wetterwarnung Westerhever//")
    cal.add("version", "2.0")

    now = datetime.now(TZ)
    start = now
    end = now + timedelta(hours=1)

    event = Event()
    event.add("summary", "⚠️ Wetterwarnung Westerhever")  # Fester Titel
    event.add("description", warntext)                     # Detaillierte Warnung
    event.add("dtstart", start)
    event.add("dtend", end)
    event.add("dtstamp", now)
    event.add("location", "Westerhever, Deutschland")
    event.add("uid", f"wetterwarnung-{now.strftime('%Y%m%d')}@fotozeiten")  # stabil für 1 Termin/Tag
    cal.add_component(event)

    os.makedirs(os.path.dirname(pfad), exist_ok=True)
    with open(pfad, "wb") as f:
        f.write(cal.to_ical())

if __name__ == "__main__":
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if not api_key:
        raise ValueError("OPENWEATHERMAP_API_KEY nicht gesetzt!")

    warnung = check_sturmflut(LAT, LON, api_key)
    if warnung:
        print("✅ Wetterwarnung erkannt, schreibe ICS-Datei.")
        schreibe_warnung_ins_ics(warnung, OUTPUT_FILE)
    else:
        print("ℹ️ Keine Wetterwarnung für Westerhever.")
