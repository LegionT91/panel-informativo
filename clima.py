import requests
from datetime import date

def obtener_clima_nueva_imperial():
    """
    Obtiene los datos del clima actual para Nueva Imperial
    Retorna un diccionario con la información del clima
    """
    try:
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

        # Datos del clima actual
        current_weather = data.get("current_weather", {})
        temperatura_actual = current_weather.get("temperature", 0)
        codigo_clima = current_weather.get("weathercode", 0)

        # Buscamos la posición de la fecha de hoy en la respuesta
        clima_info = {
            "temperatura_actual": temperatura_actual,
            "codigo_clima": codigo_clima,
            "icono_bootstrap": obtener_icono_bootstrap(codigo_clima),
            "descripcion": obtener_descripcion_clima(codigo_clima),
            "fecha": hoy
        }

        if hoy in data["daily"]["time"]:
            idx = data["daily"]["time"].index(hoy)
            clima_info.update({
                "temperatura_max": data["daily"]["temperature_2m_max"][idx],
                "temperatura_min": data["daily"]["temperature_2m_min"][idx],
                "precipitacion": data["daily"]["precipitation_sum"][idx]
            })

        return clima_info

    except Exception as e:
        # En caso de error, retornar valores por defecto
        return {
            "temperatura_actual": 15,
            "codigo_clima": 0,
            "icono_bootstrap": "bi-sun",
            "descripcion": "Soleado",
            "fecha": str(date.today()),
            "temperatura_max": 20,
            "temperatura_min": 10,
            "precipitacion": 0
        }

def obtener_icono_bootstrap(codigo_clima):
    """
    Convierte el código del clima de Open-Meteo a iconos de Bootstrap Icons
    """
    # Mapeo de códigos de clima a iconos de Bootstrap
    iconos_clima = {
        0: "bi-sun",           # Cielo despejado
        1: "bi-sun",           # Principalmente despejado
        2: "bi-cloud-sun",     # Parcialmente nublado
        3: "bi-clouds",        # Nublado
        45: "bi-cloud-fog",    # Niebla
        48: "bi-cloud-fog",    # Niebla con escarcha
        51: "bi-cloud-drizzle", # Llovizna ligera
        53: "bi-cloud-drizzle", # Llovizna moderada
        55: "bi-cloud-drizzle", # Llovizna densa
        56: "bi-cloud-sleet",   # Llovizna helada ligera
        57: "bi-cloud-sleet",   # Llovizna helada densa
        61: "bi-cloud-rain",    # Lluvia ligera
        63: "bi-cloud-rain",    # Lluvia moderada
        65: "bi-cloud-rain-heavy", # Lluvia intensa
        66: "bi-cloud-sleet",   # Lluvia helada ligera
        67: "bi-cloud-sleet",   # Lluvia helada intensa
        71: "bi-cloud-snow",    # Nieve ligera
        73: "bi-cloud-snow",    # Nieve moderada
        75: "bi-cloud-snow",    # Nieve intensa
        77: "bi-snow",          # Granizo de nieve
        80: "bi-cloud-rain",    # Chubascos ligeros
        81: "bi-cloud-rain",    # Chubascos moderados
        82: "bi-cloud-rain-heavy", # Chubascos violentos
        85: "bi-cloud-snow",    # Chubascos de nieve ligeros
        86: "bi-cloud-snow",    # Chubascos de nieve intensos
        95: "bi-cloud-lightning-rain", # Tormenta
        96: "bi-cloud-lightning-rain", # Tormenta con granizo ligero
        99: "bi-cloud-lightning-rain"  # Tormenta con granizo intenso
    }
    
    return iconos_clima.get(codigo_clima, "bi-sun")

def obtener_descripcion_clima(codigo_clima):
    """
    Convierte el código del clima a una descripción en español
    """
    descripciones = {
        0: "Despejado",
        1: "Principalmente despejado",
        2: "Parcialmente nublado",
        3: "Nublado",
        45: "Niebla",
        48: "Niebla con escarcha",
        51: "Llovizna ligera",
        53: "Llovizna moderada",
        55: "Llovizna densa",
        56: "Llovizna helada ligera",
        57: "Llovizna helada densa",
        61: "Lluvia ligera",
        63: "Lluvia moderada",
        65: "Lluvia intensa",
        66: "Lluvia helada ligera",
        67: "Lluvia helada intensa",
        71: "Nieve ligera",
        73: "Nieve moderada",
        75: "Nieve intensa",
        77: "Granizo de nieve",
        80: "Chubascos ligeros",
        81: "Chubascos moderados",
        82: "Chubascos violentos",
        85: "Chubascos de nieve ligeros",
        86: "Chubascos de nieve intensos",
        95: "Tormenta",
        96: "Tormenta con granizo ligero",
        99: "Tormenta con granizo intenso"
    }
    
    return descripciones.get(codigo_clima, "Soleado")

# Para mantener compatibilidad con el código existente
if __name__ == "__main__":
    clima = obtener_clima_nueva_imperial()
    print(f"Clima en Nueva Imperial para hoy ({clima['fecha']}):")
    print(f"🌡️ Temperatura actual: {clima['temperatura_actual']} °C")
    if 'temperatura_max' in clima:
        print(f"🌡️ Máxima: {clima['temperatura_max']} °C")
        print(f"🌡️ Mínima: {clima['temperatura_min']} °C")
        print(f"🌧️ Precipitación: {clima['precipitacion']} mm")
    print(f"☀️ Condición: {clima['descripcion']}")
    print(f"🎨 Icono: {clima['icono_bootstrap']}")