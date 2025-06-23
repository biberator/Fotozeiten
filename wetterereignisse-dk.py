# -*- coding: utf-8 -*-
import os
import pytz
import requests
from datetime import datetime, timedelta
from icalendar import Calendar, Event
from dotenv import load_dotenv
from astral import LocationInfo
from astral.sun import sun

# .env laden
load_dotenv()

# Pfad zur Kalenderdatei
ics_path = "docs/warnungen-dk.ics"

# Zeitzone
tz = pytz.timezone("Europe/Copenhagen")

# API-Key laden
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

# Koordinaten der beiden Orte
REBILD = {"name": "Rebild Baker", "lat": 56.7930, "lon": 9.8431}
RUBJERG = {"name": "Rubjerg Knude", "lat": 57.4417, "lon": 9.7543}

# Wetterwarnungen abrufen
def get_weather_alerts():
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": RUBJERG["lat"],
        "lon": RUBJERG["lon"],
        "appid": API_KEY,
        "units": "metric",
        "exclude": "current,minutely,hourly,daily"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()
        alerts = data.get("alerts", [])
        return [
            f"{alert.get('event', 'Warnung')}: {alert.get('description', '')}"
            for alert in alerts
        ]
    except Exception as e:
        print(f"⚠️ Fehler bei Wetterwarnung: {e}")
        return []

# Regenserie (nur Rebild)
def detect_rain_series():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": REBILD["lat"],
        "lon": REBILD["lon"],
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        rain_counts = {}
        for entry in data["list"]:
            dt = datetime.utcfromtimestamp(entry["dt"]).astimezone(tz)
            day = dt.date()
            rain = entry.get("rain", {}).get("3h", 0)
            if rain > 0:
                rain_counts[day] = rain_counts.get(day, 0) + 1

        # Regenserie erkennen
        valid_days = sorted([d for d, count in rain_counts.items() if count >= 2])
        streak = []
        for day in valid_days:
            if not streak or day == streak[-1] + timedelta(days=1):
                streak.append(day)
            else:
                if len(streak) >= 3:
                    break
                streak = [day]

        if len(streak) >= 3:
            return ("🌧️ Regenserie in Rebild Baker", streak[0])
        return None
    except Exception as e:
        print(f"⚠️ Fehler bei Regenanalyse: {e}")
        return None

# Ruhiger Morgen nach Sturm (nur Rubjerg)
def detect_calm_after_storm():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": RUBJERG["lat"],
        "lon": RUBJERG["lon"],
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        wind_by_day = {}
        for entry in data["list"]:
            dt = datetime.utcfromtimestamp(entry["dt"]).astimezone(tz)
            day = dt.date()
            wind = entry.get("wind", {}).get("speed", 0)
            wind_by_day.setdefault(day, []).append((dt, wind))

        for day in sorted(wind_by_day.keys()):
            speeds = [w for _, w in wind_by_day[day]]
            avg = sum(speeds) / len(speeds)
            if avg > 10:
                next_day = day + timedelta(days=1)
                if next_day in wind_by_day:
                    location = LocationInfo(RUBJERG["name"], "Denmark", tz.zone,
                                            RUBJERG["lat"], RUBJERG["lon"])
                    sunrise = sun(location.observer, date=next_day, tzinfo=tz)["sunrise"]
                    winds = wind_by_day[next_day]
                    nearest = min(winds, key=lambda tup: abs((tup[0] - sunrise).total_seconds()))
                    if nearest[1] < 5:
                        return ("🌬️ Nach dem Sturm am Rubjerg Knude", next_day)
        return None
    except Exception as e:
        print(f"⚠️ Fehler bei Windanalyse: {e}")
        return None

# Kalender aktualisieren
def update_calendar():
    cal = Calendar()
    if os.path.exists(ics_path):
        with open(ics_path, "rb") as f:
            cal = Calendar.from_ical(f.read())

    now = datetime.now(tz)
    cal.subcomponents = [
        c for c in cal.subcomponents
        if not (isinstance(c, Event) and c.get("uid") in [
            "wetterwarnung@dk", "regenserie@dk", "calmmorning@dk"
        ])
    ]

    alerts = get_weather_alerts()
    if alerts:
        event = Event()
        event.add("summary", "⚠️ Wetterwarnungen")
        event.add("description", "\n\n".join(alerts))
        event.add("dtstart", now)
        event.add("dtend", now + timedelta(hours=1))
        event.add("dtstamp", now)
        event.add("uid", "wetterwarnung@dk")
        cal.add_component(event)

    rain_event = detect_rain_series()
    if rain_event:
        summary, date = rain_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", date)
        event.add("dtend", date + timedelta(days=1))
        event.add("dtstamp", now)
        event.add("uid", "regenserie@dk")
        cal.add_component(event)

    calm_event = detect_calm_after_storm()
    if calm_event:
        summary, date = calm_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", date)
        event.add("dtend", date + timedelta(hours=1))
        event.add("dtstamp", now)
        event.add("uid", "calmmorning@dk")
        cal.add_component(event)

    os.makedirs(os.path.dirname(ics_path), exist_ok=True)
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())
    print("✅ Kalender aktualisiert:", ics_path)

# Ausführen
if __name__ == "__main__":
    update_calendar()
