# -*- coding: utf-8 -*-
import os
import pytz
import requests
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, dawn, dusk, golden_hour
from astral.location import Observer
from icalendar import Calendar, Event, vDate
from dotenv import load_dotenv
from tide_cache import get_tides  # Gezeitendaten mit Caching

# .env laden
load_dotenv()

# Standort Westerhever (Pellworm als Pegel)
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(name="Westerhever (Pegel: Pellworm)", region="Germany", timezone=tz.zone,
                        latitude=54.522, longitude=8.655)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitraum: heute + 13 Tage
start_date = datetime.now(tz).date()
end_date = start_date + timedelta(days=13)

def build_tide_lookup(tides_raw):
    """Ordnet Gezeiten nach Datum"""
    tide_by_date = {}
    for tide in tides_raw:
        dt = datetime.fromtimestamp(tide["dt"], tz=pytz.utc).astimezone(tz)
        date = dt.date()
        tide_by_date.setdefault(date, []).append((tide["type"], dt))
    return tide_by_date

def get_weather_alerts(lat, lon, api_key):
    """Wetterwarnungen von OpenWeather abrufen"""
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "exclude": "current,minutely,hourly,daily",
        "lang": "de"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        alerts = response.json().get("alerts", [])
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
    cal = Calendar()
    cal.add("prodid", "-//Fotozeiten Westerhever//")
    cal.add("version", "2.0")

    tide_data = get_tides()
    tides_raw = tide_data.get("extremes", [])
    tide_by_date = build_tide_lookup(tides_raw)

    current_date = start_date
    while current_date <= end_date:
        try:
            s = sun(observer, date=current_date, tzinfo=tz)
            dawn_start = dawn(observer, date=current_date, tzinfo=tz)
            dusk_end = dusk(observer, date=current_date, tzinfo=tz)
            gh = golden_hour(observer, date=current_date, tzinfo=tz)
            golden_morning_end = s["sunrise"] + timedelta(minutes=60)
            golden_evening_start = gh["sunset"]

            tides = tide_by_date.get(current_date, [])
            ebb_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'Low']
            flood_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'High']

            beschreibung = "\n".join(filter(None, [
                f"🌅 SA: {s['sunrise'].strftime('%H:%M')} / SU: {s['sunset'].strftime('%H:%M')}",
                f"🔵 BS: {dawn_start.strftime('%H:%M')} / {dusk_end.strftime('%H:%M')}",
                f"✨ GS: {golden_morning_end.strftime('%H:%M')} / {golden_evening_start.strftime('%H:%M')}",
                f"⛱️ Ebbe: {' / '.join(ebb_times)}" if ebb_times else "",
                f"🌊 Flut: {' / '.join(flood_times)}" if flood_times else ""
            ]))

            event = Event()
            event.add("summary", "📋 Westerhever-Zeiten")
            event.add("dtstart", current_date)
            event["dtstart"].params["VALUE"] = "DATE"
            event.add("dtend", current_date + timedelta(days=1))
            event["dtend"].params["VALUE"] = "DATE"
            event.add("uid", f"{current_date.strftime('%Y%m%d')}-westerhever@fotozeiten.de")
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            event.add("TRANSP", "TRANSPARENT")
            event.add("X-MICROSOFT-CDO-ALLDAYEVENT", "TRUE")
            cal.add_component(event)

            print(f"✔️ Event für {current_date} hinzugefügt.")

        except Exception as e:
            print(f"❌ Fehler bei {current_date}: {e}")
        current_date += timedelta(days=1)

    # Wetterwarnung als eigener Eintrag
    owm_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if owm_api_key:
        alerts = get_weather_alerts(location.latitude, location.longitude, owm_api_key)
        if alerts:
            beschreibung = "\n\n".join(alerts)
            now = datetime.now(tz)
            event = Event()
            event.add("summary", "⚠️ Wetterwarnung")
            event.add("dtstart", now)
            event.add("dtend", now + timedelta(hours=1))
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", beschreibung)
            cal.add_component(event)

    os.makedirs("docs", exist_ok=True)
    pfad = "docs/fotozeiten-westerhever.ics"
    with open(pfad, "wb") as f:
        f.write(cal.to_ical())

    print(f"📅 Kalender gespeichert: {pfad}")
    print(f"📌 Ereignisse insgesamt: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
