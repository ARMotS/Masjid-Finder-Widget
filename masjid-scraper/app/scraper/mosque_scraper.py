"""Async scraper for MasjidBoardLive.com mosque and prayer time data."""

import asyncio
import re
from datetime import datetime, date, time, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Any
from contextlib import asynccontextmanager

import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from app.config import settings
from app.db.models import Mosque, PrayerTime, ScrapeLog
from app.scraper.regions import get_region_codes, get_region_slug, is_valid_region


# Prayer name aliases for normalization
PRAYER_ALIASES = {
    "zuhr": "dhuhr",
    "zohr": "dhuhr",
    "esha": "isha",
    "ishaa": "isha",
    "fajr": "fajr",
    "sunrise": "sunrise",
    "dhuhr": "dhuhr",
    "asr": "asr",
    "maghrib": "maghrib",
    "isha": "isha",
}

# South Africa Standard Time offset (UTC+2)
SAST_OFFSET = timedelta(hours=2)


class MasjidBoardScraper:
    """
    Async scraper for MasjidBoardLive.com.
    
    Scrapes mosque information and prayer times, storing them in PostgreSQL.
    Uses httpx for async HTTP requests and BeautifulSoup for parsing.
    """
    
    def __init__(self, db_session: AsyncSession):
        """
        Initialize the scraper.
        
        Args:
            db_session: SQLAlchemy async session for database operations
        """
        self.db_session = db_session
        self.client: Optional[httpx.AsyncClient] = None
        self.base_url = settings.BASE_URL
        self.request_delay = settings.REQUEST_DELAY_SECONDS
        
    async def __aenter__(self):
        """Context manager entry - create HTTP client."""
        self.client = httpx.AsyncClient(
            headers={"User-Agent": "MasjidDataCollector/1.0"},
            timeout=30.0,
            follow_redirects=True,
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - close HTTP client."""
        if self.client:
            await self.client.aclose()
    
    async def scrape_all_regions(self) -> Tuple[int, List[str]]:
        """
        Scrape all configured regions.
        
        Returns:
            Tuple of (total_mosques_scraped, list_of_errors)
        """
        total_count = 0
        all_errors = []
        
        for region_code in get_region_codes():
            try:
                count = await self.scrape_region(region_code)
                total_count += count
            except Exception as e:
                error_msg = f"Failed to scrape region {region_code}: {str(e)}"
                all_errors.append(error_msg)
                print(error_msg)
        
        return total_count, all_errors
    
    async def scrape_region(self, region_code: str) -> int:
        """
        Scrape a single region and log to scrape_logs table.
        
        Args:
            region_code: Region code to scrape (e.g., 'jhbc')
            
        Returns:
            Number of mosques scraped
        """
        if not is_valid_region(region_code):
            raise ValueError(f"Invalid region code: {region_code}")
        
        # Create scrape log entry
        log = ScrapeLog(
            started_at=datetime.now(timezone.utc),
            status="running",
            region=region_code,
        )
        self.db_session.add(log)
        await self.db_session.commit()
        await self.db_session.refresh(log)
        
        errors = []
        mosques_scraped = 0
        
        try:
            # Discover all mosque URLs in this region
            mosque_urls = await self._discover_mosques(region_code)
            
            # Scrape each mosque
            for url in mosque_urls:
                try:
                    await self._scrape_single_mosque(url, region_code)
                    mosques_scraped += 1
                    await asyncio.sleep(self.request_delay)  # Rate limiting
                except Exception as e:
                    error_msg = f"Error scraping {url}: {str(e)}"
                    errors.append(error_msg)
                    print(error_msg)
            
            # Update log as completed
            log.finished_at = datetime.now(timezone.utc)
            log.status = "completed"
            log.mosques_scraped = mosques_scraped
            log.errors = "\n".join(errors) if errors else None
            
        except Exception as e:
            # Update log as failed
            log.finished_at = datetime.now(timezone.utc)
            log.status = "failed"
            log.errors = str(e)
            raise
        finally:
            await self.db_session.commit()
        
        return mosques_scraped
    
    async def _discover_mosques(self, region_code: str) -> List[str]:
        """
        Discover all mosque page URLs for a region by paginating through listing pages.
        
        Args:
            region_code: Region code to discover mosques in
            
        Returns:
            List of mosque page URLs
            
        Note:
            CSS selectors are illustrative and need to be adjusted based on
            the actual DOM structure of MasjidBoardLive.com
        """
        region_slug = get_region_slug(region_code)
        mosque_urls = []
        page = 1
        
        while True:
            # Construct region listing page URL
            # NOTE: This URL pattern is assumed and needs verification
            url = f"{self.base_url}/mosques/{region_slug}?page={page}"
            
            try:
                response = await self.client.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Find mosque links on the page
                # NOTE: These selectors are illustrative - adjust based on actual DOM
                mosque_links = soup.select("a.mosque-link, .mosque-item a, .mosque-list-item a")
                
                if not mosque_links:
                    break  # No more mosques, exit pagination
                
                for link in mosque_links:
                    href = link.get("href")
                    if href:
                        # Convert relative URLs to absolute
                        if href.startswith("/"):
                            href = f"{self.base_url}{href}"
                        mosque_urls.append(href)
                
                # Check if there's a next page
                # NOTE: Adjust selector based on actual pagination structure
                next_button = soup.select_one("a.next-page, .pagination .next")
                if not next_button:
                    break
                
                page += 1
                await asyncio.sleep(self.request_delay)
                
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    break  # No more pages
                raise
        
        return mosque_urls
    
    async def _scrape_single_mosque(self, url: str, region_code: str) -> None:
        """
        Scrape a single mosque page and save to database.
        
        Args:
            url: Full URL to the mosque page
            region_code: Region code for this mosque
        """
        response = await self.client.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        
        # Parse mosque information
        mosque_data = await self._parse_mosque_info(soup, url, region_code)
        
        # Upsert mosque
        mosque_id = await self._upsert_mosque(mosque_data)
        
        # Parse and upsert prayer times
        prayer_data = await self._parse_prayer_times(soup)
        if prayer_data:
            await self._upsert_prayer_times(mosque_id, prayer_data)
    
    async def _parse_mosque_info(self, soup: BeautifulSoup, url: str, region: str) -> Dict[str, Any]:
        """
        Extract mosque information from a mosque page.
        
        Args:
            soup: BeautifulSoup object of the mosque page
            url: URL of the mosque page
            region: Region code
            
        Returns:
            Dict with mosque data (name, address, phone, website, etc.)
            
        Note:
            CSS selectors are illustrative and need to be adjusted based on
            the actual DOM structure of MasjidBoardLive.com
        """
        data = {"region": region}
        
        # Extract name
        # NOTE: Adjust selector based on actual DOM
        name_elem = soup.select_one("h1.mosque-name, .masjid-title, h1")
        data["name"] = name_elem.get_text(strip=True) if name_elem else "Unknown Mosque"
        
        # Extract address
        # NOTE: Adjust selector based on actual DOM
        address_elem = soup.select_one(".mosque-address, .address, [itemprop='address']")
        data["address"] = address_elem.get_text(strip=True) if address_elem else None
        
        # Extract phone
        # NOTE: Adjust selector based on actual DOM
        phone_elem = soup.select_one(".mosque-phone, .phone, [itemprop='telephone']")
        data["phone"] = phone_elem.get_text(strip=True) if phone_elem else None
        
        # Extract website
        # NOTE: Adjust selector based on actual DOM
        website_elem = soup.select_one("a.mosque-website, .website a, [itemprop='url']")
        data["website"] = website_elem.get("href") if website_elem else None
        
        # Extract keywords/tags
        # NOTE: Adjust selector based on actual DOM
        keywords_elems = soup.select(".mosque-tags .tag, .keywords .keyword")
        data["keywords"] = ", ".join([k.get_text(strip=True) for k in keywords_elems]) if keywords_elems else None
        
        # Extract coordinates
        coords = await self._extract_coordinates(soup)
        data["latitude"] = coords[0]
        data["longitude"] = coords[1]
        
        return data
    
    async def _extract_coordinates(self, soup: BeautifulSoup) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract latitude and longitude from the page.
        
        Tries two strategies:
        1. Google Maps iframe src parameter
        2. data-lat and data-lng attributes
        
        Args:
            soup: BeautifulSoup object of the mosque page
            
        Returns:
            Tuple of (latitude, longitude) or (None, None)
        """
        # Strategy 1: Google Maps iframe
        iframe = soup.select_one("iframe[src*='google.com/maps']")
        if iframe:
            src = iframe.get("src", "")
            # Try to extract coordinates from URL patterns like !3d-26.123!2d28.456
            match = re.search(r"!3d([-\d.]+)!2d([-\d.]+)", src)
            if match:
                return float(match.group(1)), float(match.group(2))
            # Try q=lat,lng pattern
            match = re.search(r"[?&]q=([-\d.]+),([-\d.]+)", src)
            if match:
                return float(match.group(1)), float(match.group(2))
        
        # Strategy 2: data attributes
        lat_elem = soup.select_one("[data-lat], [data-latitude]")
        lng_elem = soup.select_one("[data-lng], [data-longitude]")
        if lat_elem and lng_elem:
            try:
                lat = float(lat_elem.get("data-lat") or lat_elem.get("data-latitude"))
                lng = float(lng_elem.get("data-lng") or lng_elem.get("data-longitude"))
                return lat, lng
            except (ValueError, TypeError):
                pass
        
        return None, None
    
    async def _parse_prayer_times(self, soup: BeautifulSoup) -> Optional[Dict[str, Any]]:
        """
        Extract prayer times from a mosque page.
        
        Tries two strategies:
        1. Structured table with rows for each prayer
        2. Data attributes on elements
        
        Args:
            soup: BeautifulSoup object of the mosque page
            
        Returns:
            Dict with prayer times (date, fajr, sunrise, dhuhr, asr, maghrib, isha, iqamah_times)
            or None if no times found
            
        Note:
            CSS selectors are illustrative and need to be adjusted based on
            the actual DOM structure of MasjidBoardLive.com
        """
        # Get current date in SAST timezone
        sast_now = datetime.now(timezone.utc) + SAST_OFFSET
        prayer_data = {
            "date": sast_now.date(),
            "iqamah_times": {}
        }
        
        # Strategy 1: Parse from table structure
        # NOTE: Adjust selectors based on actual DOM
        table = soup.select_one(".prayer-times-table, .timetable, table.prayers")
        if table:
            rows = table.select("tr")
            for row in rows:
                cells = row.select("td, th")
                if len(cells) >= 2:
                    prayer_name = cells[0].get_text(strip=True).lower()
                    # Normalize prayer name using aliases
                    prayer_name = PRAYER_ALIASES.get(prayer_name, prayer_name)
                    
                    # Extract adhan time
                    adhan_time_text = cells[1].get_text(strip=True)
                    adhan_time = self._parse_time(adhan_time_text)
                    
                    if prayer_name in ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]:
                        prayer_data[prayer_name] = adhan_time
                    
                    # Extract iqamah time if present
                    if len(cells) >= 3:
                        iqamah_time_text = cells[2].get_text(strip=True)
                        iqamah_time = self._parse_time(iqamah_time_text)
                        if iqamah_time:
                            prayer_data["iqamah_times"][prayer_name] = iqamah_time.strftime("%H:%M")
        
        # Strategy 2: Parse from data attributes (fallback)
        # NOTE: Adjust selectors based on actual DOM
        if not any(prayer_data.get(p) for p in ["fajr", "dhuhr", "asr", "maghrib", "isha"]):
            for prayer in ["fajr", "sunrise", "dhuhr", "asr", "maghrib", "isha"]:
                elem = soup.select_one(f"[data-{prayer}], [data-prayer='{prayer}']")
                if elem:
                    time_text = elem.get(f"data-{prayer}") or elem.get_text(strip=True)
                    prayer_data[prayer] = self._parse_time(time_text)
        
        # Check if we found any prayer times
        if not any(prayer_data.get(p) for p in ["fajr", "dhuhr", "asr", "maghrib", "isha"]):
            return None
        
        return prayer_data
    
    def _parse_time(self, time_str: str) -> Optional[time]:
        """
        Parse a time string into a time object.
        
        Args:
            time_str: Time string (e.g., "05:30", "5:30 AM", "17:45")
            
        Returns:
            time object or None if parsing fails
        """
        if not time_str:
            return None
        
        time_str = time_str.strip()
        
        # Try different time formats
        formats = [
            "%H:%M",
            "%I:%M %p",
            "%I:%M%p",
            "%H:%M:%S",
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(time_str, fmt)
                return dt.time()
            except ValueError:
                continue
        
        return None
    
    async def _upsert_mosque(self, data: Dict[str, Any]) -> int:
        """
        Insert or update a mosque by (name, region) unique key.
        
        Args:
            data: Mosque data dict
            
        Returns:
            Mosque ID
        """
        stmt = insert(Mosque).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_mosque_name_region",
            set_={
                "address": stmt.excluded.address,
                "latitude": stmt.excluded.latitude,
                "longitude": stmt.excluded.longitude,
                "phone": stmt.excluded.phone,
                "website": stmt.excluded.website,
                "keywords": stmt.excluded.keywords,
                "updated_at": datetime.now(timezone.utc),
            }
        ).returning(Mosque.id)
        
        result = await self.db_session.execute(stmt)
        await self.db_session.commit()
        mosque_id = result.scalar_one()
        return mosque_id
    
    async def _upsert_prayer_times(self, mosque_id: int, data: Dict[str, Any]) -> None:
        """
        Insert or update prayer times by (mosque_id, date) unique key.
        
        Args:
            mosque_id: Mosque ID
            data: Prayer times data dict
        """
        data["mosque_id"] = mosque_id
        
        stmt = insert(PrayerTime).values(**data)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_prayer_time_mosque_date",
            set_={
                "fajr": stmt.excluded.fajr,
                "sunrise": stmt.excluded.sunrise,
                "dhuhr": stmt.excluded.dhuhr,
                "asr": stmt.excluded.asr,
                "maghrib": stmt.excluded.maghrib,
                "isha": stmt.excluded.isha,
                "iqamah_times": stmt.excluded.iqamah_times,
                "updated_at": datetime.now(timezone.utc),
            }
        )
        
        await self.db_session.execute(stmt)
        await self.db_session.commit()
