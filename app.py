# app.py
from fasthtml.common import *
import httpx
import math
from dataclasses import dataclass
from datetime import datetime, timedelta
import pytz # Added for timezone handling
import json # Import json for embedding data in JS
import asyncio

# --- Configuration ---
DEFAULT_LAT = 40.7128
DEFAULT_LON = -74.0060
WEATHER_API_URL = "https://api.open-meteo.com/v1/forecast"
AQI_API_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"

# --- Data Classes ---
@dataclass
class WeatherInputs:
    location: str = "New York, NY" # New field for text input
    min_temp: int = 67
    max_temp: int = 79
    min_rh: int = 30
    max_rh: int = 60
    latitude: float | None = None # Make optional or keep default? Let's make optional for now
    longitude: float | None = None # Make optional for now
    indoor_ref_temp: int = 69 # New user input field
    max_aqi: int = 50 # *** ADDED AQI Threshold ***
    max_precip_prob: int = 10 # Maximum precipitation probability (%)

@dataclass
class ForecastResult:
    periods: list[tuple[str, str]] # Overall Text list
    daily_chart_data: dict[str, list[tuple[datetime, bool, float | None, float | None, float | None, int | None, float | None]]]
    daily_good_intervals: dict[str, list[tuple[datetime, datetime]]]
    # *** ADDED BACK: Store formatted text list for display ***
    daily_good_periods_text: dict[str, list[str]]

# --- Helper Functions ---
def ftoc(f):
    if f is None: return None
    return (f - 32) * 5 / 9

def ctof(c):
     if c is None: return None
     return c * 9 / 5 + 32

def calculate_rh(temp_c, dew_point_c):
    """Calculate Relative Humidity (%) from Temperature (C) and Dew Point (C)."""
    if temp_c is None or dew_point_c is None:
        return None

    # Using Magnus formula constants (Sonntag90)
    a = 17.62
    b = 243.12

    # Saturation vapor pressure at the given temperature
    es = 6.112 * math.exp((a * temp_c) / (b + temp_c))

    # Actual vapor pressure at the given dew point
    e = 6.112 * math.exp((a * dew_point_c) / (b + dew_point_c))

    if es <= 0: # Avoid division by zero or invalid results
        return None

    rh = (e / es) * 100.0
    return min(max(rh, 0), 100) # Clamp RH between 0 and 100

# Removed calculate_dew_point_c and get_target_dew_point_range_c as they are no longer used directly

async def get_weather_forecast(lat: float, lon: float) -> dict | None:
    """Fetch 7-day hourly forecast data from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "temperature_2m,dew_point_2m,precipitation,precipitation_probability",
        "temperature_unit": "fahrenheit", # Request temps in F directly
        "forecast_days": 5,
        "timezone": "auto" # Detect timezone based on lat/lon
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(WEATHER_API_URL, params=params)
            response.raise_for_status() # Raise an exception for bad status codes
            return response.json()
        except httpx.RequestError as e:
            print(f"Error fetching weather data: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred fetching weather: {e}")
            return None

# *** RENAMED back to get_aqi_forecast and only requesting AQI ***
async def get_aqi_forecast(lat: float, lon: float) -> dict | None:
    """Fetch 7-day hourly AQI forecast data from Open-Meteo."""
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "us_aqi", # *** ONLY request us_aqi ***
        "forecast_days": 5,
        "timezone": "auto"
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(AQI_API_URL, params=params)
            response.raise_for_status()
            return response.json()
        except httpx.RequestError as e:
            print(f"Error fetching air quality data: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred fetching air quality: {e}")
            return None

async def get_address_from_coords(lat: float, lon: float) -> str | None:
    """Fetch approximate address from coordinates using Nominatim."""
    # Be respectful of Nominatim's usage policy: https://operations.osmfoundation.org/policies/nominatim/
    # Especially: Max 1 request/second, provide valid HTTP Referer or User-Agent.
    url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
    headers = {
        'User-Agent': 'OpenWindowAdvisorApp/1.0 (github.com/your_repo_if_public)' # Adjust as needed
    }
    async with httpx.AsyncClient() as client:
        try:
            await asyncio.sleep(1) # Add delay to comply with usage policy
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get('display_name')
        except httpx.TimeoutException:
            print("Error fetching address: Timeout")
            return "Timeout fetching address."
        except httpx.RequestError as e:
            print(f"Error fetching address: {e}")
            return f"Error fetching address: {e}"
        except Exception as e:
            print(f"An unexpected error occurred fetching address: {e}")
            return "Error fetching address."

async def get_coords_from_address(address: str) -> tuple[float, float] | None:
    """Fetch coordinates (latitude, longitude) from an address string using Nominatim."""
    # Be respectful of Nominatim's usage policy
    url = f"https://nominatim.openstreetmap.org/search?q={address}&format=json&limit=1"
    headers = {
        'User-Agent': 'OpenWindowAdvisorApp/1.0 (github.com/your_repo_if_public)' # Adjust as needed
    }
    async with httpx.AsyncClient() as client:
        try:
            await asyncio.sleep(1) # Add delay to comply with usage policy
            response = await client.get(url, headers=headers, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            if data and isinstance(data, list) and len(data) > 0:
                # Extract lat/lon from the first result
                lat = float(data[0].get('lat'))
                lon = float(data[0].get('lon'))
                return lat, lon
            else:
                print(f"Geocoding failed for address: {address} - No results found.")
                return None
        except httpx.TimeoutException:
            print(f"Geocoding error for address '{address}': Timeout")
            return None
        except httpx.RequestError as e:
            print(f"Geocoding error for address '{address}': {e}")
            return None
        except (ValueError, KeyError, IndexError) as e:
             print(f"Error parsing geocoding result for '{address}': {e}")
             return None
        except Exception as e:
            print(f"An unexpected error occurred during geocoding for '{address}': {e}")
            return None

def find_optimal_periods(weather_data: dict, aqi_data: dict | None, inputs: WeatherInputs) -> ForecastResult:
    """Identify periods and collect data, considering weather and AQI."""
    if not weather_data or 'hourly' not in weather_data or 'time' not in weather_data['hourly']:
         return ForecastResult(periods=[], info="Error: Could not parse weather data.", daily_chart_data={}, daily_good_intervals={}, daily_good_periods_text={})

    weather_hourly = weather_data['hourly']
    times = weather_hourly['time']
    temps_f = weather_hourly['temperature_2m']
    dew_points_f = weather_hourly['dew_point_2m']
    precip_mm = weather_hourly.get('precipitation', [0.0] * len(times))
    precip_prob = weather_hourly.get('precipitation_probability', [0.0] * len(times))

    aqi_values_dict = {}
    aq_available = False # Renamed from aqi_available for clarity
    if aqi_data and 'hourly' in aqi_data and 'time' in aqi_data['hourly']:
        aq_hourly = aqi_data['hourly']
        aq_times = aq_hourly['time']
        aqi_vals = aq_hourly.get('us_aqi')
        if aqi_vals is not None and len(aq_times) == len(aqi_vals):
            aq_available = True
            for i, time_str in enumerate(aq_times):
                aqi_values_dict[time_str] = aqi_vals[i]
        else:
            print("Warning: AQI data length mismatch or missing.")
    else:
        print("Warning: AQI data not available or invalid.")

    try:
        api_timezone_str = weather_data.get('timezone', 'UTC') # *** ADDED: Get timezone string for logging ***
        tz = pytz.timezone(api_timezone_str)
    except pytz.UnknownTimeZoneError:
        api_timezone_str = 'UTC (Fallback)' # *** ADDED: Update string if fallback used ***
        tz = pytz.utc
    indoor_ref_temp_c = ftoc(inputs.indoor_ref_temp)
    if indoor_ref_temp_c is None:
        return ForecastResult(periods=[], info="Error: Invalid indoor reference temperature.", daily_chart_data={}, daily_good_intervals={}, daily_good_periods_text={})

    # --- REMOVE Log Inputs --- 
    # print(f"--- Modal Log: find_optimal_periods Inputs ---")
    # print(f"Modal Log: {inputs}")
    # --- End Log Inputs ---

    overall_good_periods_text = []
    overall_start_time = None
    hourly_data_list = [] # (dt_local, is_good, temp_f, rh_in, precip, aqi)

    for i, time_str in enumerate(times):
        temp_out_f = temps_f[i]
        dew_point_out_f = dew_points_f[i]
        precip = precip_mm[i]
        precip_probability = precip_prob[i] if i < len(precip_prob) else 0.0
        aqi = aqi_values_dict.get(time_str)
        dt_utc = datetime.fromisoformat(time_str)
        dt_local = tz.localize(dt_utc)    # NEW: Localize the naive time using the API's timezone

        predicted_rh_in = None
        is_good = False
        temp_ok, rh_ok, precip_ok, precip_prob_ok, aqi_ok = False, False, False, False, False # Initialize checks
        primary_data_ok = (temp_out_f is not None and dew_point_out_f is not None and precip is not None)

        if primary_data_ok:
            dew_point_out_c = ftoc(dew_point_out_f)
            predicted_rh_in = calculate_rh(indoor_ref_temp_c, dew_point_out_c)
            temp_ok = inputs.min_temp <= temp_out_f <= inputs.max_temp
            if predicted_rh_in is not None: rh_ok = inputs.min_rh <= predicted_rh_in <= inputs.max_rh
            precip_ok = precip < 0.1
            precip_prob_ok = precip_probability <= inputs.max_precip_prob
            if aq_available: aqi_ok = (aqi is not None and aqi <= inputs.max_aqi)
            else: aqi_ok = True # Assume OK if AQI not available
            is_good = temp_ok and rh_ok and precip_ok and precip_prob_ok and aqi_ok
        
        # --- REMOVE Log Hourly Checks --- 
        # if dt_local.hour in [8, 9, 10, 18, 19, 20]:
        #     rh_str = f"{predicted_rh_in:.1f}" if predicted_rh_in is not None else "N/A"
        #     print(f"--- Modal Log: Hourly Check {dt_local} ---")
        #     print(f"  Input Checks: temp={temp_ok}, rh={rh_ok}, precip={precip_ok}, precip_prob={precip_prob_ok}, aqi={aqi_ok}")
        #     print(f"  Values: temp_out={temp_out_f:.1f}, pred_rh_in={rh_str}, precip={precip:.2f}, precip_prob={precip_probability:.1f}, aqi={aqi}")
        #     print(f"  Overall is_good: {is_good}")
        # --- End REMOVE Log Hourly Checks ---

        hourly_data_list.append((dt_local, is_good, temp_out_f, predicted_rh_in, precip, aqi, precip_probability))

        # Aggregate overall text periods
        if is_good and overall_start_time is None: overall_start_time = dt_local
        elif not is_good and overall_start_time is not None:
            end_time = dt_local
            # --- REMOVE Log times for string formatting ---
            # print(f"--- Log: Formatting overall period: start={overall_start_time}, end={end_time} ---")
            # --- End log REMOVAL ---
            start_fmt=overall_start_time.strftime('%a %I:%M %p'); end_fmt=end_time.strftime('%a %I:%M %p');
            if overall_start_time.date()==end_time.date(): end_fmt=end_time.strftime('%I:%M %p');
            overall_good_periods_text.append((start_fmt,end_fmt)); overall_start_time=None
    if overall_start_time is not None:
        end_time=(datetime.fromisoformat(times[-1]).astimezone(tz)+timedelta(hours=1))
        # --- REMOVE Log times for string formatting (end of forecast) ---
        # print(f"--- Log: Formatting overall period (end): start={overall_start_time}, end={end_time} ---")
        # --- End log REMOVAL ---
        start_fmt=overall_start_time.strftime('%a %I:%M %p'); end_fmt=end_time.strftime('%a %I:%M %p');
        if overall_start_time.date()==end_time.date(): end_fmt=end_time.strftime('%I:%M %p');
        overall_good_periods_text.append((start_fmt,end_fmt))

    # Group hourly data and calculate daily intervals/text
    daily_chart_data_map = {}
    daily_good_intervals_map = {}
    daily_good_periods_text_map = {}
    if hourly_data_list:
        current_day_str = hourly_data_list[0][0].strftime('%a %Y-%m-%d')
        daily_chart_data_map[current_day_str] = []
        daily_good_intervals_map[current_day_str] = []
        daily_good_periods_text_map[current_day_str] = []
        daily_start_dt = None
        last_dt_local = None
        for dt_local, is_good_status, temp_f, rh_in, p, aqi_val, precip_prob in hourly_data_list:
            day_str = dt_local.strftime('%a %Y-%m-%d')
            last_dt_local = dt_local
            if day_str not in daily_chart_data_map:
                if daily_start_dt is not None:
                    end_dt=dt_local; daily_good_intervals_map[current_day_str].append((daily_start_dt,end_dt));
                    prev_day_last_hour=dt_local-timedelta(hours=1); start_fmt=daily_start_dt.strftime('%I:%M %p'); end_fmt=(prev_day_last_hour+timedelta(hours=1)).strftime('%I:%M %p');
                    daily_good_periods_text_map[current_day_str].append(f"{start_fmt} - {end_fmt}"); daily_start_dt=None
                current_day_str=day_str; daily_chart_data_map[current_day_str]=[]; daily_good_intervals_map[current_day_str]=[]; daily_good_periods_text_map[current_day_str]=[]
            daily_chart_data_map[current_day_str].append((dt_local, is_good_status, temp_f, rh_in, p, aqi_val, precip_prob))
            if is_good_status and daily_start_dt is None: daily_start_dt=dt_local
            elif not is_good_status and daily_start_dt is not None:
                end_dt=dt_local; daily_good_intervals_map[current_day_str].append((daily_start_dt,end_dt));
                start_fmt=daily_start_dt.strftime('%I:%M %p'); end_fmt=end_dt.strftime('%I:%M %p');
                daily_good_periods_text_map[current_day_str].append(f"{start_fmt} - {end_fmt}"); daily_start_dt=None
        if daily_start_dt is not None and last_dt_local is not None:
            end_dt=last_dt_local+timedelta(hours=1); daily_good_intervals_map[current_day_str].append((daily_start_dt,end_dt));
            start_fmt=daily_start_dt.strftime('%I:%M %p'); end_fmt=end_dt.strftime('%I:%M %p');
            daily_good_periods_text_map[current_day_str].append(f"{start_fmt} - {end_fmt}")

    return ForecastResult(
        periods=overall_good_periods_text,
        daily_chart_data=daily_chart_data_map,
        daily_good_intervals=daily_good_intervals_map,
        daily_good_periods_text=daily_good_periods_text_map
    )

# --- Visualisation Helpers ---

def create_day_chart_script(day_str: str,
                            hourly_data: list[tuple[datetime, bool, float|None, float|None, float|None, int|None, float|None]], # Updated tuple
                            good_intervals: list[tuple[datetime, datetime]],
                            inputs: WeatherInputs) -> Script:
    chart_id = f"chart-div-{day_str.replace(' ', '-').replace('/', '-')}"
    hours = [dt.isoformat() for dt, _, _, _, _, _, _ in hourly_data]
    temps = [t for _, _, t, _, _, _, _ in hourly_data]
    rh_in = [rh for _, _, _, rh, _, _, _ in hourly_data]
    precip_prob = [p for _, _, _, _, _, _, p in hourly_data]
    
    hours_json = json.dumps(hours)
    temps_json = json.dumps(temps)
    rh_in_json = json.dumps(rh_in)
    precip_prob_json = json.dumps(precip_prob)
    
    shapes = [{"type": "rect", "xref": "x", "yref": "paper", "x0": s.isoformat(), "y0": 0, "x1": e.isoformat(), "y1": 1, "fillcolor": "rgba(147, 217, 147, 0.3)", "line": {"width": 0}} for s, e in good_intervals]
    shapes.append({"type": "line", "xref": "paper", "yref": "y1", "x0": 0, "y0": inputs.min_temp, "x1": 1, "y1": inputs.min_temp, "line": {"color": "#ff7f0e", "width": 1, "dash": "dash"}})
    shapes.append({"type": "line", "xref": "paper", "yref": "y1", "x0": 0, "y0": inputs.max_temp, "x1": 1, "y1": inputs.max_temp, "line": {"color": "#ff7f0e", "width": 1, "dash": "dash"}})
    shapes.append({"type": "line", "xref": "paper", "yref": "y2", "x0": 0, "y0": inputs.min_rh, "x1": 1, "y1": inputs.min_rh, "line": {"color": "#2ca02c", "width": 1, "dash": "dash"}})
    shapes.append({"type": "line", "xref": "paper", "yref": "y2", "x0": 0, "y0": inputs.max_rh, "x1": 1, "y1": inputs.max_rh, "line": {"color": "#2ca02c", "width": 1, "dash": "dash"}})
    shapes.append({"type": "line", "xref": "paper", "yref": "y3", "x0": 0, "y0": inputs.max_precip_prob, "x1": 1, "y1": inputs.max_precip_prob, "line": {"color": "#87ceeb", "width": 1, "dash": "dash"}})
    shapes_json = json.dumps(shapes)
    script_content = f"""
    try {{ 
        var trace_temp = {{ x: {hours_json}, y: {temps_json}, name: 'Outdoor Temp (°F)', type: 'scatter', mode: 'lines', yaxis: 'y1', line: {{ color: '#ff7f0e' }} }};
        var trace_rh = {{ x: {hours_json}, y: {rh_in_json}, name: 'Predicted Indoor RH (%)', type: 'scatter', mode: 'lines', yaxis: 'y2', line: {{ color: '#2ca02c' }} }};
        var trace_precip_prob = {{ x: {hours_json}, y: {precip_prob_json}, name: 'Precip Probability (%)', type: 'scatter', mode: 'lines', yaxis: 'y3', line: {{ color: '#87ceeb', width: 2 }} }};
        var layout = {{
            title: {{ text: '', font: {{size: 14}} }},
            xaxis: {{ type: 'date', tickformat: '%I:%M %p', tickangle: -45, showticklabels: false }}, 
            yaxis: {{ title: 'Temp (°F)', side: 'left', range: [40, 100], titlefont: {{ color: '#ff7f0e' }}, tickfont: {{ color: '#ff7f0e' }} }},
            yaxis2: {{ title: '%', titlefont: {{ color: '#2ca02c' }}, tickfont: {{ color: '#2ca02c' }}, overlaying: 'y', side: 'right', range: [0, 100] }},
            yaxis3: {{ title: '', titlefont: {{ color: '#87ceeb' }}, tickfont: {{ color: '#87ceeb' }}, overlaying: 'y', anchor: 'free', side: 'right', position: 0.85, range: [0, 100], showgrid: false, showticklabels: false }},
            margin: {{ l: 40, r: 40, t: 20, b: 0 }},
            legend: {{ x: 0.5, y: 1.1, xanchor: 'center', orientation: 'h' }},
            height: 300,
            shapes: {shapes_json}
        }};
        Plotly.newPlot('{chart_id}', [trace_temp, trace_rh, trace_precip_prob], layout, {{responsive: true}});
     }} catch (e) {{ console.error('Plotly error for {chart_id}:', e); var el=document.getElementById('{chart_id}'); if(el) el.innerHTML='Error.'; }}
    """
    return Script(script_content)

def create_precip_chart_script(day_str: str,
                               hourly_data: list[tuple[datetime, bool, float|None, float|None, float|None, int|None, float|None]]) -> Script: # Updated tuple
    chart_id = f"precip-chart-div-{day_str.replace(' ', '-').replace('/', '-')}"
    hours = [dt.isoformat() for dt, _, _, _, _, _, _ in hourly_data]
    precip = [p for _, _, _, _, p, _, _ in hourly_data]
    hours_json = json.dumps(hours); precip_json = json.dumps(precip)
    script_content = f"""
    try {{
        var trace_precip = {{ x: {hours_json}, y: {precip_json}, name: 'Precip (mm)', type: 'bar', marker: {{ color: '#87ceeb' }} }};
        var layout_precip = {{
            # *** Hide x-axis labels ***
            xaxis: {{ type: 'date', tickformat: '%I:%M %p', tickangle: -45, showticklabels: false }},
            yaxis: {{ title: 'Precip (mm)', range: [0, Math.max(...{precip_json}.filter(v => v !== null)) > 0 ? Math.max(...{precip_json}.filter(v => v !== null)) * 1.1 : 1] }},
            margin: {{ l: 40, r: 40, t: 5, b: 0 }}, # Remove bottom margin
            height: 100, showlegend: false
        }};
        Plotly.newPlot('{chart_id}', [trace_precip], layout_precip, {{responsive: true}});
    }} catch (e) {{ console.error('Plotly error for {chart_id}:', e); var el=document.getElementById('{chart_id}'); if(el) el.innerHTML='Error.'; }}
    """
    return Script(script_content)

def create_aqi_chart_script(day_str: str,
                            hourly_data: list[tuple[datetime, bool, float|None, float|None, float|None, int|None, float|None]],
                            max_aqi_threshold: int) -> Script:
    """Generates the Plotly Script tag for the AQI line chart."""
    chart_id = f"aqi-chart-div-{day_str.replace(' ', '-').replace('/', '-')}"
    hours = [dt.isoformat() for dt, _, _, _, _, _, _ in hourly_data]
    aqi = [a for _, _, _, _, _, a, _ in hourly_data]

    has_aqi_data = any(a is not None for a in aqi)

    hours_json = json.dumps(hours); aqi_json = json.dumps(aqi)
    aqi_shapes_json = json.dumps([{
        "type": "line", "xref": "paper", "yref": "y", "x0": 0, "y0": max_aqi_threshold,
        "x1": 1, "y1": max_aqi_threshold, "line": {"color": "red", "width": 1, "dash": "dash"}
    }]) if max_aqi_threshold is not None else '[]'

    script_content = f"""
    try {{
        var trace_aqi = {{ x: {hours_json}, y: {aqi_json}, name: 'US AQI', type: 'scatter', mode: 'lines', line: {{ color: 'purple' }} }};
        var layout_aqi = {{
            xaxis: {{ type: 'date', tickformat: '%I:%M %p', tickangle: -45, showticklabels: true }},
            yaxis: {{ title: 'US AQI', range: [0, Math.max(100, ...{aqi_json}.filter(v => v !== null && !isNaN(v))) * 1.1] }},
            margin: {{ l: 40, r: 40, t: 5, b: 60 }},
            height: 100, showlegend: false, shapes: {aqi_shapes_json}
        }};
        if ({str(has_aqi_data).lower()}) {{
             Plotly.newPlot('{chart_id}', [trace_aqi], layout_aqi, {{responsive: true}});
        }} else {{
             var el = document.getElementById('{chart_id}');
             if(el) el.innerHTML = '(AQI data not available)'; 
        }}
    }} catch (e) {{
        console.error('Plotly error for AQI chart {chart_id}:', e);
        var el = document.getElementById('{chart_id}');
        if(el) el.innerHTML = 'Error rendering AQI chart.';
    }}
    """
    return Script(script_content)

# --- FastHTML App ---

# *** Adjust CSS ***
styles = Style("""
.day-data-container { margin-bottom: 20px; border: 1px solid #ccc; padding: 15px; border-radius: 5px; background: #fff; }
.chart-container { margin-bottom: 0; min-height: 250px; }
.precip-chart-container { margin-top: 0; min-height: 100px; }
.aqi-chart-container { margin-top: 0; min-height: 100px; }
.error-message { color: red; font-weight: bold; }
.day-label { font-weight: bold; margin-bottom: 5px; font-size: 1.1em; color: #333; }
.daily-periods-list { font-size: 0.85em; margin-top: 8px; padding-left: 20px; color: #495057; list-style: disc; }
.daily-periods-list li { margin-bottom: 3px; }
""")

# Include Plotly library
plotly_hdr = Script(src="https://cdn.plot.ly/plotly-2.32.0.min.js")

# *** ADDED Monster UI Theme Setup ***
# theme = Theme.slate # Or choose another theme like stone, gray, etc.
# # Combine Monster UI headers with Plotly header
# monster_hdrs = theme.headers(daisy=True, highlightjs=False, katex=False) # Using DaisyUI, disable others for now
# combined_hdrs = monster_hdrs + (plotly_hdr,)


# *** Update fast_app call with combined headers ***
# app, rt = fast_app(hdrs=combined_hdrs)
app, rt = fast_app(hdrs=(styles, plotly_hdr)) # Reverted fast_app call

@rt("/")
async def get(inputs: WeatherInputs):
    # *** 1. Add Introductory Text ***
    intro_text = P(
        "This tool helps determine good times to open windows based on forecast conditions. "
        "It considers outdoor temperature, predicted indoor relative humidity (calculated for the reference indoor temperature), "
        "precipitation, and air quality index (AQI). "
        "Adjust the thresholds and location below and click 'Update Forecast'.",
        Cls="mb-4"
    )
    # *** Initialize lat/lon ***
    lat = inputs.latitude
    lon = inputs.longitude
    geocoding_error = None
    address_str = None # Initialize address string

    # *** Attempt Geocoding if location string is provided ***
    if inputs.location:
        coords = await get_coords_from_address(inputs.location)
        if coords:
            lat, lon = coords
            # Update inputs dataclass with derived coordinates for consistency
            inputs.latitude = lat
            inputs.longitude = lon
            # Fetch address string using the derived coordinates
            address_str = await get_address_from_coords(lat, lon)
        else:
            geocoding_error = f"Could not find coordinates for location: '{inputs.location}'. Please try a different query."
            # Reset lat/lon if geocoding failed
            lat, lon = None, None
    # *** Fallback: Use provided lat/lon if location string wasn't used or failed, and lat/lon are valid ***
    elif inputs.latitude is not None and inputs.longitude is not None and not (-90 <= inputs.latitude <= 90 and -180 <= inputs.longitude <= 180):
         # If only invalid lat/lon provided without location, treat as error
         geocoding_error = "Invalid Latitude/Longitude provided."
         lat, lon = None, None # Ensure we don't proceed with invalid coords
    elif inputs.latitude is not None and inputs.longitude is not None:
        # Valid lat/lon provided directly, use them
        lat = inputs.latitude
        lon = inputs.longitude
        address_str = await get_address_from_coords(lat, lon)
    else:
        # No location string and no valid coordinates - use default NYC
        lat, lon = DEFAULT_LAT, DEFAULT_LON
        inputs.latitude = lat
        inputs.longitude = lon
        inputs.location = "New York, NY" # Set default location string
        address_str = await get_address_from_coords(lat, lon)


    # *** Display Geocoding Error if any ***
    if geocoding_error:
        results_div = Div(P(geocoding_error), Cls="error-message", id="results")
        forecast_data = None # Prevent further processing
        aqi_data = None
    # *** Proceed only if we have valid coordinates ***
    elif lat is not None and lon is not None:
        # *** 2. Fetch Data (Weather, AQI) using derived/validated coordinates ***
        forecast_data = await get_weather_forecast(lat, lon)
        aqi_data = await get_aqi_forecast(lat, lon)
    else: # Should not happen if logic above is correct, but as a safeguard
        results_div = Div(P("Could not determine location coordinates."), id="results")
        forecast_data = None
        aqi_data = None

    # *** Display Address ***
    address_display = None
    if address_str:
        address_display = P(Strong("Approximate Location: "), address_str, Cls="mb-3")
    elif lat is not None and lon is not None and not geocoding_error: # If reverse lookup failed but we have coords
        address_display = P(Strong("Approximate Location: "), f"Lat: {lat:.4f}, Lon: {lon:.4f} (Address lookup failed)", Cls="mb-3 text-muted")
    elif not geocoding_error: # If geocoding failed initially
         address_display = P(Strong("Approximate Location: "), "Unknown (Geocoding failed)", Cls="mb-3 text-muted")
         # address_display might be None if geocoding_error is set, handled below

    # *** 3. Validate Other Inputs (Only if not already failed on geocoding) ***
    validation_error = None
    if not geocoding_error:
        if inputs.min_temp >= inputs.max_temp: validation_error = "Min temp >= max temp."
        elif inputs.min_rh >= inputs.max_rh: validation_error = "Min RH >= max RH."
        elif inputs.max_aqi < 0: validation_error = "Max AQI cannot be negative."
        # Lat/lon validation already handled during geocoding/initial check

    # *** 4. Process and Display Results (Skip if errors occurred) ***
    results_content_list = []
    if geocoding_error:
        # results_div already set above
        pass
    elif validation_error:
        results_div = Div(P(f"Input Error: {validation_error}"), Cls="error-message", id="results")
    elif forecast_data is None:
        results_div = Div(P("Error fetching weather forecast data."), id="results")
    else:
        # Ensure we pass the potentially updated 'inputs' (with derived lat/lon)
        result = find_optimal_periods(forecast_data, aqi_data, inputs)
        if not result.daily_chart_data:
            results_content_list.append(P("No forecast data available to display."))
        else:
            sorted_days = sorted(result.daily_chart_data.keys(), key=lambda d: datetime.strptime(d, '%a %Y-%m-%d'))

            # --- Determine current date in the location's timezone --- 
            current_local_date = None
            try:
                # tz is defined earlier in the 'get' function when processing forecast_data
                if 'timezone' in forecast_data:
                     tz_api = pytz.timezone(forecast_data.get('timezone', 'UTC'))
                     current_local_date = datetime.now(tz_api).date()
                else: # Fallback if timezone info somehow missing
                     current_local_date = datetime.now().date()
            except Exception as e:
                print(f"Error determining current local date: {e}")
                current_local_date = datetime.now().date() # Fallback
            # --- End date determination ---
            # print(f"Modal Log: Current local date for filtering = {current_local_date}") # REMOVE Log current date

            for day_str in sorted_days:
                # --- Filter out past days --- 
                day_date = datetime.strptime(day_str, '%a %Y-%m-%d').date()
                if current_local_date and day_date < current_local_date:
                    # print(f"Skipping past day: {day_str}") # Optional logging
                    continue
                # --- End filtering ---

                day_chart_data = result.daily_chart_data[day_str]
                day_good_intervals = result.daily_good_intervals.get(day_str, [])
                day_good_periods_text = result.daily_good_periods_text.get(day_str, [])

                # Chart IDs and Divs
                main_chart_id=f"chart-div-{day_str.replace(' ','-').replace('/','-')}"
                aqi_chart_id=f"aqi-chart-div-{day_str.replace(' ','-').replace('/','-')}"
                main_chart_div=Div(id=main_chart_id, Cls="chart-container")
                aqi_chart_div=Div(id=aqi_chart_id, Cls="aqi-chart-container")

                # Chart Scripts
                main_chart_script=create_day_chart_script(day_str, day_chart_data, day_good_intervals, inputs)
                aqi_chart_script=create_aqi_chart_script(day_str, day_chart_data, inputs.max_aqi)

                day_label = P(day_str, Cls="day-label")
                day_content_children = [day_label]

                if day_good_periods_text:
                    day_content_children.append(H4("Good times to open windows:", Cls="mt-3 h6"))
                    list_items = [Li(period) for period in day_good_periods_text]
                    text_list_ul = Ul(*list_items, Cls="daily-periods-list")
                    day_content_children.append(text_list_ul)

                day_content_children.extend([
                    main_chart_div, main_chart_script,
                    aqi_chart_div, aqi_chart_script
                ])

                day_container = Div(*day_content_children, Cls="day-data-container")
                results_content_list.append(day_container)
        results_div = Div(*results_content_list, id="results")

    # *** Form Setup ***
    form = Form(
        H3("Window Opening Conditions:"),
        Fieldset( # Location - NEW
             Label("Location: ", Input(name="location", type="text", value=inputs.location or ""))
        ),
        Fieldset( # Temp
             Label("Min Outdoor Temp (°F): ", Input(name="min_temp", type="number", value=inputs.min_temp)),
             Label("Max Outdoor Temp (°F): ", Input(name="max_temp", type="number", value=inputs.max_temp))
        ),
        Fieldset( # RH
             Label("Min Indoor Rel Hum (%): ", Input(name="min_rh", type="number", value=inputs.min_rh, min=0, max=100)),
             Label("Max Indoor Rel Hum (%): ", Input(name="max_rh", type="number", value=inputs.max_rh, min=0, max=100))
        ),
        Fieldset( # Indoor Temp Ref
            Label("Reference Indoor Temp (°F): ", Input(name="indoor_ref_temp", type="number", value=inputs.indoor_ref_temp))
        ),
        Fieldset( # Precip Probability
            Label("Max Precipitation Probability (%): ", Input(name="max_precip_prob", type="number", value=inputs.max_precip_prob, min=0, max=100))
        ),
        Fieldset( # AQI Threshold
            Label("Max US AQI: ", Input(name="max_aqi", type="number", value=inputs.max_aqi, min=0))
        ),
        # Fieldset( # Location - REMOVED
        #     Label("Latitude: ", Input(name="latitude", type="number", step="any", value=inputs.latitude)),
        #     Label("Longitude: ", Input(name="longitude", type="number", step="any", value=inputs.longitude))
        # ),
         # Optionally add hidden fields for lat/lon if needed, or display them read-only
         Hidden(name="latitude", value=str(inputs.latitude or "")),
         Hidden(name="longitude", value=str(inputs.longitude or "")),
        Button("Update Forecast", type="submit"),
        method="get", action="/", Cls="mt-4"
    )

    # *** Update Attribution Footer ***
    attribution_footer = Footer(
        P(
          A("Weather and Air Quality data by Open-Meteo.com", href="https://open-meteo.com/"),
          " | ",
          A("Address lookup by Nominatim", href="https://nominatim.org/"),
          " (OpenStreetMap data)"
        ),
        Cls="mt-5 text-center text-muted small"
    )

    # *** Combine Page Elements ***
    page_elements = [intro_text]
    if address_display: page_elements.append(address_display)
    page_elements.append(results_div)
    page_elements.append(form)
    page_elements.append(attribution_footer)

    return Titled("Open Window Advisor", *page_elements)


if __name__ == "__main__":
    serve()