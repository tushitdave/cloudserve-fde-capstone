"""FastAPI composition root; add routers as use cases become real."""

from fastapi import FastAPI

from cloudserve.api.routes.health import router as health_router
from cloudserve.api.routes.tickets import router as tickets_router
from cloudserve.api.routes.knowledge import router as knowledge_router

app = FastAPI(title="CloudServe API", version="0.1.0")
app.include_router(health_router)
app.include_router(tickets_router)
app.include_router(knowledge_router)
