#!/usr/bin/env python3
"""
FINN.no Real Estate API Client and Scraper

This module provides a client for scraping real estate listings from FINN.no,
Norway's largest online marketplace for real estate, cars, jobs, and more.

Architecture:
- FINN.no embeds listing data as JSON within the HTML response
- The data is structured in a "docs" array containing listing objects
- Pagination is handled via URL parameters (?page=N)
- Location filtering uses FINN's location taxonomy codes

IMPORTANT - API Access:
    FINN.no has an official REST API (api.finn.no) but it requires:
    1. Business relationship with FINN
    2. API key obtained through business contact
    3. orgId parameter for searches

    This scraper uses web scraping of the public website instead,
    which doesn't require API access but should be used responsibly.

Usage:
    from finn_api import FinnClient

    client = FinnClient()

    # Search for rental apartments in Oslo
    results = client.search_lettings(
        location="0.20061",  # Oslo
        price_from=5000,
        price_to=15000,
        no_of_bedrooms_from=1
    )

    # Search for homes for sale
    results = client.search_homes(
        location="0.20003",  # Bergen
        price_from=2000000,
        property_type=["1", "2"]  # Leilighet, Rekkehus
    )

    # Get listing details
    details = client.get_listing_details("448603189")
"""

import json
import time
import logging
import re
from typing import Optional, List, Dict, Any, Iterator, Union
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urlencode, urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SearchType(Enum):
    """Types of real estate searches on FINN.no"""
    LETTINGS = "lettings"      # Rentals (Til leie)
    HOMES = "homes"            # For sale (Til salgs)
    NEWBUILDINGS = "newbuildings"  # New construction
    PLOTS = "plots"            # Building plots
    COMMERCIAL = "commercial"  # Commercial real estate
    LEISURE = "leisure"        # Vacation homes (Fritidsbolig)


class PropertyType(Enum):
    """Property types on FINN.no"""
    APARTMENT = "1"       # Leilighet
    TOWNHOUSE = "2"       # Rekkehus
    DETACHED = "3"        # Enebolig
    SEMI_DETACHED = "4"   # Tomannsbolig
    OTHER = "5"           # Annet


class SortOption(Enum):
    """Sorting options for search results"""
    RELEVANCE = ""           # Default relevance
    PUBLISHED_DESC = "PUBLISHED_DESC"  # Newest first
    PUBLISHED_ASC = "PUBLISHED_ASC"    # Oldest first
    PRICE_DESC = "PRICE_DESC"          # Highest price first
    PRICE_ASC = "PRICE_ASC"            # Lowest price first


# Common location codes for Norway
LOCATION_CODES = {
    "oslo": "0.20061",
    "bergen": "0.20003",
    "trondheim": "0.20016",
    "stavanger": "0.20012",
    "kristiansand": "0.20011",
    "tromso": "0.20019",
    "drammen": "0.20006",
    "fredrikstad": "0.20001",
    "sandnes": "0.20012.20253",
    "asker": "0.20002",
    "bodo": "0.20018",
    "aalesund": "0.20015",
    # Counties (Fylker)
    "viken": "0.20030",
    "vestland": "0.20046",
    "rogaland": "0.20011",
    "trondelag": "0.20050",
    "nordland": "0.20018",
    "innlandet": "0.20034",
    "vestfold_telemark": "0.20038",
    "agder": "0.20042",
}


@dataclass
class Image:
    """Image information for a listing"""
    url: str
    path: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None
    aspect_ratio: Optional[float] = None


@dataclass
class ListingBasic:
    """Basic listing information from search results"""
    id: str
    heading: str
    location: str
    search_type: str
    url: str
    image: Optional[Image] = None
    price: Optional[str] = None
    price_total: Optional[int] = None
    price_suggestion: Optional[str] = None
    area: Optional[str] = None
    bedrooms: Optional[int] = None
    property_type: Optional[str] = None
    flags: List[str] = field(default_factory=list)
    timestamp: Optional[str] = None
    labels: List[str] = field(default_factory=list)


@dataclass
class ListingDetails(ListingBasic):
    """Detailed listing information"""
    description: Optional[str] = None
    address: Optional[str] = None
    postal_code: Optional[str] = None
    city: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    floor: Optional[str] = None
    total_floors: Optional[int] = None
    year_built: Optional[int] = None
    energy_label: Optional[str] = None
    ownership_type: Optional[str] = None
    facilities: List[str] = field(default_factory=list)
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    agency_name: Optional[str] = None
    images: List[Image] = field(default_factory=list)
    viewing_dates: List[str] = field(default_factory=list)
    common_costs: Optional[int] = None
    deposit: Optional[int] = None


@dataclass
class SearchResults:
    """Search results container"""
    items: List[ListingBasic]
    total_count: int
    page: int
    per_page: int
    has_next_page: bool
    search_type: str
    filters_applied: Dict[str, Any] = field(default_factory=dict)


class FinnClient:
    """
    API client for FINN.no real estate listings.

    This client scrapes the public FINN.no website to extract listing data.
    It supports:
    - Searching listings with various filters
    - Pagination through results
    - Getting detailed listing information
    - Rate limiting to avoid being blocked

    Note: FINN.no has an official API but requires business authentication.
    This scraper works without API access but should be used responsibly.
    """

    BASE_URL = "https://www.finn.no"
    SEARCH_ENDPOINTS = {
        SearchType.LETTINGS: "/realestate/lettings/search.html",
        SearchType.HOMES: "/realestate/homes/search.html",
        SearchType.NEWBUILDINGS: "/realestate/newbuildings/search.html",
        SearchType.PLOTS: "/realestate/plots/search.html",
        SearchType.COMMERCIAL: "/realestate/commercial/search.html",
        SearchType.LEISURE: "/realestate/leisuresale/search.html",  # Note: "leisuresale" not "leisure"
    }

    def __init__(
        self,
        rate_limit_delay: float = 1.0,
        max_retries: int = 3,
        timeout: int = 30,
        user_agent: Optional[str] = None
    ):
        """
        Initialize the FINN client.

        Args:
            rate_limit_delay: Delay between requests in seconds
            max_retries: Maximum number of retries for failed requests
            timeout: Request timeout in seconds
            user_agent: Custom user agent string
        """
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.last_request_time = 0

        # Create session with retry logic
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        # Set default headers
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        # Minimal headers - too many Accept headers can cause FINN to return different content
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept-Language": "nb-NO,nb;q=0.9,no;q=0.8,en;q=0.7",
        })

    def _rate_limit(self):
        """Enforce rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - elapsed)
        self.last_request_time = time.time()

    def _make_request(self, url: str) -> requests.Response:
        """
        Make an HTTP request with rate limiting.

        Args:
            url: Request URL

        Returns:
            Response object

        Raises:
            requests.RequestException: On request failure
        """
        self._rate_limit()
        logger.debug(f"Requesting: {url}")

        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response

    def _extract_listings(self, html: str) -> List[Dict[str, Any]]:
        """
        Extract listing data from HTML.

        Args:
            html: HTML content

        Returns:
            List of listing dictionaries
        """
        listings = []

        # Primary pattern - matches FINN's embedded listing JSON format
        # Format: {"type":"realestate","id":"...","main_search_key":"...","heading":"...","location":"...",...}
        pattern = r'\{"type":"realestate","id":"(\d+)","main_search_key":"([^"]+)","heading":"([^"]+)","location":"([^"]*)"'

        seen_ids = set()
        for match in re.finditer(pattern, html):
            listing_id = match.group(1)
            if listing_id in seen_ids:
                continue
            seen_ids.add(listing_id)

            listing = {
                "id": listing_id,
                "main_search_key": match.group(2),
                "heading": match.group(3),
                "location": match.group(4),
            }

            # Try to extract more data from the surrounding JSON context
            # Find the full listing object by searching from the match position
            start_pos = match.start()
            # Find the corresponding closing structure (next listing or end)
            end_marker = html.find('{"type":"realestate"', start_pos + 10)
            if end_marker == -1:
                end_marker = start_pos + 2000  # Reasonable limit

            listing_chunk = html[start_pos:end_marker]

            # Extract image info
            image_match = re.search(
                r'"image":\{"url":"([^"]+)"[^}]*"path":"([^"]*)"[^}]*"height":(\d+)[^}]*"width":(\d+)',
                listing_chunk
            )
            if image_match:
                listing["image"] = {
                    "url": image_match.group(1),
                    "path": image_match.group(2),
                    "height": int(image_match.group(3)),
                    "width": int(image_match.group(4)),
                }

            # Extract flags (like "private" for private sellers)
            flags_match = re.search(r'"flags":\[([^\]]*)\]', listing_chunk)
            if flags_match:
                flags_str = flags_match.group(1)
                listing["flags"] = re.findall(r'"([^"]+)"', flags_str)
            else:
                listing["flags"] = []

            listings.append(listing)

        logger.debug(f"Extracted {len(listings)} listings from HTML")
        return listings

    def _extract_total_count(self, html: str) -> int:
        """
        Extract total result count from HTML.

        Args:
            html: HTML content

        Returns:
            Total count of listings
        """
        # Try to find in meta description
        match = re.search(r'Du finner (\d+[\s\d]*)', html)
        if match:
            count_str = match.group(1).replace(" ", "").replace("\xa0", "")
            return int(count_str)

        # Try alternative patterns
        match = re.search(r'(\d+)\s*(?:treff|boliger|leieobjekter)', html, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return 0

    def _parse_listing(self, data: Dict[str, Any], search_type: SearchType) -> ListingBasic:
        """
        Parse listing data into ListingBasic object.

        Args:
            data: Raw listing data
            search_type: Type of search (lettings, homes, etc.)

        Returns:
            ListingBasic object
        """
        image = None
        if "image" in data:
            img_data = data["image"]
            image = Image(
                url=img_data.get("url", ""),
                path=img_data.get("path"),
                width=img_data.get("width"),
                height=img_data.get("height"),
                aspect_ratio=img_data.get("aspect_ratio"),
            )

        listing_url = f"{self.BASE_URL}/realestate/{search_type.value}/ad.html?finnkode={data['id']}"

        return ListingBasic(
            id=data["id"],
            heading=data.get("heading", ""),
            location=data.get("location", ""),
            search_type=search_type.value,
            url=listing_url,
            image=image,
            price=data.get("price"),
            price_total=data.get("price_total"),
            price_suggestion=data.get("price_suggestion"),
            area=data.get("area"),
            bedrooms=data.get("bedrooms"),
            property_type=data.get("property_type"),
            flags=data.get("flags", []),
            timestamp=data.get("timestamp"),
            labels=data.get("labels", []),
        )

    def _build_search_url(
        self,
        search_type: SearchType,
        page: int = 1,
        **filters
    ) -> str:
        """
        Build search URL with filters.

        Args:
            search_type: Type of search
            page: Page number (1-indexed)
            **filters: Search filters

        Returns:
            Complete search URL
        """
        base_path = self.SEARCH_ENDPOINTS[search_type]
        params = {}

        if page > 1:
            params["page"] = page

        # Location filter - can be single value or list
        if filters.get("location"):
            loc = filters["location"]
            if isinstance(loc, str):
                params["location"] = loc
            elif isinstance(loc, list):
                # Multiple locations use repeated parameters
                params["location"] = loc

        # Price filters
        if filters.get("price_from"):
            params["price_from"] = filters["price_from"]
        if filters.get("price_to"):
            params["price_to"] = filters["price_to"]

        # Area filters (square meters)
        if filters.get("area_from"):
            params["area_from"] = filters["area_from"]
        if filters.get("area_to"):
            params["area_to"] = filters["area_to"]

        # Bedrooms filter
        if filters.get("no_of_bedrooms_from"):
            params["no_of_bedrooms_from"] = filters["no_of_bedrooms_from"]
        if filters.get("no_of_bedrooms_to"):
            params["no_of_bedrooms_to"] = filters["no_of_bedrooms_to"]

        # Property type filter
        if filters.get("property_type"):
            pt = filters["property_type"]
            if isinstance(pt, list):
                params["property_type"] = pt
            else:
                params["property_type"] = pt

        # Sort option
        if filters.get("sort"):
            params["sort"] = filters["sort"]

        # Published date filter
        if filters.get("published"):
            params["published"] = filters["published"]  # 1=today, 2=3days, 3=week, etc.

        # For lettings only
        if search_type == SearchType.LETTINGS:
            if filters.get("rent_from"):
                params["rent_from"] = filters["rent_from"]
            if filters.get("rent_to"):
                params["rent_to"] = filters["rent_to"]

        # Keyword search
        if filters.get("q"):
            params["q"] = filters["q"]

        url = f"{self.BASE_URL}{base_path}"
        if params:
            # Handle multi-value parameters
            param_list = []
            for key, value in params.items():
                if isinstance(value, list):
                    for v in value:
                        param_list.append(f"{key}={v}")
                else:
                    param_list.append(f"{key}={value}")
            url += "?" + "&".join(param_list)

        return url

    def search(
        self,
        search_type: SearchType,
        page: int = 1,
        **filters
    ) -> SearchResults:
        """
        Search for real estate listings.

        Args:
            search_type: Type of search (lettings, homes, etc.)
            page: Page number (1-indexed)
            **filters: Search filters including:
                - location: Location code (e.g., "0.20061" for Oslo)
                - price_from/price_to: Price range
                - area_from/area_to: Area in square meters
                - no_of_bedrooms_from/no_of_bedrooms_to: Bedroom count
                - property_type: Property type code(s)
                - sort: Sort option
                - q: Keyword search

        Returns:
            SearchResults object

        Example:
            >>> client = FinnClient()
            >>> results = client.search(
            ...     SearchType.LETTINGS,
            ...     location="0.20061",
            ...     price_from=5000,
            ...     price_to=15000
            ... )
            >>> print(f"Found {results.total_count} listings")
        """
        url = self._build_search_url(search_type, page=page, **filters)
        logger.info(f"Searching: {url}")

        response = self._make_request(url)
        html = response.text

        listings_data = self._extract_listings(html)
        total_count = self._extract_total_count(html)

        listings = [
            self._parse_listing(data, search_type)
            for data in listings_data
        ]

        # Estimate pagination
        per_page = 51  # FINN typically shows ~51 listings per page
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 0

        return SearchResults(
            items=listings,
            total_count=total_count,
            page=page,
            per_page=per_page,
            has_next_page=page < total_pages,
            search_type=search_type.value,
            filters_applied=filters,
        )

    def search_lettings(self, page: int = 1, **filters) -> SearchResults:
        """
        Search for rental listings (Til leie).

        Args:
            page: Page number
            **filters: Search filters

        Returns:
            SearchResults object
        """
        return self.search(SearchType.LETTINGS, page=page, **filters)

    def search_homes(self, page: int = 1, **filters) -> SearchResults:
        """
        Search for homes for sale (Bolig til salgs).

        Args:
            page: Page number
            **filters: Search filters

        Returns:
            SearchResults object
        """
        return self.search(SearchType.HOMES, page=page, **filters)

    def search_newbuildings(self, page: int = 1, **filters) -> SearchResults:
        """
        Search for new construction projects.

        Args:
            page: Page number
            **filters: Search filters

        Returns:
            SearchResults object
        """
        return self.search(SearchType.NEWBUILDINGS, page=page, **filters)

    def search_leisure(self, page: int = 1, **filters) -> SearchResults:
        """
        Search for vacation homes (Fritidsbolig).

        Args:
            page: Page number
            **filters: Search filters

        Returns:
            SearchResults object
        """
        return self.search(SearchType.LEISURE, page=page, **filters)

    def search_all_pages(
        self,
        search_type: SearchType,
        max_pages: Optional[int] = None,
        **filters
    ) -> Iterator[ListingBasic]:
        """
        Iterator that yields all listings across all pages.

        Args:
            search_type: Type of search
            max_pages: Maximum number of pages to fetch (None for all)
            **filters: Search filters

        Yields:
            ListingBasic objects

        Example:
            >>> client = FinnClient()
            >>> for listing in client.search_all_pages(
            ...     SearchType.LETTINGS,
            ...     location="0.20061",
            ...     max_pages=5
            ... ):
            ...     print(listing.heading)
        """
        page = 1
        while True:
            results = self.search(search_type, page=page, **filters)

            for listing in results.items:
                yield listing

            if not results.has_next_page:
                break

            if max_pages and page >= max_pages:
                break

            page += 1

    def get_listing_details(self, listing_id: str) -> Optional[ListingDetails]:
        """
        Get detailed information for a specific listing.

        Args:
            listing_id: The FINN listing ID (finnkode)

        Returns:
            ListingDetails object or None if not found

        Example:
            >>> client = FinnClient()
            >>> details = client.get_listing_details("448603189")
            >>> if details:
            ...     print(details.heading, details.price_total)
        """
        # Try lettings first, then homes
        for search_type in [SearchType.LETTINGS, SearchType.HOMES, SearchType.LEISURE]:
            url = f"{self.BASE_URL}/realestate/{search_type.value}/ad.html?finnkode={listing_id}"

            try:
                response = self._make_request(url)
                html = response.text

                # Check if we got the right page
                if f'finnkode={listing_id}' not in html and listing_id not in html:
                    continue

                return self._parse_listing_details(html, listing_id, search_type)

            except requests.RequestException as e:
                logger.debug(f"Failed to fetch {search_type.value} listing: {e}")

        logger.warning(f"Listing {listing_id} not found")
        return None

    def _parse_listing_details(
        self,
        html: str,
        listing_id: str,
        search_type: SearchType
    ) -> Optional[ListingDetails]:
        """
        Parse detailed listing information from HTML.

        Args:
            html: HTML content
            listing_id: Listing ID
            search_type: Type of listing

        Returns:
            ListingDetails object or None
        """
        details = {
            "id": listing_id,
            "search_type": search_type.value,
        }

        # Extract heading
        heading_match = re.search(r'<h1[^>]*>([^<]+)</h1>', html)
        if heading_match:
            details["heading"] = heading_match.group(1).strip()

        # Extract address/location
        address_match = re.search(r'"streetAddress"\s*:\s*"([^"]+)"', html)
        if address_match:
            details["address"] = address_match.group(1)

        # Extract postal code and city
        postal_match = re.search(r'"postalCode"\s*:\s*"(\d+)"', html)
        if postal_match:
            details["postal_code"] = postal_match.group(1)

        city_match = re.search(r'"addressLocality"\s*:\s*"([^"]+)"', html)
        if city_match:
            details["city"] = city_match.group(1)

        # Extract coordinates
        lat_match = re.search(r'"latitude"\s*:\s*([0-9.]+)', html)
        lng_match = re.search(r'"longitude"\s*:\s*([0-9.]+)', html)
        if lat_match:
            details["latitude"] = float(lat_match.group(1))
        if lng_match:
            details["longitude"] = float(lng_match.group(1))

        # Extract price
        price_match = re.search(r'"price"\s*:\s*(\d+)', html)
        if price_match:
            details["price_total"] = int(price_match.group(1))

        # Extract description
        desc_match = re.search(r'"description"\s*:\s*"([^"]+)"', html)
        if desc_match:
            details["description"] = desc_match.group(1)

        # Extract images
        images = []
        img_pattern = r'"image"\s*:\s*"(https://images\.finncdn\.no[^"]+)"'
        for match in re.finditer(img_pattern, html):
            images.append(Image(url=match.group(1)))
        details["images"] = images

        # Build location string
        location_parts = []
        if details.get("address"):
            location_parts.append(details["address"])
        if details.get("postal_code"):
            location_parts.append(details["postal_code"])
        if details.get("city"):
            location_parts.append(details["city"])
        details["location"] = ", ".join(location_parts)

        # Build URL
        details["url"] = f"{self.BASE_URL}/realestate/{search_type.value}/ad.html?finnkode={listing_id}"

        return ListingDetails(**{k: v for k, v in details.items() if v is not None})

    def get_location_suggestions(self, query: str) -> List[Dict[str, Any]]:
        """
        Get location suggestions for a search query.

        This is useful for finding the correct location code.

        Args:
            query: Search query (city, area name, etc.)

        Returns:
            List of location suggestions

        Example:
            >>> client = FinnClient()
            >>> suggestions = client.get_location_suggestions("Oslo")
            >>> for s in suggestions:
            ...     print(s['label'], s['value'])
        """
        # FINN uses a location API endpoint
        url = f"{self.BASE_URL}/realestate/lettings/xhr"
        params = {"term": query}

        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, json.JSONDecodeError) as e:
            logger.error(f"Location lookup failed: {e}")
            return []

    def close(self):
        """Close the session."""
        self.session.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def listing_to_dict(listing: Union[ListingBasic, ListingDetails]) -> Dict[str, Any]:
    """
    Convert a listing object to a dictionary.

    Args:
        listing: Listing object

    Returns:
        Dictionary representation
    """
    result = asdict(listing)

    # Convert nested dataclasses
    if listing.image:
        result["image"] = asdict(listing.image)

    if isinstance(listing, ListingDetails) and listing.images:
        result["images"] = [asdict(img) for img in listing.images]

    return result


# Example usage and testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="FINN.no Real Estate Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Search for rentals in Oslo
    python finn_api.py --type lettings --location oslo

    # Search for homes for sale in Bergen, price range 3-5 million
    python finn_api.py --type homes --location bergen --price-from 3000000 --price-to 5000000

    # Search with custom location code
    python finn_api.py --type lettings --location-code 0.20061

    # Get listing details
    python finn_api.py --details 448603189

    # Demo mode
    python finn_api.py --demo

Common location codes:
    Oslo: 0.20061
    Bergen: 0.20003
    Trondheim: 0.20016
    Stavanger: 0.20012
    Kristiansand: 0.20011
        """
    )

    parser.add_argument("--type", choices=["lettings", "homes", "leisure", "newbuildings"],
                        default="lettings", help="Type of search")
    parser.add_argument("--location", help="Location name (oslo, bergen, etc.)")
    parser.add_argument("--location-code", help="FINN location code (e.g., 0.20061)")
    parser.add_argument("--price-from", type=int, help="Minimum price")
    parser.add_argument("--price-to", type=int, help="Maximum price")
    parser.add_argument("--bedrooms", type=int, help="Minimum bedrooms")
    parser.add_argument("--area-from", type=int, help="Minimum area (sqm)")
    parser.add_argument("--page", type=int, default=1, help="Page number")
    parser.add_argument("--details", help="Get details for listing ID")
    parser.add_argument("--output", help="Output file (JSON)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--demo", action="store_true", help="Show demo data")

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Demo mode
    if args.demo:
        print("=" * 80)
        print("FINN.NO REAL ESTATE SCRAPER - DEMO MODE")
        print("=" * 80)
        print("""
This scraper extracts real estate listings from FINN.no, Norway's largest
online marketplace.

ARCHITECTURE:
- FINN.no embeds listing data as JSON within HTML responses
- Listings are in a "docs" array with id, heading, location, image, etc.
- Pagination via ?page=N parameter
- Location filtering via FINN's location taxonomy codes

SEARCH TYPES:
- lettings: Rental properties (Bolig til leie)
- homes: Properties for sale (Bolig til salgs)
- newbuildings: New construction projects
- leisure: Vacation homes (Fritidsbolig)
- plots: Building plots
- commercial: Commercial real estate

SAMPLE LISTING DATA:
""")
        sample = ListingBasic(
            id="448603189",
            heading="Moderne 2-roms leilighet i sentrum",
            location="Karl Johans gate 1, Oslo",
            search_type="lettings",
            url="https://www.finn.no/realestate/lettings/ad.html?finnkode=448603189",
            image=Image(
                url="https://images.finncdn.no/dynamic/default/item/448603189/example.jpg",
                width=1600,
                height=1067,
            ),
            price="12 500 kr/mnd",
            price_total=12500,
            area="45 m\u00b2",
            bedrooms=1,
            flags=["verified"],
        )
        print(json.dumps(listing_to_dict(sample), indent=2, ensure_ascii=False))
        print("""

USAGE:
    from finn_api import FinnClient, SearchType

    client = FinnClient()

    # Search rentals in Oslo
    results = client.search_lettings(location="0.20061")
    print(f"Found {results.total_count} rentals")

    for listing in results.items[:5]:
        print(f"- {listing.heading}: {listing.price}")

    # Get all listings (paginated)
    for listing in client.search_all_pages(SearchType.LETTINGS, max_pages=3):
        print(listing.id, listing.heading)

FILTERS:
    - location: FINN location code
    - price_from / price_to: Price range
    - area_from / area_to: Area in square meters
    - no_of_bedrooms_from: Minimum bedrooms
    - property_type: Property type code
    - sort: PUBLISHED_DESC, PRICE_ASC, etc.
""")
        exit(0)

    # Run actual search
    client = FinnClient()

    try:
        if args.details:
            print(f"Fetching details for listing {args.details}...")
            details = client.get_listing_details(args.details)

            if details:
                print(f"\nTitle: {details.heading}")
                print(f"Location: {details.location}")
                print(f"Price: {details.price_total}")
                print(f"URL: {details.url}")
                if details.description:
                    print(f"\nDescription:\n{details.description[:500]}...")

                if args.output:
                    with open(args.output, "w", encoding="utf-8") as f:
                        json.dump(listing_to_dict(details), f, indent=2, ensure_ascii=False)
                    print(f"\nSaved to {args.output}")
            else:
                print("Listing not found")
        else:
            # Build search parameters
            search_params = {}

            if args.location:
                loc_code = LOCATION_CODES.get(args.location.lower())
                if loc_code:
                    search_params["location"] = loc_code
                else:
                    print(f"Unknown location '{args.location}', using as-is")
                    search_params["location"] = args.location
            elif args.location_code:
                search_params["location"] = args.location_code

            if args.price_from:
                search_params["price_from"] = args.price_from
            if args.price_to:
                search_params["price_to"] = args.price_to
            if args.bedrooms:
                search_params["no_of_bedrooms_from"] = args.bedrooms
            if args.area_from:
                search_params["area_from"] = args.area_from

            # Select search type
            search_type = {
                "lettings": SearchType.LETTINGS,
                "homes": SearchType.HOMES,
                "leisure": SearchType.LEISURE,
                "newbuildings": SearchType.NEWBUILDINGS,
            }.get(args.type, SearchType.LETTINGS)

            print(f"Searching {args.type}...")
            results = client.search(search_type, page=args.page, **search_params)

            print(f"\nFound {results.total_count} listings (page {results.page})")
            print("-" * 80)

            for listing in results.items[:10]:
                print(f"ID: {listing.id}")
                print(f"  Title: {listing.heading}")
                print(f"  Location: {listing.location}")
                if listing.price_total:
                    print(f"  Price: {listing.price_total:,} kr")
                print(f"  URL: {listing.url}")
                print()

            if args.output:
                output_data = {
                    "total_count": results.total_count,
                    "page": results.page,
                    "has_next_page": results.has_next_page,
                    "search_type": results.search_type,
                    "items": [listing_to_dict(item) for item in results.items]
                }
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(output_data, f, indent=2, ensure_ascii=False)
                print(f"Results saved to {args.output}")

    except requests.RequestException as e:
        print(f"Error: {e}")

    finally:
        client.close()
