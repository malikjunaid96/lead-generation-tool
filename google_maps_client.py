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
from typing import Callable, Dict, List, Optional, Set

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
        "places.rating",
        "places.userRatingCount",
    ]
)

# Text Search (New) returns up to 20 results per page, up to 3 pages per query (60 results).
MAX_PAGE_SIZE = 20


def has_no_website(place: Dict) -> bool:
    """Returns True if the place does not have a listed website."""
    website = place.get("websiteUri")
    if not website:
        return True
    website_str = str(website).strip()
    return website_str == "" or website_str.lower() in ("none", "null", "n/a", "-")


def build_query_variations(query: str, business_type: str = "", location: str = "") -> List[str]:
    """
    Generates variations of the search query so we can retrieve more than
    Google's 60-result per-query cap if needed to satisfy the exact target count
    (e.g., finding 40 businesses that have no website).
    """
    b_type = (business_type or "").strip()
    loc = (location or "").strip()

    if not b_type and " in " in query:
        parts = query.split(" in ", 1)
        b_type, loc = parts[0].strip(), parts[1].strip()

    if b_type and loc:
        variations = [
            f"{b_type} in {loc}",
            f"{b_type} near {loc}",
            f"local {b_type} in {loc}",
            f"best {b_type} in {loc}",
            f"{b_type} services in {loc}",
            f"{b_type} companies in {loc}",
            f"{b_type} contractor in {loc}",
            f"top {b_type} in {loc}",
            f"affordable {b_type} in {loc}",
            f"{b_type} {loc}",
        ]
    else:
        variations = [
            query,
            f"local {query}",
            f"best {query}",
            f"{query} services",
            f"top {query}",
        ]

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_variations: List[str] = []
    for v in variations:
        v_clean = v.strip()
        if v_clean.lower() not in seen:
            seen.add(v_clean.lower())
            unique_variations.append(v_clean)
    return unique_variations


class GoogleMapsClient:
    """Small wrapper around the Places API (New) Text Search endpoint."""

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("A Google Maps API key is required.")
        self.api_key = api_key

    def search_places(
        self,
        query: str,
        target_count: int = 20,
        filter_no_website: bool = False,
        min_rating: float = 0.0,
        min_reviews: int = 0,
        business_type: str = "",
        location: str = "",
        status_callback: Optional[Callable[[str], None]] = None,
        max_results: Optional[int] = None,
    ) -> List[Dict]:
        """
        Runs a Text Search (New) query and pages through results until `target_count`
        is reached.

        If `filter_no_website` is True, it filters places during collection and queries
        variations if needed to return EXACTLY `target_count` businesses that have no website.
        Optionally filters by `min_rating` and `min_reviews`.
        """
        if max_results is not None:
            target_count = max_results

        target_count = max(1, target_count)

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": FIELD_MASK,
        }

        seen_place_ids: Set[str] = set()
        matching_places: List[Dict] = []
        queries = build_query_variations(query, business_type, location)

        for q_idx, current_query in enumerate(queries):
            if len(matching_places) >= target_count:
                break

            if status_callback:
                if filter_no_website:
                    status_callback(
                        f"Searching: '{current_query}' (found {len(matching_places)}/{target_count} qualified leads)..."
                    )
                else:
                    status_callback(
                        f"Searching: '{current_query}' (found {len(matching_places)}/{target_count})..."
                    )

            next_token = None
            page = 0
            while page < 3:  # Google Places TextSearch limits to at most 3 pages (60 places) per query
                page += 1
                body: Dict[str, object] = {"textQuery": current_query, "pageSize": MAX_PAGE_SIZE}
                if next_token:
                    body["pageToken"] = next_token

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

                places = data.get("places", [])
                if not places:
                    break

                for place in places:
                    place_id = place.get("id")
                    if place_id:
                        if place_id in seen_place_ids:
                            continue
                        seen_place_ids.add(place_id)

                    if filter_no_website and not has_no_website(place):
                        continue

                    # Filter by minimum rating if specified
                    if min_rating > 0.0:
                        place_rating = float(place.get("rating") or 0.0)
                        if place_rating < min_rating:
                            continue

                    # Filter by minimum reviews count if specified
                    if min_reviews > 0:
                        place_reviews = int(place.get("userRatingCount") or 0)
                        if place_reviews < min_reviews:
                            continue

                    matching_places.append(place)
                    if len(matching_places) >= target_count:
                        break

                if len(matching_places) >= target_count:
                    break

                next_token = data.get("nextPageToken")
                if not next_token:
                    break

                # Google's next-page tokens take a moment to become valid
                time.sleep(2)

        return matching_places[:target_count]


def parse_place(place: Dict) -> Dict[str, object]:
    """Flattens a raw Places API (New) place object into simple fields with rating and reviews."""
    name = place.get("displayName", {}).get("text", "") if place.get("displayName") else ""
    phone: Optional[str] = place.get("internationalPhoneNumber") or place.get("nationalPhoneNumber")
    raw_rating = place.get("rating")
    raw_reviews = place.get("userRatingCount")

    return {
        "Business Name": name,
        "Phone Number": phone or "",
        "Rating": float(raw_rating) if raw_rating is not None else "",
        "Reviews": int(raw_reviews) if raw_reviews is not None else 0,
        "Website": place.get("websiteUri") or "",
        "Address": place.get("formattedAddress") or "",
        "Google Maps URL": place.get("googleMapsUri") or "",
    }
