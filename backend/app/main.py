from fastapi import FastAPI


APP_VERSION = "0.1.0"


def create_app() -> FastAPI:
    app = FastAPI(title="个人国补比价工具", version=APP_VERSION)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": APP_VERSION, "database": "pending"}

    return app


app = create_app()
