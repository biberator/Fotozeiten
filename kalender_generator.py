# -*- coding: utf-8 -*-
import requests
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, golden_hour, dawn, dusk
from astral.location import Observer
import pytz
from icalendar import Calendar, Event
from dotenv import load_dotenv
import os

# .env laden
load_dotenv()
API_KEY = os.getenv("WORLDTIDES_API_KEY")

# Standort Westerhever
location = LocationInfo(name="Westerhever", region="Germany", timezone="Europe/Berlin",
                        latitude=54.3726, longitude=8.6489)
tz = pytz.timezone(location.timezone)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitrahmen
start_date = datetime.now().date()
end_date = start_date + timedelta(days=13)

# Kalender vorbereiten
cal = Calendar()
cal.add("prodid", "-//Fotozeiten Westerhever//")
cal.add("version", "2.0")

def add_event(summary, dt, duration_minutes=0):
    event = Event()
    event.add("summary", summary)
    event.add("dtstart", dt)
    event.add("dtend", dt + timedelta(minutes=duration_minutes))
    event.add("dtstamp", datetime.now(pytz.utc))
    cal.add_component(event)

def add_period(summary, start_dt, end_dt):
    event = Event()
    event.add("summary", summary)
    event.add("dtstart", start_dt)
    event.add("dtend", end_dt)
    event.add("dtstamp", datetime.now(pytz.utc))
    cal.add_component(event)

# Gezeiten abrufen
def fetch_tides():
    url = "https://www.worldtides.info/api/v2"
    params = {
        "extremes": "",
        "lat": location.latitude,
        "lon": location.longitude,
        "length": 60 * 60 * 24 * 14,  # 14 Tage
        "key": API_KEY
    }
    response = requests.get(url, params=params)
    data = response.json()
    extremes = data.get("extremes", [])
    print(f"🌊 Gezeitendaten: {len(extremes)} Einträge erhalten.")
    return extremes

# Gezeiten organisieren
def build_tide_lookup(tides_raw):
    tide_by_date = {}
    for tide in tides_raw:
        dt = datetime.fromtimestamp(tide["dt"], tz=pytz.utc).astimezone(tz)
        date = dt.date()
        if date not in tide_by_date:
            tide_by_date[date] = []
        tide_by_date[date].append((tide["type"], dt))
    return tide_by_date

# Kalender generieren
def generate_calendar():
    tides_raw = fetch_tides()
    tide_by_date = build_tide_lookup(tides_raw)

    total = 0
    current_date = start_date
    while current_date <= end_date:
        try:
            s = sun(observer, date=current_date, tzinfo=tz)

            # Sonnenaufgang/-untergang als Zeitpunkte
            add_event("🌅 Sonnenaufgang", s["sunrise"])
            add_event("🌇 Sonnenuntergang", s["sunset"])

            # Goldene Stunde (abends)
            gh = golden_hour(observer, date=current_date, tzinfo=tz)
            add_period("✨ Goldene Stunde", gh[0], gh[1])

            # Blaue Stunde = Nautische Dämmerung (vor Sonnenaufgang & nach Sonnenuntergang)
            dawn_start = dawn(observer, date=current_date, tzinfo=tz)
            dusk_end = dusk(observer, date=current_date, tzinfo=tz)
            add_period("🔵 Blaue Stunde (morgens)", dawn_start, s["sunrise"])
            add_period("🔵 Blaue Stunde (abends)", s["sunset"], dusk_end)

            # Gezeiten
            for tide_type, tide_dt in tide_by_date.get(current_date, []):
                symbol = "🔺" if tide_type == "High" else "🔻"
                label = "Hochwasser" if tide_type == "High" else "Niedrigwasser"
                add_event(f"{symbol} {label}", tide_dt)

        except Exception as e:
            print(f"⚠️ Fehler bei {current_date}: {e}")
        current_date += timedelta(days=1)

    # Ordner sicherstellen
        os.makedirs("docs", exist_ok=True)

# Kalender schreiben
        with open("docs/fotozeiten-westerhever.ics", "wb") as f:
            f.write(cal.to_ical())

        print("📅 Kalender erstellt: docs/fotozeiten-westerhever.ics")
        print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

# Ausführen
if __name__ == "__main__":
    generate_calendar()