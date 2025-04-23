import modal

# Define the Modal App (formerly Stub)
app = modal.App("open-window-advisor")

# Define the Modal image with necessary dependencies
# Make sure these match the packages used in app.py
modal_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "python-fasthtml>=0.12.14", # Corrected package name
        "httpx",
        "pytz",
        # Add any other direct dependencies of app.py here
    )
    .add_local_python_source("app") # Explicitly add the app module
)

# Import the FastHTML app instance from your app.py file
# Assuming your app instance is named 'app' in app.py
from app import app as fasthtml_app

# Expose the FastHTML app using Modal's ASGI adapter
@app.function(image=modal_image)
@modal.asgi_app()
def web():
    return fasthtml_app

# You can add other Modal functions here if needed, for example, a scheduled task.

# To deploy this app, run: modal deploy deploy.py
# To run it locally for development with Modal: modal serve deploy.py 