# -*- coding: utf-8 -*-
import os
import pytz
import requests
from datetime import datetime, timedelta
from astral import LocationInfo
from astral.sun import sun, dawn, dusk
from astral.location import Observer
from icalendar import Calendar, Event, vDate
from dotenv import load_dotenv
from tide_cache import get_tides  # 🌊 Gezeitendaten werden benötigt

# .env laden
load_dotenv()

# Standort Pellworm für genauere Sonnenstände
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(name="Westerhever (Pegel: Pellworm)", region="Germany", timezone=tz.zone,
                        latitude=54.522, longitude=8.655)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitrahmen für Kalender: rückwirkend 14 Tage + 14 Tage in die Zukunft
start_date = (datetime.now(tz) - timedelta(days=14)).date()
end_date = (datetime.now(tz) + timedelta(days=14)).date()

def get_weather_alerts(lat, lon, api_key):
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
        data = response.json()
        alerts = data.get("alerts", [])
        messages = []
        for alert in alerts:
            event = alert.get("event", "Warnung")
            desc = alert.get("description", "")
            messages.append(f"⚠️ {event}: {desc.strip()}")
        return messages
    except Exception as e:
        print(f"⚠️ Fehler bei Wetterwarnung: {e}")
        return []

def get_extreme_alerts(lat, lon, api_key):
    """Liefert nur extreme Wetterwarnungen mit Zeitraum zurück"""
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric",
        "exclude": "current,minutely,hourly,daily",
        "lang": "en"
    }
    keyword_map = {
        "storm": "Sturm",
        "storm surge": "Sturmflut",
        "hurricane": "Hurrikan",
        "gale": "Sturmböen",
        "tornado": "Tornado",
        "extreme wind": "Extreme Winde",
    }
    extreme_keywords = keyword_map.keys()

    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        alerts = data.get("alerts", [])

        extreme_alerts = []

        for alert in alerts:
            event = alert.get("event", "").lower()
            desc = alert.get("description", "").lower()

            matched_keywords = [kw for kw in extreme_keywords if kw in event or kw in desc]

            if matched_keywords:
                first_kw = matched_keywords[0]
                title_de = keyword_map.get(first_kw, "Extreme Wetterwarnung")

                start_ts = alert.get("start")
                end_ts = alert.get("end")
                if start_ts and end_ts:
                    start = datetime.fromtimestamp(start_ts, tz=pytz.utc).astimezone(tz)
                    end = datetime.fromtimestamp(end_ts, tz=pytz.utc).astimezone(tz)
                    # max. 7 Tage Dauer
                    if (end - start) > timedelta(days=7):
                        end = start + timedelta(days=7)
                else:
                    start = datetime.now(tz)
                    end = start + timedelta(days=7)

                extreme_alerts.append({
                    "title": title_de,
                    "description": alert.get("description", "").strip(),
                    "start": start,
                    "end": end,
                })

        return extreme_alerts

    except Exception as e:
        print(f"⚠️ Fehler bei extremen Wetterwarnungen: {e}")
        return []

def build_tide_lookup(tides_raw):
    tide_by_date = {}
    for tide in tides_raw:
        dt = datetime.fromtimestamp(tide["dt"], tz=pytz.utc).astimezone(tz)
        date = dt.date()
        if date not in tide_by_date:
            tide_by_date[date] = []
        tide_by_date[date].append((tide["type"], dt))
    return tide_by_date

def generate_calendar():
    cal = Calendar()
    cal.add("prodid", "-//Fotozeiten Westerhever//")
    cal.add("version", "2.0")

    owm_api_key = os.getenv("OPENWEATHERMAP_API_KEY")

    # Tages-Events mit Zeiten, Ebbe/Flut
    try:
        tide_data = get_tides()
        tides_raw = tide_data.get("extremes", [])
        tide_by_date = build_tide_lookup(tides_raw)
        print(f"🌊 Gezeiten geladen: {len(tides_raw)} Einträge")
    except Exception as e:
        print(f"⚠️ Fehler beim Laden der Gezeiten: {e}")
        tide_by_date = {}

    current_date = start_date
    while current_date <= end_date:
        try:
            s = sun(observer, date=current_date, tzinfo=tz)
            dawn_start = dawn(observer, date=current_date, tzinfo=tz)
            dusk_end = dusk(observer, date=current_date, tzinfo=tz)

            golden_morning_end = s["sunrise"] + timedelta(minutes=60)
            golden_evening_start = s["sunset"] - timedelta(minutes=60)

            beschreibungsteile = [
                f"🌅 SA: {s['sunrise'].strftime('%H:%M')} / SU: {s['sunset'].strftime('%H:%M')}",
                f"🔵 BS: {dawn_start.strftime('%H:%M')} / {dusk_end.strftime('%H:%M')}",
                f"✨ GS: {golden_morning_end.strftime('%H:%M')} / {golden_evening_start.strftime('%H:%M')}"
            ]

            tides = tide_by_date.get(current_date, [])
            ebb_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'Low']
            flood_times = [t[1].strftime('%H:%M') for t in tides if t[0] == 'High']

            if ebb_times:
                beschreibungsteile.append(f"⛱️ Ebbe: {' / '.join(ebb_times)}")
            if flood_times:
                beschreibungsteile.append(f"🌊 Flut: {' / '.join(flood_times)}")

            event = Event()
            event.add("summary", "📋 Westerhever-Zeiten")
            event.add("dtstart", vDate(current_date))
            event.add("dtend", vDate(current_date + timedelta(days=1)))
            event.add("uid", f"{current_date.strftime('%Y%m%d')}-westerhever@fotozeiten.de")
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", "\n".join(beschreibungsteile))
            event.add("TRANSP", "TRANSPARENT")
            event.add("X-MICROSOFT-CDO-ALLDAYEVENT", "TRUE")
            cal.add_component(event)

            print(f"✔️ Tages-Event für {current_date} hinzugefügt.")
        except Exception as e:
            print(f"⚠️ Fehler bei {current_date}: {e}")

        current_date += timedelta(days=1)

    # Extreme Wetterwarnungen als separate Events (max. 7 Tage)
    if owm_api_key:
        extreme_alerts = get_extreme_alerts(location.latitude, location.longitude, owm_api_key)
        for alert in extreme_alerts:
            event = Event()
            event.add("summary", f"⚠️ {alert['title']}")
            event.add("dtstart", alert['start'])
            event.add("dtend", alert['end'])
            event.add("dtstamp", datetime.now(pytz.utc))
            event.add("description", alert['description'])
            event.add("uid", f"extreme-{alert['start'].strftime('%Y%m%d')}-{alert['title'].lower()}@fotozeiten.de")
            cal.add_component(event)
            print(f"⚠️ Extremwarnung hinzugefügt: {alert['title']} von {alert['start']} bis {alert['end']}")

    os.makedirs("docs", exist_ok=True)
    kalender_pfad = "docs/fotozeiten-westerhever.ics"
    with open(kalender_pfad, "wb") as f:
        f.write(cal.to_ical())

    print(f"📅 Kalender erstellt: {kalender_pfad}")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
