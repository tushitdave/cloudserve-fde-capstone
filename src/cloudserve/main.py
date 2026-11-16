"""FastAPI composition root."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from cloudserve.api.routes.health import router as health_router
from cloudserve.api.routes.knowledge import router as knowledge_router
from cloudserve.api.routes.policy import router as policy_router
from cloudserve.api.routes.tickets import router as tickets_router
from cloudserve.retrieval import warm_up


@asynccontextmanager
async def lifespan(_app):
    warm_up()  # load the dense index and models before the first ticket (falls back to lexical if unavailable)
    yield


app = FastAPI(title="CloudServe API", version="0.3.0", lifespan=lifespan)
app.include_router(health_router)
app.include_router(tickets_router)
app.include_router(knowledge_router)
app.include_router(policy_router)
