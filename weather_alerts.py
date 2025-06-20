import requests

def get_weather_data(lat, lon, api_key):
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lon,
        "appid": api_key,
        "units": "metric"
    }
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

def check_sturmflut(lat, lon, api_key):
    data = get_weather_data(lat, lon, api_key)

    warning_msgs = []

    alerts = data.get("alerts", [])
    if alerts:
        for alert in alerts:
            event = alert.get("event", "Warnung")
            description = alert.get("description", "")
            warning_msgs.append(f"{event}: {description}")

    if warning_msgs:
        return " | ".join(warning_msgs)
    return None
