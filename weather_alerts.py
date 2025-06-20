import os
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

    wind_speed = data.get("wind", {}).get("speed", 0)  # m/s
    wind_kmh = wind_speed * 3.6
    pressure = data.get("main", {}).get("pressure", 1013)  # hPa

    warning_msgs = []

    if wind_kmh >= 70:
        warning_msgs.append(f"Sturmwarnung: starker Wind ({wind_kmh:.1f} km/h)")

    if pressure <= 1000:
        warning_msgs.append(f"Niedriger Luftdruck ({pressure} hPa)")

    if warning_msgs:
        return " | ".join(warning_msgs)
    return None
