import time
import logging
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urljoin
import requests
from requests.auth import HTTPBasicAuth

logger = logging.getLogger("woocommerce_client")


class WooCommerceAPIError(Exception):
    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Optional[Any] = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class WooCommerceClient:
    """
    Robust HTTP client for WooCommerce REST API v3 with authentication,
    exponential backoff retry logic, pagination, and rate limit handling.
    """

    def __init__(
        self,
        store_url: str,
        consumer_key: str,
        consumer_secret: str,
        api_version: str = "wc/v3",
        verify_ssl: bool = True,
        timeout_seconds: int = 30,
        max_retries: int = 3,
        backoff_factor: float = 1.5
    ):
        self.store_url = store_url.rstrip("/") + "/"
        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret
        self.api_version = api_version
        self.verify_ssl = verify_ssl
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.consumer_key, self.consumer_secret)
        self.session.headers.update({
            "User-Agent": "WooCommerce-Analytics-Intelligence/1.0 (Python)",
            "Accept": "application/json"
        })

    def _get_endpoint_url(self, endpoint: str) -> str:
        clean_endpoint = endpoint.lstrip("/")
        return urljoin(self.store_url, f"wp-json/{self.api_version}/{clean_endpoint}")

    def request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        json_data: Optional[Dict[str, Any]] = None
    ) -> requests.Response:
        url = self._get_endpoint_url(endpoint)
        retries = 0

        while retries <= self.max_retries:
            try:
                response = self.session.request(
                    method=method.upper(),
                    url=url,
                    params=params,
                    json=json_data,
                    verify=self.verify_ssl,
                    timeout=self.timeout_seconds
                )

                # Check for rate limiting (HTTP 429)
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")
                    sleep_time = float(retry_after) if retry_after else (self.backoff_factor ** retries)
                    logger.warning("WooCommerce API Rate limit encountered (429). Retrying in %.2f seconds.", sleep_time)
                    time.sleep(sleep_time)
                    retries += 1
                    continue

                # Server errors (5xx) - retry with exponential backoff
                if 500 <= response.status_code < 600:
                    sleep_time = self.backoff_factor ** retries
                    logger.warning("WooCommerce 5xx Server Error (%d). Retrying in %.2f seconds.", response.status_code, sleep_time)
                    time.sleep(sleep_time)
                    retries += 1
                    continue

                # Client error or success
                if not response.ok:
                    try:
                        err_json = response.json()
                        msg = err_json.get("message", response.text)
                    except Exception:
                        msg = response.text
                    raise WooCommerceAPIError(f"WooCommerce API error [{response.status_code}]: {msg}", response.status_code, response.text)

                return response

            except (requests.Timeout, requests.ConnectionError) as exc:
                retries += 1
                if retries > self.max_retries:
                    raise WooCommerceAPIError(f"Connection to WooCommerce failed after {self.max_retries} attempts: {str(exc)}")
                sleep_time = self.backoff_factor ** retries
                logger.warning("Network issue (%s). Retrying in %.2f seconds.", type(exc).__name__, sleep_time)
                time.sleep(sleep_time)

        raise WooCommerceAPIError(f"Failed to complete {method} request to {endpoint}")

    def test_connection(self) -> Dict[str, Any]:
        """Tests the credentials and fetches store metadata."""
        try:
            # Query system status or general settings
            resp = self.request("GET", "system_status")
            status_data = resp.json()
            env_info = status_data.get("environment", {})
            settings_info = status_data.get("settings", {})

            return {
                "success": True,
                "message": "Successfully connected to WooCommerce store.",
                "store_name": env_info.get("site_title", "Connected Store"),
                "currency": settings_info.get("currency", "USD"),
                "timezone": settings_info.get("timezone", "UTC"),
                "woocommerce_version": env_info.get("version", "v3+")
            }
        except WooCommerceAPIError as e:
            # Fallback test with products endpoint if system_status is restricted
            try:
                self.request("GET", "products", params={"per_page": 1})
                return {
                    "success": True,
                    "message": "Connected successfully via Products API.",
                    "store_name": "WooCommerce Store",
                    "currency": "USD",
                    "timezone": "UTC",
                    "woocommerce_version": "REST v3"
                }
            except Exception as fallback_err:
                return {
                    "success": False,
                    "message": f"Connection failed: {str(e)}",
                    "store_name": None,
                    "currency": None,
                    "timezone": None,
                    "woocommerce_version": None
                }

    def fetch_paginated(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        per_page: int = 100,
        max_pages: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetches all records across pages using WooCommerce header metadata."""
        current_page = 1
        all_records = []
        request_params = dict(params or {})
        request_params["per_page"] = per_page

        while True:
            request_params["page"] = current_page
            logger.info("Fetching %s page %d...", endpoint, current_page)

            resp = self.request("GET", endpoint, params=request_params)
            data = resp.json()

            if not isinstance(data, list) or not data:
                break

            all_records.extend(data)

            # Check WooCommerce total pages header
            total_pages_header = resp.headers.get("X-WP-TotalPages")
            if total_pages_header:
                total_pages = int(total_pages_header)
                if current_page >= total_pages:
                    break
            else:
                # If less than per_page items returned, reached the end
                if len(data) < per_page:
                    break

            if max_pages and current_page >= max_pages:
                break

            current_page += 1

        return all_records
