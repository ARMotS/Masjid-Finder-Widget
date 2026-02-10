"""Widget-specific API endpoints optimized for Android and iOS widgets."""

from datetime import datetime, date, time, timedelta
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Mosque, PrayerTime


router = APIRouter(prefix="/api/widget", tags=["widget"])


# South Africa Standard Time offset (UTC+2)
SAST_OFFSET = timedelta(hours=2)


def _format_countdown(seconds: Optional[int]) -> Optional[str]:
    """
    Format countdown seconds into human-readable string.
    
    Args:
        seconds: Number of seconds
        
    Returns:
        Formatted string like "2h 15m" or "45m"
    """
    if seconds is None or seconds < 0:
        return None
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _get_sast_now() -> datetime:
    """Get current time in South Africa Standard Time (UTC+2)."""
    return datetime.utcnow() + SAST_OFFSET


@router.get("/mosques/nearby")
async def get_nearby_mosques(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(10, ge=0.1, le=100, description="Search radius in kilometers"),
    limit: int = Query(10, ge=1, le=50, description="Maximum number of results"),
    db: AsyncSession = Depends(get_db)
):
    """
    Find mosques near a location using Haversine formula.
    
    Powers: All widget sizes - mosque discovery
    
    Query Parameters:
    - lat: Latitude of search center
    - lng: Longitude of search center
    - radius_km: Search radius in kilometers (default: 10, max: 100)
    - limit: Maximum results to return (default: 10, max: 50)
    
    Returns:
        List of nearby mosques sorted by distance with distance_km field
    """
    # Haversine formula in PostgreSQL to calculate distance
    # Returns distance in kilometers
    haversine_formula = text(f"""
        (6371 * acos(
            cos(radians(:lat)) * 
            cos(radians(latitude)) * 
            cos(radians(longitude) - radians(:lng)) + 
            sin(radians(:lat)) * 
            sin(radians(latitude))
        ))
    """)
    
    # Build query with distance calculation
    query = (
        select(
            Mosque,
            haversine_formula.label("distance_km")
        )
        .where(Mosque.latitude.isnot(None))
        .where(Mosque.longitude.isnot(None))
        .having(text("distance_km") <= radius_km)
        .order_by(text("distance_km"))
        .limit(limit)
    )
    
    result = await db.execute(
        query,
        {"lat": lat, "lng": lng}
    )
    rows = result.all()
    
    return {
        "location": {"latitude": lat, "longitude": lng},
        "radius_km": radius_km,
        "mosques": [
            {
                "id": mosque.id,
                "name": mosque.name,
                "address": mosque.address,
                "latitude": float(mosque.latitude),
                "longitude": float(mosque.longitude),
                "phone": mosque.phone,
                "website": mosque.website,
                "region": mosque.region,
                "distance_km": round(distance, 2),
            }
            for mosque, distance in rows
        ],
        "count": len(rows),
    }


@router.get("/mosques/{mosque_id}/next-prayer")
async def get_next_prayer(
    mosque_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get the next upcoming prayer and countdown for a mosque.
    
    Powers: Small widget (2×2) countdown display
    
    Path Parameters:
    - mosque_id: Unique mosque identifier
    
    Returns:
        Next prayer name, time, iqamah time, and countdown
    """
    # Verify mosque exists
    result = await db.execute(select(Mosque).where(Mosque.id == mosque_id))
    mosque = result.scalar_one_or_none()
    if not mosque:
        raise HTTPException(status_code=404, detail="Mosque not found")
    
    # Get current SAST time
    now = _get_sast_now()
    today = now.date()
    current_time = now.time()
    
    # Get today's prayer times
    result = await db.execute(
        select(PrayerTime)
        .where(PrayerTime.mosque_id == mosque_id)
        .where(PrayerTime.date == today)
    )
    prayer_time = result.scalar_one_or_none()
    
    # If no prayer times for today, try tomorrow
    if not prayer_time:
        tomorrow = today + timedelta(days=1)
        result = await db.execute(
            select(PrayerTime)
            .where(PrayerTime.mosque_id == mosque_id)
            .where(PrayerTime.date == tomorrow)
        )
        prayer_time = result.scalar_one_or_none()
        if not prayer_time:
            raise HTTPException(status_code=404, detail="No prayer times available")
        # Return tomorrow's Fajr
        return {
            "mosque_id": mosque_id,
            "mosque_name": mosque.name,
            "next_prayer": "fajr",
            "next_prayer_time": prayer_time.fajr.strftime("%H:%M") if prayer_time.fajr else None,
            "next_iqamah_time": prayer_time.iqamah_times.get("fajr") if prayer_time.iqamah_times else None,
            "countdown_seconds": None,
            "countdown_display": None,
        }
    
    # Check each prayer in order to find the next one
    prayers = [
        ("fajr", prayer_time.fajr),
        ("sunrise", prayer_time.sunrise),
        ("dhuhr", prayer_time.dhuhr),
        ("asr", prayer_time.asr),
        ("maghrib", prayer_time.maghrib),
        ("isha", prayer_time.isha),
    ]
    
    for prayer_name, prayer_time_obj in prayers:
        if prayer_time_obj and prayer_time_obj > current_time:
            # Calculate countdown
            prayer_datetime = datetime.combine(today, prayer_time_obj)
            countdown_seconds = int((prayer_datetime - now).total_seconds())
            
            # Get iqamah time if available
            iqamah_time = None
            if prayer_time.iqamah_times and prayer_name in prayer_time.iqamah_times:
                iqamah_time = prayer_time.iqamah_times[prayer_name]
            
            return {
                "mosque_id": mosque_id,
                "mosque_name": mosque.name,
                "next_prayer": prayer_name,
                "next_prayer_time": prayer_time_obj.strftime("%H:%M"),
                "next_iqamah_time": iqamah_time,
                "countdown_seconds": countdown_seconds,
                "countdown_display": _format_countdown(countdown_seconds),
            }
    
    # All prayers passed today, return tomorrow's Fajr
    tomorrow = today + timedelta(days=1)
    result = await db.execute(
        select(PrayerTime)
        .where(PrayerTime.mosque_id == mosque_id)
        .where(PrayerTime.date == tomorrow)
    )
    tomorrow_prayer = result.scalar_one_or_none()
    
    if tomorrow_prayer and tomorrow_prayer.fajr:
        prayer_datetime = datetime.combine(tomorrow, tomorrow_prayer.fajr)
        countdown_seconds = int((prayer_datetime - now).total_seconds())
        
        iqamah_time = None
        if tomorrow_prayer.iqamah_times and "fajr" in tomorrow_prayer.iqamah_times:
            iqamah_time = tomorrow_prayer.iqamah_times["fajr"]
        
        return {
            "mosque_id": mosque_id,
            "mosque_name": mosque.name,
            "next_prayer": "fajr",
            "next_prayer_time": tomorrow_prayer.fajr.strftime("%H:%M"),
            "next_iqamah_time": iqamah_time,
            "countdown_seconds": countdown_seconds,
            "countdown_display": _format_countdown(countdown_seconds),
        }
    
    raise HTTPException(status_code=404, detail="No upcoming prayer times available")


@router.get("/mosques/{mosque_id}/timetable")
async def get_mosque_timetable(
    mosque_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get mosque info and full prayer timetable in a single call.
    
    Powers: Medium widget (4×2) and Large widget (4×4)
    
    Path Parameters:
    - mosque_id: Unique mosque identifier
    
    Returns:
        Mosque details with today's complete prayer timetable
    """
    # Get mosque
    result = await db.execute(select(Mosque).where(Mosque.id == mosque_id))
    mosque = result.scalar_one_or_none()
    if not mosque:
        raise HTTPException(status_code=404, detail="Mosque not found")
    
    # Get today's prayer times
    today = date.today()
    result = await db.execute(
        select(PrayerTime)
        .where(PrayerTime.mosque_id == mosque_id)
        .where(PrayerTime.date == today)
    )
    prayer_time = result.scalar_one_or_none()
    
    if not prayer_time:
        raise HTTPException(status_code=404, detail="No prayer times available for today")
    
    return {
        "mosque": {
            "id": mosque.id,
            "name": mosque.name,
            "address": mosque.address,
            "latitude": float(mosque.latitude) if mosque.latitude else None,
            "longitude": float(mosque.longitude) if mosque.longitude else None,
            "phone": mosque.phone,
            "region": mosque.region,
        },
        "timetable": {
            "date": prayer_time.date.isoformat(),
            "prayers": {
                "fajr": {
                    "adhan": prayer_time.fajr.strftime("%H:%M") if prayer_time.fajr else None,
                    "iqamah": prayer_time.iqamah_times.get("fajr") if prayer_time.iqamah_times else None,
                },
                "sunrise": {
                    "time": prayer_time.sunrise.strftime("%H:%M") if prayer_time.sunrise else None,
                },
                "dhuhr": {
                    "adhan": prayer_time.dhuhr.strftime("%H:%M") if prayer_time.dhuhr else None,
                    "iqamah": prayer_time.iqamah_times.get("dhuhr") if prayer_time.iqamah_times else None,
                },
                "asr": {
                    "adhan": prayer_time.asr.strftime("%H:%M") if prayer_time.asr else None,
                    "iqamah": prayer_time.iqamah_times.get("asr") if prayer_time.iqamah_times else None,
                },
                "maghrib": {
                    "adhan": prayer_time.maghrib.strftime("%H:%M") if prayer_time.maghrib else None,
                    "iqamah": prayer_time.iqamah_times.get("maghrib") if prayer_time.iqamah_times else None,
                },
                "isha": {
                    "adhan": prayer_time.isha.strftime("%H:%M") if prayer_time.isha else None,
                    "iqamah": prayer_time.iqamah_times.get("isha") if prayer_time.iqamah_times else None,
                },
            },
        },
    }


@router.get("/nearby-timetables")
async def get_nearby_timetables(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius_km: float = Query(10, ge=0.1, le=100, description="Search radius in kilometers"),
    limit: int = Query(3, ge=1, le=10, description="Maximum number of mosques"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get nearby mosques with their full timetables in one call.
    
    Powers: Large widget (4×4) swipeable mosque cards
    
    Query Parameters:
    - lat: Latitude of search center
    - lng: Longitude of search center
    - radius_km: Search radius in kilometers (default: 10, max: 100)
    - limit: Maximum mosques to return (default: 3, max: 10)
    
    Returns:
        List of nearby mosques with their complete prayer timetables
    """
    today = date.today()
    
    # Haversine formula for distance calculation
    haversine_formula = text(f"""
        (6371 * acos(
            cos(radians(:lat)) * 
            cos(radians(latitude)) * 
            cos(radians(longitude) - radians(:lng)) + 
            sin(radians(:lat)) * 
            sin(radians(latitude))
        ))
    """)
    
    # Get nearby mosques with their prayer times
    query = (
        select(
            Mosque,
            PrayerTime,
            haversine_formula.label("distance_km")
        )
        .join(PrayerTime, Mosque.id == PrayerTime.mosque_id)
        .where(Mosque.latitude.isnot(None))
        .where(Mosque.longitude.isnot(None))
        .where(PrayerTime.date == today)
        .having(text("distance_km") <= radius_km)
        .order_by(text("distance_km"))
        .limit(limit)
    )
    
    result = await db.execute(
        query,
        {"lat": lat, "lng": lng}
    )
    rows = result.all()
    
    return {
        "location": {"latitude": lat, "longitude": lng},
        "radius_km": radius_km,
        "date": today.isoformat(),
        "mosques": [
            {
                "mosque": {
                    "id": mosque.id,
                    "name": mosque.name,
                    "address": mosque.address,
                    "latitude": float(mosque.latitude),
                    "longitude": float(mosque.longitude),
                    "phone": mosque.phone,
                    "region": mosque.region,
                    "distance_km": round(distance, 2),
                },
                "timetable": {
                    "prayers": {
                        "fajr": {
                            "adhan": pt.fajr.strftime("%H:%M") if pt.fajr else None,
                            "iqamah": pt.iqamah_times.get("fajr") if pt.iqamah_times else None,
                        },
                        "sunrise": {
                            "time": pt.sunrise.strftime("%H:%M") if pt.sunrise else None,
                        },
                        "dhuhr": {
                            "adhan": pt.dhuhr.strftime("%H:%M") if pt.dhuhr else None,
                            "iqamah": pt.iqamah_times.get("dhuhr") if pt.iqamah_times else None,
                        },
                        "asr": {
                            "adhan": pt.asr.strftime("%H:%M") if pt.asr else None,
                            "iqamah": pt.iqamah_times.get("asr") if pt.iqamah_times else None,
                        },
                        "maghrib": {
                            "adhan": pt.maghrib.strftime("%H:%M") if pt.maghrib else None,
                            "iqamah": pt.iqamah_times.get("maghrib") if pt.iqamah_times else None,
                        },
                        "isha": {
                            "adhan": pt.isha.strftime("%H:%M") if pt.isha else None,
                            "iqamah": pt.iqamah_times.get("isha") if pt.iqamah_times else None,
                        },
                    },
                },
            }
            for mosque, pt, distance in rows
        ],
        "count": len(rows),
    }
