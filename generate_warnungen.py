import requests
from icalendar import Calendar, Event
from datetime import datetime, timedelta
import pytz

# Koordinaten Rubjerg Knude und Rebild Baker
LOCATIONS = {
    "Rubjerg Knude": {"lat": 57.462, "lon": 9.853},
    "Rebild Baker": {"lat": 56.916, "lon": 9.849},
}

# Wetter-API Open-Meteo: Stündliche Daten für Wind und Regen
API_URL = "https://api.open-meteo.com/v1/forecast"

# Sturm-Schwelle in km/h
STURM_WIND_GRENZE = 100

# Regen-Schwelle: mindestens 50% Regenstunden pro Tag
REGEN_PROZENT_GRENZE = 0.5

def fetch_weather(lat, lon):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m,precipitation",
        "timezone": "Europe/Copenhagen",
        "start": datetime.utcnow().date().isoformat(),
        "forecast_days": 7,
    }
    resp = requests.get(API_URL, params=params)
    resp.raise_for_status()
    return resp.json()

def sturmwarnung(daten):
    morgen = (datetime.utcnow() + timedelta(days=1)).date()
    hourly_time = daten["hourly"]["time"]
    hourly_wind = daten["hourly"]["windspeed_10m"]

    wind_morgen = [hourly_wind[i] for i, t in enumerate(hourly_time) if t.startswith(str(morgen))]

    max_wind = max(wind_morgen) if wind_morgen else 0

    if max_wind >= STURM_WIND_GRENZE:
        return max_wind
    return None

def regenwarnung(daten):
    heute = datetime.utcnow().date()
    hourly_time = daten["hourly"]["time"]
    hourly_precip = daten["hourly"]["precipitation"]

    regen_tage = []
    for tag_offset in range(7):
        tag = heute + timedelta(days=tag_offset)
        regenstunden = [hourly_precip[i] for i, t in enumerate(hourly_time) if t.startswith(str(tag))]
        if not regenstunden:
            break
        regenstunden_mit_regen = sum(1 for r in regenstunden if r > 0)
        if regenstunden_mit_regen / len(regenstunden) >= REGEN_PROZENT_GRENZE:
            regen_tage.append(tag)
        else:
            break
    return len(regen_tage)

def erstelle_ical_events(sturm_wind, regen_tage):
    cal = Calendar()
    cal.add('prodid', '-//Wetterwarnungen Fotozeiten//')
    cal.add('version', '2.0')

    tz = pytz.timezone("Europe/Copenhagen")
    heute = datetime.now(tz).date()

    if sturm_wind:
        event = Event()
        event.add('summary', f'Sturmwarnung Rubjerg Knude: {int(sturm_wind)} km/h')
        event.add('dtstart', heute)
        event.add('dtend', heute + timedelta(days=1))
        event.add('description', f'Morgen wird Sturm mit {int(sturm_wind)} km/h erwartet.')
        cal.add_component(event)

    if regen_tage >= 3:
        event = Event()
        event.add('summary', f'{regen_tage} Tage Regen in Rebild Baker')
        event.add('dtstart', heute)
        event.add('dtend', heute + timedelta(days=1))
        event.add('description', f'Seit {regen_tage} Tagen durchgehend Regen vorhergesagt.')
        cal.add_component(event)

    return cal.to_ical()

def main():
    try:
        rubjerg_data = fetch_weather(**LOCATIONS["Rubjerg Knude"])
        rebild_data = fetch_weather(**LOCATIONS["Rebild Baker"])

        sturm = sturmwarnung(rubjerg_data)
        regen = regenwarnung(rebild_data)

        ical_data = erstelle_ical_events(sturm, regen)

        with open("warnungen-dk.ics", "wb") as f:
            f.write(ical_data)

    except Exception as e:
        print(f"Fehler bei der Wetterwarnung: {e}")

if __name__ == "__main__":
    main()