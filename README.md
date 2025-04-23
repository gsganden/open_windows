# Open Window Advisor

This application helps determine good times to open windows based on weather forecasts and air quality index (AQI) data.

It is deployed at https://gsganden--open-window-advisor-web.modal.run/.

It considers:
* Outdoor temperature
* Predicted indoor relative humidity (based on outdoor dew point and a reference indoor temperature)
* Precipitation probability
* US Air Quality Index (AQI)

## How to Run

```bash
uv sync
```

```bash
uv run modal serve deploy.py
```
