"""Earth-observation fetchers — earthquakes, FIRMS fires, space weather, weather radar."""
import csv
import io
import logging
import heapq
from services.network_utils import fetch_with_curl
from services.fetchers._store import latest_data, _data_lock, _mark_fresh
from services.fetchers.retry import with_retry

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Earthquakes (USGS)
# ---------------------------------------------------------------------------
@with_retry(max_retries=1, base_delay=1)
def fetch_earthquakes():
    quakes = []
    try:
        url = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.geojson"
        response = fetch_with_curl(url, timeout=10)
        if response.status_code == 200:
            features = response.json().get("features", [])
            for f in features[:50]:
                mag = f["properties"]["mag"]
                lng, lat, depth = f["geometry"]["coordinates"]
                quakes.append({
                    "id": f["id"], "mag": mag,
                    "lat": lat, "lng": lng,
                    "place": f["properties"]["place"]
                })
    except Exception as e:
        logger.error(f"Error fetching earthquakes: {e}")
    with _data_lock:
        latest_data["earthquakes"] = quakes
    if quakes:
        _mark_fresh("earthquakes")


# ---------------------------------------------------------------------------
# NASA FIRMS Fires
# ---------------------------------------------------------------------------
@with_retry(max_retries=1, base_delay=2)
def fetch_firms_fires():
    """Fetch global fire/thermal anomalies from NASA FIRMS (NOAA-20 VIIRS, 24h, no key needed)."""
    fires = []
    try:
        url = "https://firms.modaps.eosdis.nasa.gov/data/active_fire/noaa-20-viirs-c2/csv/J1_VIIRS_C2_Global_24h.csv"
        response = fetch_with_curl(url, timeout=30)
        if response.status_code == 200:
            reader = csv.DictReader(io.StringIO(response.text))
            all_rows = []
            for row in reader:
                try:
                    lat = float(row.get("latitude", 0))
                    lng = float(row.get("longitude", 0))
                    frp = float(row.get("frp", 0))
                    conf = row.get("confidence", "nominal")
                    daynight = row.get("daynight", "")
                    bright = float(row.get("bright_ti4", 0))
                    all_rows.append({
                        "lat": lat, "lng": lng, "frp": frp,
                        "brightness": bright, "confidence": conf,
                        "daynight": daynight,
                        "acq_date": row.get("acq_date", ""),
                        "acq_time": row.get("acq_time", ""),
                    })
                except (ValueError, TypeError):
                    continue
            fires = heapq.nlargest(5000, all_rows, key=lambda x: x["frp"])
        logger.info(f"FIRMS fires: {len(fires)} hotspots (from {response.status_code})")
    except Exception as e:
        logger.error(f"Error fetching FIRMS fires: {e}")
    with _data_lock:
        latest_data["firms_fires"] = fires
    if fires:
        _mark_fresh("firms_fires")


# ---------------------------------------------------------------------------
# Space Weather (NOAA SWPC)
# ---------------------------------------------------------------------------
@with_retry(max_retries=1, base_delay=1)
def fetch_space_weather():
    """Fetch NOAA SWPC Kp index and recent solar events."""
    try:
        kp_resp = fetch_with_curl("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json", timeout=10)
        kp_value = None
        kp_text = "QUIET"
        if kp_resp.status_code == 200:
            kp_data = kp_resp.json()
            if kp_data:
                latest_kp = kp_data[-1]
                kp_value = float(latest_kp.get("kp_index", 0))
                if kp_value >= 7:
                    kp_text = f"STORM G{min(int(kp_value) - 4, 5)}"
                elif kp_value >= 5:
                    kp_text = f"STORM G{min(int(kp_value) - 4, 5)}"
                elif kp_value >= 4:
                    kp_text = "ACTIVE"
                elif kp_value >= 3:
                    kp_text = "UNSETTLED"

        events = []
        ev_resp = fetch_with_curl("https://services.swpc.noaa.gov/json/edited_events.json", timeout=10)
        if ev_resp.status_code == 200:
            all_events = ev_resp.json()
            for ev in all_events[-10:]:
                events.append({
                    "type": ev.get("type", ""),
                    "begin": ev.get("begin", ""),
                    "end": ev.get("end", ""),
                    "classtype": ev.get("classtype", ""),
                })

        with _data_lock:
            latest_data["space_weather"] = {
                "kp_index": kp_value,
                "kp_text": kp_text,
                "events": events,
            }
        _mark_fresh("space_weather")
        logger.info(f"Space weather: Kp={kp_value} ({kp_text}), {len(events)} events")
    except Exception as e:
        logger.error(f"Error fetching space weather: {e}")


# ---------------------------------------------------------------------------
# Weather Radar (RainViewer)
# ---------------------------------------------------------------------------
@with_retry(max_retries=1, base_delay=1)
def fetch_weather():
    try:
        url = "https://api.rainviewer.com/public/weather-maps.json"
        response = fetch_with_curl(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if "radar" in data and "past" in data["radar"]:
                latest_time = data["radar"]["past"][-1]["time"]
                with _data_lock:
                    latest_data["weather"] = {"time": latest_time, "host": data.get("host", "https://tilecache.rainviewer.com")}
                _mark_fresh("weather")
    except Exception as e:
        logger.error(f"Error fetching weather: {e}")
