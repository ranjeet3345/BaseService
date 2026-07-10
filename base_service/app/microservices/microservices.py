from typing import Any, Dict, Optional, Union
from urllib.parse import urlencode

import httpx
from starlette import status

from app.microservices.api_config import ApiConfig
from app.provider.redis.redis_provider import RedisCache
from app.schemas.dto.service_response import ServiceResponseDTO
from utils.alerting import alerter
from utils.exception_helper import raise_http_exception_422, raise_http_exception
from utils.logger import print_data

class BaseService:
    _API_VERSION: Optional[str] = None
    _SERVICE_NAME: Optional[str] = None

    def __init__(self):
        if not all([self._API_VERSION, self._SERVICE_NAME]):
            raise ValueError("API_VERSION and SERVICE_NAME are required.")

        self.default_headers: Dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    # ------------------------------------------------------------
    # URL Builder
    # ------------------------------------------------------------
    @classmethod
    def get_service_name(cls) -> str:
        return cls._SERVICE_NAME.capitalize()

    # ------------------------------------------------------------
    # URL Builder
    # ------------------------------------------------------------
    @classmethod
    def get_url(cls, path: str, query_params: Optional[Dict[str, Any]] = None) -> str:
        base_url = ApiConfig.get_base_url(
            service=cls._SERVICE_NAME,
            version=cls._API_VERSION
        )
        if query_params:
            query_string = urlencode(query_params)
            return f"{base_url}?{query_string}"

        if path:
            base_url = f"{base_url}/{path.strip('/')}"

        return base_url

    # ------------------------------------------------------------
    # Request Handler (with cache mechanics)
    # ------------------------------------------------------------
    async def _request(
            self,
            method: str,
            endpoint: str,
            *,
            path_params: Optional[Dict[str, Any]] = None,
            query_params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            data: Optional[Union[Dict[str, Any], str]] = None,
            timeout: int = 10,
            secret_key_header: bool = False,

            # CACHE PARAMETERS
            check_from_cache: bool = False,
            cache_key: Optional[str] = None,
            cache_expiry: int = 60 * 50  # default 5 minutes
    ) -> ServiceResponseDTO:

        try:
            """
            Generic request method to interact with remote APIs.
            Includes: Cache check + Cache store logic
            """

            # ----------------------------------------------
            # 1. CACHE CHECK
            # ----------------------------------------------
            if check_from_cache:
                if not cache_key:
                    raise ValueError("cache_key is required when check_from_cache=True")

                redis_cache = RedisCache()
                cached_value = redis_cache.get_data(cache_key)
                if cached_value:
                    print_data(f"[GET FROM CACHE] key={cache_key}")
                    return ServiceResponseDTO(**cached_value)

                print_data(f"[CACHE MISS] key={cache_key}")

            # ----------------------------------------------
            # Format endpoint
            # ----------------------------------------------
            if path_params:
                endpoint = endpoint.format(**path_params)

            url = self.get_url(endpoint)
            merged_headers = {**self.default_headers, **(headers or {})}

            if secret_key_header:
                merged_headers = {**ApiConfig.secret_key_header(), **merged_headers}

            # ----------------------------------------------
            # 2. MAKE API REQUEST
            # ----------------------------------------------
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.request(
                        method=method.upper(),
                        url=url,
                        headers=merged_headers,
                        params=query_params,
                        json=data
                    )

            except Exception as e:
                raise e

            status_code = response.status_code

            # ----------------------------------------------
            # 3. HANDLE 500 ERROR
            # ----------------------------------------------
            if status_code == 500:
                try:
                    error_body = response.json()
                except ValueError:
                    error_body = response.text

                alerter.send_alert(
                    message=f"{self.get_service_name()} Service is not working.",
                    extra_data={f"{self.get_service_name()} Response": error_body}
                )
                raise_http_exception(message=f"{self.get_service_name()} Service is not working.")

            response_data = response.json()

            # ----------------------------------------------
            # 4. HANDLE NON-200 ERRORS
            # ----------------------------------------------
            if status_code != status.HTTP_200_OK:
                alerter.send_alert(
                    message=f"{self.get_service_name()} Given- {status_code}",
                    extra_data={f"{self.get_service_name()} Response": response_data}
                )
                raise_http_exception_422(message=response_data['message']['message'])

            print_data(f"request pass- url: {url}, status_code: {status_code}, data: {response.json()}")

            # ----------------------------------------------
            # 5. STORE RESPONSE IN CACHE
            # ----------------------------------------------
            if check_from_cache and cache_key:
                redis_cache = RedisCache()
                redis_cache.set_data(cache_key, response_data, expire_seconds=cache_expiry)
                print_data(f"[CACHE STORE] key={cache_key}")

            return ServiceResponseDTO(**response_data)
        except Exception as e:
            alerter.send_alert(
                message=f"{self.get_service_name()} Service is not working.",
                extra_data={f"{self.get_service_name()} Response": str(e)}
            )
            raise e

 