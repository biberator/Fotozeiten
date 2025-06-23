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

# Standort Rubjerg Knude, Dänemark (für ruhigen Morgen)
lat_rubjerg, lon_rubjerg = 57.4417, 9.7543
location_name_rubjerg = "Rubjerg Knude"

# Standort Rebild Bakker, Dänemark (für Regenserie)
lat_rebild, lon_rebild = 56.9167, 9.7167
location_name_rebild = "Rebild Bakker"

tz = pytz.timezone("Europe/Copenhagen")
ics_path = "docs/warnungen-dk.ics"

# Astral Standorte
location_rubjerg = LocationInfo(name=location_name_rubjerg, region="Denmark", timezone=tz.zone,
                               latitude=lat_rubjerg, longitude=lon_rubjerg)
location_rebild = LocationInfo(name=location_name_rebild, region="Denmark", timezone=tz.zone,
                              latitude=lat_rebild, longitude=lon_rebild)

# OpenWeatherMap API
API_KEY = os.getenv("OPENWEATHERMAP_API_KEY")

# Wetterwarnungen abrufen
def get_weather_alerts(lat, lon):
    url = "https://api.openweathermap.org/data/3.0/onecall"
    params = {
        "lat": lat,
        "lon": lon,
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

# Regenanalyse: 3+ Tage in Folge mit mindestens 2 Regen-Zeitblöcken pro Tag (für Rebild Bakker)
def detect_rain_series():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat_rebild,
        "lon": lon_rebild,
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

        rain_event = None
        if len(streak) >= 3:
            rain_event = (f"🌧️ Regenserie in Rebild Baker: {len(streak)} Tage ab {streak[0].strftime('%d.%m.')}", streak[0])

        return rain_event

    except Exception as e:
        print(f"⚠️ Fehler bei Regenanalyse: {e}")
        return None

# Sturm → ruhiger Morgen erkennen (bezogen auf Sonnenaufgang bei Rubjerg Knude)
def detect_calm_morning():
    url = "https://api.openweathermap.org/data/2.5/forecast"
    params = {
        "lat": lat_rubjerg,
        "lon": lon_rubjerg,
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
        days_sorted = sorted(wind_speed_by_day.keys())

        for day in days_sorted:
            speeds = [w for _, w in wind_speed_by_day[day]]
            avg = sum(speeds) / len(speeds)
            if avg > 10:
                next_day = day + timedelta(days=1)
                if next_day in wind_speed_by_day:
                    sunrise = sun(location_rubjerg.observer, date=next_day, tzinfo=tz)["sunrise"]
                    winds = wind_speed_by_day[next_day]
                    nearest = min(winds, key=lambda tup: abs((tup[0] - sunrise).total_seconds()))
                    if nearest[1] < 5:
                        calm_event = ("🌬️ Nach dem Sturm am Rubjerg Knude", next_day)
                        break

        return calm_event

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

    # Alte Ereignisse mit diesen UIDs löschen, um Doppelungen zu vermeiden
    cal.subcomponents = [
        c for c in cal.subcomponents
        if not (isinstance(c, Event) and c.get("uid") in ["regenserie@dk", "calmmorning@dk"])
    ]

    rain_event = detect_rain_series()
    if rain_event:
        summary, start = rain_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", start)
        event.add("dtend", start + timedelta(days=1))
        event.add("dtstamp", now)
        event.add("uid", "regenserie@dk")
        cal.add_component(event)

    calm_event = detect_calm_morning()
    if calm_event:
        summary, when = calm_event
        event = Event()
        event.add("summary", summary)
        event.add("dtstart", when)
        event.add("dtend", when + timedelta(hours=1))
        event.add("dtstamp", now)
        event.add("uid", "calmmorning@dk")
        cal.add_component(event)

    os.makedirs(os.path.dirname(ics_path), exist_ok=True)
    with open(ics_path, "wb") as f:
        f.write(cal.to_ical())

    print("✅ Kalender aktualisiert: warnungen-dk.ics")

if __name__ == "__main__":
    update_calendar()
