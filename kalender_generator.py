# -*- coding: utf-8 -*-
import os
import pytz
import requests
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, dawn, dusk
from astral.location import Observer
from icalendar import Calendar, Event
from dotenv import load_dotenv
from tide_cache import get_tides  # Caching

# .env laden
load_dotenv()

# Standort Süderoogsand (genauer für Tidewerte)
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(
    name="Süderoogsand", region="Germany", timezone=tz.zone,
    latitude=54.2175, longitude=8.5767
)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitrahmen
start_date = datetime.now().date()
end_date = start_date + timedelta(days=13)

# Kalender vorbereiten
cal = Calendar()
cal.add("prodid", "-//Westerhever Fotozeiten//")  # Hier Name "Westerhever"
cal.add("version", "2.0")

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

# Wetterwarnungen (OpenWeatherMap One Call 3.0)
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

    current_date = start_date
    while current_date <= end_date:
        try:
            s = sun(observer, date=current_date, tzinfo=tz)
            dawn_start = dawn(observer, date=current_date, tzinfo=tz)
            dusk_end = dusk(observer, date=current_date, tzinfo=tz)

            # Blaue Stunde (nautische Dämmerung)
            bs_morning_start = dawn_start
            bs_morning_end = s["sunrise"]
            bs_evening_start = s["sunset"]
            bs_evening_end = dusk_end

            # Goldene Stunde (1 Stunde nach Sonnenaufgang, 1 Stunde vor Sonnenuntergang)
            gs_morning_start = s["sunrise"]
            gs_morning_end = gs_morning_start + timedelta(hours=1)
            gs_evening_start = s["sunset"] - timedelta(hours=1)
            gs_evening_end = s["sunset"]

            # Gezeiten für den Tag: Ebbe = Low, Flut = High
            tides = tide_by_date.get(current_date, [])
            unique_tides = {}
            for tide_type, tide_dt in tides:
                time_str = tide_dt.strftime("%H:%M")
                # Überschreibe falls doppelt, so bleiben nur eindeutige Zeiten
                label = "Flut" if tide_type == "High" else "Ebbe"
                unique_tides[time_str] = label

            tide_lines = [f"{zeit} Uhr - {label}" for zeit, label in sorted(unique_tides.items())]

            # Tagesbeschreibung mit Abkürzungen
            beschreibung = "\n".join([
                f"🌅 SA: {s['sunrise'].strftime('%H:%M')}",
                f"🌇 SU: {s['sunset'].strftime('%H:%M')}",
                f"🔵 BS morgens: {bs_morning_start.strftime('%H:%M')} – {bs_morning_end.strftime('%H:%M')}",
                f"🔵 BS abends: {bs_evening_start.strftime('%H:%M')} – {bs_evening_end.strftime('%H:%M')}",
                f"✨ GS morgens: {gs_morning_start.strftime('%H:%M')} – {gs_morning_end.strftime('%H:%M')}",
                f"✨ GS abends: {gs_evening_start.strftime('%H:%M')} – {gs_evening_end.strftime('%H:%M')}",
                "",
                "🌊 Gezeiten:",
                *tide_lines
            ])

            # Tagesüberblick als ein Eintrag
            event = Event()
            event.add("summary", "📋 Tagesüberblick")
            event.add("dtstart", tz.localize(datetime.combine(current_date, datetime.min.time())))
            event.add("dtend", tz.localize(datetime.combine(current_date + timedelta(days=1), datetime.min.time())))
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            cal.add_component(event)

        except Exception as e:
            print(f"⚠️ Fehler bei {current_date}: {e}")
        current_date += timedelta(days=1)

    # Wetterwarnung separat (optional)
    owm_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if owm_api_key:
        alerts = get_weather_alerts(location.latitude, location.longitude, owm_api_key)
        if alerts:
            beschreibung = "\n\n".join(alerts)
            event = Event()
            event.add("summary", "⚠️ Wetterwarnung")
            now = datetime.now(tz)
            event.add("dtstart", now)
            event.add("dtend", now + timedelta(hours=1))
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            cal.add_component(event)

    # Kalender speichern
    os.makedirs("docs", exist_ok=True)
    with open("docs/fotozeiten-westerhever.ics", "wb") as f:
        f.write(cal.to_ical())

    print("📅 Kalender erstellt: docs/fotozeiten-westerhever.ics")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
