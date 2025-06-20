# -*- coding: utf-8 -*-
import os
import pytz
import requests
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, golden_hour, dawn, dusk
from astral.location import Observer
from icalendar import Calendar, Event
from dotenv import load_dotenv
from tide_cache import get_tides  # Neuer Import für Caching

# .env laden
load_dotenv()

# Standort Westerhever
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(name="Westerhever", region="Germany", timezone=tz.zone,
                        latitude=54.3726, longitude=8.6489)
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

# Wetterwarnungen (One Call API 3.0, nur wenn nötig)
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
        messages = []
        for alert in alerts:
            event = alert.get("event", "Warnung")
            desc = alert.get("description", "")
            messages.append(f"{event}: {desc}")
        return messages
    except Exception as e:
        print(f"⚠️ Fehler bei Wetterwarnung: {e}")
        return []

# Kalender generieren
def generate_calendar():
    tide_data = get_tides()
    tides_raw = tide_data.get("extremes", [])
    print(f"🌊 Gezeitendaten (aus Cache oder API): {len(tides_raw)} Einträge erhalten.")
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

    # Wetterwarnung einmalig prüfen
owm_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
if owm_api_key:
    alerts = get_weather_alerts(location.latitude, location.longitude, owm_api_key)
    if alerts:
        description = "\n\n".join(alerts)
        now = datetime.now(tz)
        event = Event()
        event.add("summary", "⚠️ Wetterwarnungen")
        event.add("dtstart", now)
        event.add("dtend", now + timedelta(hours=1))
        event.add("dtstamp", datetime.now(pytz.utc))
        event.add("description", description)
        event.add("uid", "wetterwarnungen-westerhever@example.com")
        cal.add_component(event)

    # Ordner sicherstellen
    os.makedirs("docs", exist_ok=True)
    with open("docs/fotozeiten-westerhever.ics", "wb") as f:
        f.write(cal.to_ical())

    print("📅 Kalender erstellt: docs/fotozeiten-westerhever.ics")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

# Ausführen
if __name__ == "__main__":
    generate_calendar()
