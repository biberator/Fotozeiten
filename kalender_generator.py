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

def build_tide_lookup(tides_raw):
    tide_by_date = {}
    for tide in tides_raw:
        dt = datetime.fromtimestamp(tide["dt"], tz=pytz.utc).astimezone(tz)
        date = dt.date()
        if date not in tide_by_date:
            tide_by_date[date] = []
        tide_by_date[date].append((tide["type"], dt))
    return tide_by_date

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

            # GS Startzeiten
            gs_morning = s["sunrise"]
            gs_evening = s["sunset"] - timedelta(hours=1)

            # BS Startzeiten
            bs_morning = dawn_start
            bs_evening = s["sunset"]

            # Gezeiten (sortiert & gruppiert)
            tides = tide_by_date.get(current_date, [])
            ebbe = [t[1].strftime('%H:%M') for t in tides if t[0] == 'Low']
            flut = [t[1].strftime('%H:%M') for t in tides if t[0] == 'High']

            # Beschreibung bauen
            beschreibung = "\n".join([
                f"🌅 SA: {s['sunrise'].strftime('%H:%M')}",
                f"🌇 SU: {s['sunset'].strftime('%H:%M')}",
                f"🔵 BS: {bs_morning.strftime('%H:%M')} / {bs_evening.strftime('%H:%M')}",
                f"✨ GS: {gs_morning.strftime('%H:%M')} / {gs_evening.strftime('%H:%M')}",
                f"🌊 Ebbe: {' / '.join(ebbe)}" if ebbe else "",
                f"🌊 Flut: {' / '.join(flut)}" if flut else ""
            ]).strip()

            # Kalender-Eintrag hinzufügen
            event = Event()
            event.add("summary", "📍 Westerhever-Zeiten")
            event.add("dtstart", tz.localize(datetime.combine(current_date, datetime.min.time())))
            event.add("dtend", tz.localize(datetime.combine(current_date + timedelta(days=1), datetime.min.time())))
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            cal.add_component(event)

        except Exception as e:
            print(f"⚠️ Fehler bei {current_date}: {e}")
        current_date += timedelta(days=1)

    # Wetterwarnungen separat
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

    # Speichern
    os.makedirs("docs", exist_ok=True)
    with open("docs/fotozeiten-westerhever.ics", "wb") as f:
        f.write(cal.to_ical())

    print("📅 Kalender erstellt: docs/fotozeiten-westerhever.ics")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
