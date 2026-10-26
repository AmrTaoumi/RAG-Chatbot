import logging
import sys

import discovery
from fastapi import FastAPI, HTTPException

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)

app = FastAPI()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/discover")
def discover():
    try:
        count = discovery.discover()
    except discovery.RobotsDisallowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except discovery.DiscoveryBusy as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"published": count}
