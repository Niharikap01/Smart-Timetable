from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.routes import api_router
from app.api.routes.vacancy import router as vacancy_router
from app.websocket.manager import ws_manager
from app.vacancy.cache import occupancy_cache

app = FastAPI(
    title="Smart Department Timetable System",
    description="Automated timetable generation, classroom allotment & real-time vacancy system",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(vacancy_router)


@app.get("/api/health")
def health_check():
    return {"status": "ok", "message": "Smart Timetable System is running"}


@app.websocket("/ws/vacancy")
async def vacancy_ws(ws: WebSocket):
    await ws_manager.connect(ws)
    try:
        # Send current state on connect
        await ws.send_json({"event": "INITIAL_STATE", "rooms": occupancy_cache.get_all()})
        while True:
            await ws.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(ws)
