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

# .env laden
load_dotenv()

# Standort Pellworm für genauere Sonnenstände
tz = pytz.timezone("Europe/Berlin")
location = LocationInfo(name="Westerhever (Pegel: Pellworm)", region="Germany", timezone=tz.zone,
                        latitude=54.522, longitude=8.655)
observer = Observer(latitude=location.latitude, longitude=location.longitude)

# Zeitrahmen für Kalender (heute + 13 Tage)
start_date = datetime.now(tz).date()
end_date = start_date + timedelta(days=13)

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

def generate_calendar():
    cal = Calendar()
    cal.add("prodid", "-//Fotozeiten Westerhever//")
    cal.add("version", "2.0")

    # Wetterwarnungen laden
    owm_api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    weather_alerts = {}
    if owm_api_key:
        alerts = get_weather_alerts(location.latitude, location.longitude, owm_api_key)
        now = datetime.now(tz).date()
        if alerts:
            weather_alerts[now] = alerts

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

            if current_date in weather_alerts:
                beschreibungsteile.append("")
                beschreibungsteile.extend(weather_alerts[current_date])

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

    os.makedirs("docs", exist_ok=True)
    kalender_pfad = "docs/fotozeiten-westerhever.ics"
    with open(kalender_pfad, "wb") as f:
        f.write(cal.to_ical())

    print(f"📅 Kalender erstellt: {kalender_pfad}")
    print(f"✅ Gesamtzahl der Kalendereinträge: {len(cal.subcomponents)}")

if __name__ == "__main__":
    generate_calendar()
