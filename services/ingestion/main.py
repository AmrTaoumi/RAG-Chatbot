import logging
import sys
import threading
from contextlib import asynccontextmanager

import consumer
import discovery
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}',
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    threading.Thread(target=consumer.run, daemon=True).start()
    yield


class Health(BaseModel):
    status: str


class DiscoverResult(BaseModel):
    published: int


class Error(BaseModel):
    detail: str


app = FastAPI(
    title="Ingestion service",
    description="Scrapes the MARP index page, publishes DocumentDiscovered events and downloads the PDFs.",
    lifespan=lifespan,
)


@app.get("/health", response_model=Health, summary="Liveness check")
def health():
    return {"status": "ok"}


@app.post(
    "/discover",
    response_model=DiscoverResult,
    summary="Scrape the MARP page and publish new PDFs",
    description="Publishes one DocumentDiscovered event per PDF not seen before. Runs synchronously.",
    responses={
        403: {"model": Error, "description": "robots.txt disallows the index page"},
        409: {"model": Error, "description": "another discovery run is in progress"},
    },
)
def discover():
    try:
        count = discovery.discover()
    except discovery.RobotsDisallowed as e:
        raise HTTPException(status_code=403, detail=str(e))
    except discovery.DiscoveryBusy as e:
        raise HTTPException(status_code=409, detail=str(e))
    return {"published": count}
