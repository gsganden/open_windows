# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture

This is a FastHTML web application that provides window opening recommendations based on weather forecasts and air quality data. The app calculates optimal times to open windows by analyzing:

- Outdoor temperature ranges
- Predicted indoor relative humidity (calculated from outdoor dew point and reference indoor temperature)
- Precipitation probability 
- US Air Quality Index (AQI)

The main application logic is in `app.py` with Modal deployment configuration in `deploy.py`.

### Key Components

- **Data fetching**: Uses Open-Meteo APIs for weather and AQI data, Nominatim for geocoding
- **Core algorithm**: `find_optimal_periods()` processes hourly forecast data and identifies good time windows
- **Visualization**: Plotly charts showing temperature, humidity, precipitation, and AQI with highlighted optimal periods
- **Location handling**: Supports both text address input (geocoded to coordinates) and direct lat/lon input

## Development Commands

### Local Development
```bash
# Install dependencies
uv sync

# Run locally with Modal
uv run modal serve deploy.py
```

### Deployment
```bash
# Deploy to Modal
uv run modal deploy deploy.py
```

The deployed app is available at: https://gsganden--open-window-advisor-web.modal.run/

## Key Files

- `app.py`: Main FastHTML application with weather data processing and UI
- `deploy.py`: Modal deployment configuration
- `pyproject.toml`: Python dependencies (httpx, modal, python-fasthtml, pytz)

## Data Sources

- Weather: Open-Meteo forecast API (temperature, dew point, precipitation)
- Air Quality: Open-Meteo air quality API (US AQI)
- Geocoding: Nominatim/OpenStreetMap (respects 1 req/sec rate limit)