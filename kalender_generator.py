# -*- coding: utf-8 -*-
import os
import pytz
import requests
import uuid
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, dawn, dusk, golden_hour
from astral.location import Observer
from icalendar import Calendar, Event, vDate
from dotenv import load_dotenv
from tide_cache import get_tides  # Import für Gezeitendaten mit Caching

# .env laden
load_dotenv()

# Standort Pellworm für genauere Gezeiten
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(name="Westerhever (Pegel: Pellworm)", region="Germany", timezone=tz.zone,
                        latitude=54.522, longitude=8.655)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitrahmen für Kalender (heute + 13 Tage)
start_date = datetime.now(tz).date()
end_date = start_date + timedelta(days=13)

# Kalender vorbereiten
cal = Calendar()
cal.add("prodid", "-//Fotozeiten Westerhever//")
cal.add("version", "2.0")

def build_tide_lookup(tides_raw):
    """Organisiert rohe Gezeitendaten in ein dict mit Datum als Key"""
    tide_by_date = {}
    for tide in tides_raw:
        dt = datetime.fromtimestamp(tide["dt"], tz=pytz.utc).astimezone(tz)
        date = dt.date()
        if date not in tide_by_date:
            tide_by_date[date] = []
        tide_by_date[date].append((tide["type"], dt))
    return tide_by_date

def get_weather_alerts(lat, lon, api_key):
    """Wetterwarnungen von OpenWeatherMap abrufen (auf Deutsch)"""
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "exclude": "current,minutely,hourly,daily",
        "lang": "de"  # Sprache Deutsch
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

            # Goldene Stunde ermitteln (morgens Ende = Sonnenaufgang + 60 Min, abends Start = golden_hour 'sunset')
            gh = golden_hour(observer, date=current_date, tzinfo=tz)
            golden_morning_end = s['sunrise'] + timedelta(minutes=60)  # Ende morgens
            golden_evening_start = gh['sunset']  # Start abends

            # Gezeiten für den Tag
            tides = tide_by_date.get(current_date, [])
            ebb_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'Low']
            flood_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'High']

            ebb_line = f"⛱️ Ebbe: {' / '.join(ebb_times)}" if ebb_times else ""
            flood_line = f"🌊 Flut: {' / '.join(flood_times)}" if flood_times else ""

            # Beschreibungstext zusammensetzen
            beschreibung = "\n".join(filter(None, [
                f"🌅 SA: {s['sunrise'].strftime('%H:%M')} / SU: {s['sunset'].strftime('%H:%M')}",
                f"🔵 BS: {dawn_start.strftime('%H:%M')} / {dusk_end.strftime('%H:%M')}",
                f"✨ GS: {golden_morning_end.strftime('%H:%M')} / {golden_evening_start.strftime('%H:%M')}",
                ebb_line,
                flood_line
            ]))

            # Ganztägiger Kalendereintrag mit eindeutiger UID für Apple Kalender
            event = Event()
            event.add("summary", "📋 Westerhever-Zeiten")
            event.add("dtstart", vDate(current_date))  # Nur Datum, keine Zeit
            event.add("dtend", vDate(current_date + timedelta(days=1)))  # exclusives Ende
            event.add("uid", f"{current_date.strftime('%Y%m%d')}-westerhever@fotozeiten.de")  # feste UID pro Tag
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            event.add("TRANSP", "TRANSPARENT")
            event.add("X-MICROSOFT-CDO-ALLDAYEVENT", "TRUE")
            cal.add_component(event)

        except Exception as e:
            print(f"⚠️ Fehler bei {current_date}: {e}")
        current_date += timedelta(days=1)

    # Wetterwarnung als separater Termin
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
    kalender_pfad = "docs/fotozeiten-westerhever.ics"
    with open(kalender_pfad, "wb") as f:
        f.write(cal.to_ical())

    print(f"📅 Kalender erstellt: {kalender_pfad}")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
