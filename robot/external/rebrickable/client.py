import requests
import time
import os
from typing import Optional, List, Dict
from robot.external.rebrickable.types import (
    RebrickableSetData,
    RebrickableSetSearchResponse,
    RebrickablePartData,
    RebrickableInventoryResponse,
)


BASE_URL = "https://rebrickable.com/api/v3/lego"
RATE_LIMIT_DELAY_MS = 100  # Be nice to the API


class RebrickableClient:
    """Client for interacting with the Rebrickable API"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("REBRICKABLE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Rebrickable API key required. Set REBRICKABLE_API_KEY environment variable."
            )
        self.headers = {"Authorization": f"key {self.api_key}"}
        self._last_request_time = 0

    def _rate_limit(self):
        """Ensure we don't exceed rate limits"""
        current_time = time.time()
        time_since_last = (current_time - self._last_request_time) * 1000
        if time_since_last < RATE_LIMIT_DELAY_MS:
            time.sleep((RATE_LIMIT_DELAY_MS - time_since_last) / 1000.0)
        self._last_request_time = time.time()

    def _make_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[dict]:
        """Make a GET request to the Rebrickable API"""
        self._rate_limit()
        url = BASE_URL + endpoint

        try:
            response = requests.get(url, headers=self.headers, params=params or {})

            if response.status_code != 200:
                print(f"Rebrickable API error: {response.status_code} - {response.text}")
                return None

            return response.json()

        except Exception as e:
            print(f"Rebrickable API request failed: {e}")
            return None

    def search_sets(
        self, query: str, page_size: int = 20
    ) -> Optional[RebrickableSetSearchResponse]:
        """
        Search for LEGO sets by name or set number

        Args:
            query: Search query (set number or name)
            page_size: Number of results per page (default 20)

        Returns:
            RebrickableSetSearchResponse with search results
        """
        endpoint = "/sets/"
        params = {"search": query, "page_size": page_size}

        result = self._make_request(endpoint, params)
        return result if result else None

    def get_set_info(self, set_num: str) -> Optional[RebrickableSetData]:
        """
        Get detailed information about a specific set

        Args:
            set_num: Set number (e.g., "75192-1")

        Returns:
            RebrickableSetData with set information
        """
        endpoint = f"/sets/{set_num}/"
        return self._make_request(endpoint)

    def get_set_inventory(
        self, set_num: str, include_spares: bool = True
    ) -> List[RebrickablePartData]:
        """
        Get the complete inventory (parts list) for a set

        Args:
            set_num: Set number (e.g., "75192-1")
            include_spares: Whether to include spare parts (default True)

        Returns:
            List of RebrickablePartData with all parts in the set
        """
        all_parts: List[RebrickablePartData] = []
        endpoint = f"/sets/{set_num}/parts/"
        page = 1

        while True:
            params = {"page": page, "page_size": 100}
            result = self._make_request(endpoint, params)

            if not result or "results" not in result:
                break

            parts: List[RebrickablePartData] = result["results"]

            # Filter spares if requested
            if not include_spares:
                parts = [p for p in parts if not p.get("is_spare", False)]

            all_parts.extend(parts)

            # Check if there are more pages
            if not result.get("next"):
                break

            page += 1

        return all_parts

    def get_part_mappings(self, rebrickable_part_num: str) -> Optional[Dict]:
        """
        Get external ID mappings for a part (e.g., BrickLink ID)

        Args:
            rebrickable_part_num: Rebrickable part number

        Returns:
            Dict with external IDs including BrickLink
        """
        endpoint = f"/parts/{rebrickable_part_num}/"
        result = self._make_request(endpoint)

        if result and "external_ids" in result:
            return result["external_ids"]

        return None


# Convenience functions for use without instantiating the client


def searchSets(query: str, api_key: Optional[str] = None) -> Optional[RebrickableSetSearchResponse]:
    """Search for LEGO sets"""
    client = RebrickableClient(api_key)
    return client.search_sets(query)


def getSetInfo(set_num: str, api_key: Optional[str] = None) -> Optional[RebrickableSetData]:
    """Get information about a specific set"""
    client = RebrickableClient(api_key)
    return client.get_set_info(set_num)


def getSetInventory(
    set_num: str, include_spares: bool = True, api_key: Optional[str] = None
) -> List[RebrickablePartData]:
    """Get the parts inventory for a set"""
    client = RebrickableClient(api_key)
    return client.get_set_inventory(set_num, include_spares)
