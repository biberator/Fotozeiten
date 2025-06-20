# wetterwarnung.py
import os
import pytz
from datetime import datetime
from icalendar import Calendar, Event
from dotenv import load_dotenv
import requests

load_dotenv()

tz = pytz.timezone("Europe/Berlin")

# Standort Westerhever
lat = 54.3726
lon = 8.6489

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

def write_weather_ics(alerts):
    cal = Calendar()
    cal.add("prodid", "-//Wetterwarnung Westerhever//")
    cal.add("version", "2.0")

    now = datetime.now(tz)
    for msg in alerts:
        event = Event()
        event.add("summary", f"⚠️ Wetterwarnung: {msg}")
        event.add("dtstart", now)
        event.add("dtend", now)
        event.add("dtstamp", now)
        cal.add_component(event)

    os.makedirs("docs", exist_ok=True)
    with open("docs/fotozeiten-westerhever.ics", "wb") as f:
        f.write(cal.to_ical())
    print("✅ Wetterwarnung in Kalenderdatei gespeichert.")

if __name__ == "__main__":
    api_key = os.getenv("OPENWEATHERMAP_API_KEY")
    if api_key:
        alerts = get_weather_alerts(lat, lon, api_key)
        if alerts:
            write_weather_ics(alerts)
        else:
            print("ℹ️ Keine Wetterwarnungen.")
    else:
        print("❌ OPENWEATHERMAP_API_KEY nicht gesetzt.")
