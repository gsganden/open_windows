<a href="https://www.hannahilea.com/blog/houseplant-programming">
  <img alt="Static Badge" src="https://img.shields.io/badge/%F0%9F%AA%B4%20Houseplant%20-x?style=flat&amp;label=Project%20type&amp;color=1E1E1D">
</a>

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
