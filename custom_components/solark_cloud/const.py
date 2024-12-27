"""Constants for the Sol-Ark Cloud integration."""

DOMAIN = "solark_cloud"

# Sol-Ark Cloud only gets data once every 5 minutes, but poll minutely so we get data
# reasonably quickly.
DEFAULT_SCAN_INTERVAL = 60
