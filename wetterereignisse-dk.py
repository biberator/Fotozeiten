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

# Pfad zum Kalender
ics_path = "doc/wettereignisse-dk.ics"

# Zeitzone
tz = pytz.timezone("Europe/Copenhagen")

# Standorte
# Rebild Baker für Regenserie
rebild_lat, rebild_lon = 56.8961, 9.9260
rebild_name = "Rebild Baker"

# Rubjerg Knude für Sturm-Morgen
rubjerg_lat, rubjerg_lon = 57.4417, 9.7543
rubjerg_name = "Rubjerg Knude"

# Astral Standort für Rubjerg Knude (Sonnenaufgang)
rubjerg_location = LocationInfo(name=rubjerg_name, region="Denmark", timezone=tz.zone,
                               latitude=rubjerg_lat, longitude=rubjerg_lon)

# API-Key aus .env
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

# Wetterwarnungen abrufen
def get_weather_alerts():
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": rubjerg_lat,
        "lon": rubjerg_lon,
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

# Regenserie in Rebild Baker (3+ Tage mit je mind. 2 Regenblöcken)
def detect_rain_series():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": rebild_lat,
        "lon": rebild_lon,
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
            return (f"🌧️ {len(streak)} Tage Regen in {rebild_name} ab {streak[0].strftime('%d.%m.')}", streak[0])

        return None
    except Exception as e:
        print(f"⚠️ Fehler bei Regenserie: {e}")
        return None

# Ruhiger Morgen nach Sturm in Rubjerg Knude (Wind >10km/h heute, <5km/h zum Sonnenaufgang morgen)
def detect_calm_morning():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": rubjerg_lat,
        "lon": rubjerg_lon,
        "appid": API_KEY,
        "units": "metric"
    }
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        wind_speed_by_day = {}

        for entry in data["list"]:
            dt = datetime.utcfromtimestamp(entry["dt"]).astimezone(tz)
            day = dt.date()
            wind = entry.get("wind", {}).get("speed", 0)
            wind_speed_by_day.setdefault(day, []).append((dt, wind))

        calm_event = None
        for day in sorted(wind_speed_by_day.keys()):
            speeds = [w for _, w in wind_speed_by_day[day]]
            avg = sum(speeds) / len(speeds)
            if avg > 10:
                next_day = day + timedelta(days=1)
                if next_day in wind_speed_by_day:
                    sunrise = sun(rubjerg_location.observer, date=next_day, tzinfo=tz)["sunrise"]
                    winds = wind_speed_by_day[next_day]
                    nearest = min(winds, key=lambda tup: abs((tup[0] - sunrise).total_seconds()))
                    if nearest[1] < 5:
                        calm_event = ("🌬️ Ruhiger Morgen nach Sturm am Rubjerg Knude", next_day)
                        break

        return calm_event
    except Exception as e:
        print(f"⚠️ Fehler bei ruhigem Morgen: {e}")
        return None

# Kalender aktualisieren
def update_calendar():
    cal = Calendar()
    if os.path.exists(ics_path):
        with open(ics_path, "rb") as f:
            cal = Calendar.from_ical(f.read())

    now = datetime.now(tz)

    # Alte Events entfernen
    cal.subcomponents = [
        c for c in cal.subcomponents
        if not (c.name == "VEVENT" and c.get("uid") in ["wetterwarnung@dk", "regenserie@rebild", "calmmorning@rubjerg"])
    ]

    # Wetterwarnungen
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

    # Regenserie Rebild Baker
    rain_event = detect_rain_series()
    if rain_event:
        summary, start = rain_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(days=1))
        event.add("dtstamp", now)
        event.add("uid", "regenserie@rebild")
        cal.add_component(event)

    # Ruhiger Morgen nach Sturm Rubjerg Knude
    calm_event = detect_calm_morning()
    if calm_event:
        summary, start = calm_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(hours=1))
        event.add("dtstamp", now)
        event.add("uid", "calmmorning@rubjerg")
        cal.add_component(event)

    # Ordner erstellen & speichern
    os.makedirs(os.path.dirname(ics_path), exist_ok=True)
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())

    print(f"✅ Kalender aktualisiert: {ics_path}")

if __name__ == "__main__":
    update_calendar()
