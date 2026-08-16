"""
Thin client for the Google Places API (New) - Text Search endpoint.

Docs: https://developers.google.com/maps/documentation/places/web-service/text-search

A single Text Search (New) call, with the right field mask, returns each
business's name, address, phone number, and website all at once - so unlike
the older/legacy Places API, we don't need a separate "Place Details" call
per result.
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

import requests

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Fields to request for every place. displayName/formattedAddress/googleMapsUri
# are "Pro" tier; the phone number and website fields are "Enterprise" tier.
# Google bills the whole call at the highest tier touched, so this call bills
# as Enterprise regardless - see README.md "Costs" section.
FIELD_MASK = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.nationalPhoneNumber",
        "places.internationalPhoneNumber",
        "places.websiteUri",
        "places.googleMapsUri",
    ]
)

# Text Search (New) never returns more than this many results, total, no
# matter how many pages you request - it's a hard limit set by the API.
MAX_TOTAL_RESULTS = 60

# Google returns at most this many results per page.
MAX_PAGE_SIZE = 20


class GoogleMapsClient:
    """Small wrapper around the Places API (New) Text Search endpoint."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("A Google Maps API key is required.")
        self.api_key = api_key

    def search_places(self, query: str, max_results: int = 20) -> List[Dict]:
        """
        Runs a Text Search (New) query (e.g. "Roofers in Austin, TX") and
        pages through results until `max_results` is reached or the API's
        own 60-result cap kicks in.

        Returns a list of raw "Place" objects (dicts) as documented at
        https://developers.google.com/maps/documentation/places/web-service/reference/rest/v1/places
        """
        max_results = max(1, min(max_results, MAX_TOTAL_RESULTS))
        page_size = min(max_results, MAX_PAGE_SIZE)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        all_places: List[Dict] = []
        body = {"textQuery": query, "pageSize": page_size}

        while True:
            try:
                response = requests.post(TEXT_SEARCH_URL, headers=headers, json=body, timeout=15)
            except requests.RequestException as exc:
                raise RuntimeError(f"Network error while calling the Places API: {exc}") from exc

            if response.status_code != 200:
                raise RuntimeError(
                    f"Google Places API error ({response.status_code}): {response.text}"
                )

            try:
                data = response.json()
            except ValueError as exc:
                raise RuntimeError(
                    "Google Places API returned an unexpected (non-JSON) response."
                ) from exc

            all_places.extend(data.get("places", []))

            next_token = data.get("nextPageToken")
            if not next_token or len(all_places) >= max_results:
                break

            # Google's next-page tokens can take a moment to become valid.
            time.sleep(2)
            body = {"textQuery": query, "pageSize": page_size, "pageToken": next_token}

        return all_places[:max_results]


def parse_place(place: Dict) -> Dict[str, str]:
    """Flattens a raw Places API (New) place object into simple string fields."""
    name = place.get("displayName", {}).get("text", "") if place.get("displayName") else ""
    phone: Optional[str] = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
    return {
        "Business Name": name,
        "Phone Number": phone or "",
        "Website": place.get("websiteUri") or "",
        "Address": place.get("formattedAddress") or "",
        "Google Maps URL": place.get("googleMapsUri") or "",
    }
