"""REST API connector with pagination and nested payload support."""

from typing import Any, Dict, List
import httpx
import pandas as pd

from datasentinel.config.schema import SourceConfig
from datasentinel.connectors.base import BaseConnector, ConnectorRegistry, DataSet
from datasentinel.connectors.json_connector import _extract_nested_path
from datasentinel.core.exceptions import ConnectorError


@ConnectorRegistry.register("rest_api")
class RestAPIConnector(BaseConnector):
    """Adapter for fetching tabular data from REST APIs with pagination support."""

    def __init__(self, config: SourceConfig) -> None:
        super().__init__(config)
        if not self.config.api_url:
            raise ConnectorError("REST API connector requires 'api_url' parameter.")
        self.api_url = self.config.api_url
        self.headers = dict(self.config.headers)
        self.page_param = self.config.page_param
        self.size_param = self.config.size_param
        self.max_pages = max(1, self.config.max_pages)
        self.nested_path = self.config.nested_path

    def connect(self) -> None:
        """Validate URL formatting."""
        if not (self.api_url.startswith("http://") or self.api_url.startswith("https://")):
            raise ConnectorError(
                f"Invalid API URL protocol: '{self.api_url}'",
                details="API URL must start with http:// or https://",
            )

    def test_connection(self) -> bool:
        """Send HEAD or probe GET request."""
        try:
            with httpx.Client(timeout=5.0) as client:
                res = client.get(self.api_url, headers=self.headers, params={self.size_param: 1})
                return res.status_code < 400
        except Exception:
            return False

    def load(self) -> DataSet:
        """Fetch paginated data pages and combine into unified DataSet."""
        all_records: List[Dict[str, Any]] = []

        try:
            with httpx.Client(timeout=15.0) as client:
                for page in range(1, self.max_pages + 1):
                    params = {
                        self.page_param: page,
                        self.size_param: 50,
                    }
                    response = client.get(self.api_url, headers=self.headers, params=params)
                    if response.status_code >= 400:
                        raise ConnectorError(
                            f"API request failed with HTTP {response.status_code} on page {page}",
                            details=response.text[:200],
                        )

                    payload = response.json()
                    page_items = payload
                    if self.nested_path:
                        try:
                            page_items = _extract_nested_path(payload, self.nested_path)
                        except Exception as exc:
                            raise ConnectorError(
                                f"Failed resolving path '{self.nested_path}' in API response page {page}",
                                details=str(exc),
                            ) from exc

                    if not isinstance(page_items, list):
                        if isinstance(page_items, dict):
                            all_records.append(page_items)
                            break
                        raise ConnectorError(
                            f"Expected list of items from API, got {type(page_items).__name__}"
                        )

                    if not page_items:
                        break

                    for item in page_items:
                        if isinstance(item, dict):
                            all_records.append(item)

        except httpx.RequestError as exc:
            raise ConnectorError(
                f"Network communication failure connecting to API: {self.api_url}",
                details=str(exc),
            ) from exc
        except Exception as exc:
            if isinstance(exc, ConnectorError):
                raise
            raise ConnectorError(
                f"Unexpected failure while querying API {self.api_url}",
                details=str(exc),
            ) from exc

        df = pd.DataFrame(all_records)
        info: Dict[str, Any] = {
            "source_type": "rest_api",
            "url": self.api_url,
            "total_records_fetched": len(all_records),
        }
        return DataSet(name="rest_api_dataset", dataframe=df, source_info=info)
