import requests
from datetime import date

# Coordenadas de Nueva Imperial
latitude = -38.74451
longitude = -72.95025

# URL de la API
url = "https://api.open-meteo.com/v1/forecast"

# Parámetros de consulta
params = {
    "latitude": latitude,
    "longitude": longitude,
    "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
    "current_weather": "true",
    "timezone": "America/Santiago"
}

# Hacemos la petición
response = requests.get(url, params=params)
data = response.json()

# Fecha de hoy
hoy = str(date.today())

# Buscamos la posición de la fecha de hoy en la respuesta
if hoy in data["daily"]["time"]:
    idx = data["daily"]["time"].index(hoy)
    tmax = data["daily"]["temperature_2m_max"][idx]
    tmin = data["daily"]["temperature_2m_min"][idx]
    lluvia = data["daily"]["precipitation_sum"][idx]

    print(f"Clima en Nueva Imperial para hoy ({hoy}):")
    print(f"🌡️ Máxima: {tmax} °C")
    print(f"🌡️ Mínima: {tmin} °C")
    print(f"🌧️ Precipitación: {lluvia} mm")
	
else:
    print("No hay datos disponibles para hoy.")
