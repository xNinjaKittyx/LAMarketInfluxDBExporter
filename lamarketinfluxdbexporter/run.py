"""

This is not meant to be a long running script. This should only be ran once to be able to visualize the data.

"""
import argparse
import datetime
import logging
import os
import pathlib
import time
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

import requests
import urllib3
from influxdb import InfluxDBClient

urllib3.disable_warnings()

LOG_PATH = pathlib.Path(os.getenv("LOG_LOCATION", "./logs"))
LOG_PATH.mkdir(exist_ok=True)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s::%(levelname)s:%(module)s:%(lineno)d - %(message)s")
fh = RotatingFileHandler(
    filename=LOG_PATH / "data_export.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=10,
)
fh.setFormatter(formatter)
logger.addHandler(fh)
sh = logging.StreamHandler()
sh.setFormatter(formatter)
logger.addHandler(sh)


NA_WEST_LOST_MARKET_API = "https://www.lostarkmarket.online/api/export-item-history/North%20America%20West/"

ITEMS = [
    "basic-oreha-fusion-material-2",
    "crystallized-destruction-stone-0",
    "crystallized-guardian-stone-0",
    "great-honor-leapstone-2",
    "honor-leapstone-2",
    "honor-shard-pouch-l-3",
    "honor-shard-pouch-m-2",
    "honor-shard-pouch-s-1",
    "metallurgy-basic-welding-3",
    "metallurgy-applied-welding-4",
    "powder-of-sage-3",
    "simple-oreha-fusion-material-1",
    "solar-blessing-2",
    "solar-grace-1",
    "solar-protection-3",
    "tailoring-basic-mending-3",
    "tailoring-applied-mending-4",
    "fish-0",
    "oreha-solar-carp-2",
    "natural-pearl-1",
    "blue-crystal-0",
    "royal-crystal-0",
]


parser = argparse.ArgumentParser()
parser.add_argument("--host", default=os.getenv("INFLUX_HOST"), type=str, help="Host where influxdb is located.")
parser.add_argument("--port", default=os.getenv("INFLUX_PORT", 8086), type=int, help="Port Number (default 8086)")
parser.add_argument("--user", default=os.getenv("INFLUX_USER"), help="InfluxDB Username")
parser.add_argument("--pw", default=os.getenv("INFLUX_PASS"), help="InfluxDB Password")
parser.add_argument("--db", default=os.getenv("INFLUX_DB", "lamarket-test"), help="InfluxDB Database Name")
parser.add_argument("--fresh", action="store_true", default=False, help="Recreate the influx database.")
parser.add_argument(
    "--sleep",
    default=os.getenv("SLEEP_TIMER", 60),
    type=int,
    help="Time to sleep between data fetching. Recommended to be 30 or higher. (Most likely can't do less than 15)",
)


def ping_influxdb(client):
    tries = 0
    while True:
        try:
            client.ping()
            return
        except Exception:
            tries += 1
            logger.exception(f"Failed to ping database - Trying again ({tries})")
            time.sleep(1)


def create_or_use_database(client, db_name):
    for database in client.query("SHOW DATABASES").get_points():
        if database["name"] == db_name:
            return

    client.create_database(db_name)


def normalize_numbers(value):
    return float(value) if value else 0.0


if __name__ == "__main__":
    args = parser.parse_args()
    client = InfluxDBClient(args.host, args.port, args.user, args.pw, args.db)

    ping_influxdb(client)
    # We don't expect anyone to be running with this flag unless it's ran manually.
    if args.fresh:
        client.drop_database(args.db)
    create_or_use_database(client, args.db)

    influxdb_data = []

    fields = ["open", "high", "low", "close"]

    # Asyncio possible? Ratelimiting concerns?
    for item in ITEMS:
        r = requests.get(f"{NA_WEST_LOST_MARKET_API}{item}")
        data = r.json()
        for value in data[0]:
            influxdb_data.append(
                {
                    "measurement": "price",
                    "tags": {
                        "item": item,
                    },
                    "time": datetime.datetime.fromtimestamp(value["timestamp"] / 1000.0, tz=ZoneInfo("America/Los_Angeles")).isoformat(),
                    "fields": {field_key: normalize_numbers(value[field_key]) for field_key in fields},
                }
            )

    breakpoint()
    client.write_points(influxdb_data)
