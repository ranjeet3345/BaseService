from urllib.parse import urlparse

from app.core.config import settings

class ApiConfig:

    @staticmethod

    def secret_key_header() -> dict:

        return {
        "Erp-Secret-Key": settings.ERP_SECRET_KEY,

    }

    @staticmethod

    def get_base_url(service: str, version: str = "v1", path: str | None = None) -> str:

        parsed = urlparse(settings.CLOUD_API_URL)

        # api.ainstitute.cloud
        host = parsed.netloc

        # inject env for non-prod

        if settings.ENVIRONMENT_MODE != "prod":

            host = f"{settings.ENVIRONMENT_MODE}.{host}"

        base = f"{parsed.scheme}://{host}/{version.strip('/')}/{service.strip('/')}"

        if path:

            return f"{base}/{path.strip('/')}"

        return base

