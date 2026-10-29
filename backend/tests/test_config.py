import os

from app.config import Settings


def test_default_frontend_origins_include_local_vite_and_docker_ports() -> None:
    previous_origin = os.environ.get("FRONTEND_ORIGIN")
    previous_database_url = os.environ.get("DATABASE_URL")
    try:
        os.environ.pop("FRONTEND_ORIGIN", None)
        os.environ["DATABASE_URL"] = "sqlite:///:memory:"
        settings = Settings(_env_file=None)
    finally:
        if previous_origin is None:
            os.environ.pop("FRONTEND_ORIGIN", None)
        else:
            os.environ["FRONTEND_ORIGIN"] = previous_origin

        if previous_database_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_database_url

    origins = [origin.strip() for origin in settings.frontend_origin.split(",") if origin.strip()]

    assert "http://localhost:5173" in origins
    assert "http://localhost:4173" in origins
    assert "http://localhost:8080" in origins