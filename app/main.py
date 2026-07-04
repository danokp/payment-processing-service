from fastapi import FastAPI

from app.api.v1.payments import router as payments_router


def create_app() -> FastAPI:
    app = FastAPI(title="Nebus Payment Processing Service")
    app.include_router(payments_router)
    return app


app = create_app()
