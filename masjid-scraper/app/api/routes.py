"""Core REST API endpoints for mosques, prayer times, and stats."""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.models import Mosque, PrayerTime, ScrapeLog
from app.scraper.regions import REGIONS, is_valid_region


router = APIRouter(prefix="/api", tags=["core"])


@router.get("/mosques")
async def list_mosques(
    region: Optional[str] = Query(None, description="Filter by region code"),
    search: Optional[str] = Query(None, description="Search by mosque name"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(100, ge=1, le=500, description="Pagination limit"),
    db: AsyncSession = Depends(get_db)
):
    """
    List mosques with optional filtering and pagination.
    
    Query Parameters:
    - region: Filter by region code (e.g., 'jhbc')
    - search: Search by mosque name (case-insensitive partial match)
    - skip: Number of records to skip (pagination)
    - limit: Maximum number of records to return
    
    Returns:
        List of mosques with metadata
    """
    query = select(Mosque)
    
    # Apply filters
    if region:
        if not is_valid_region(region):
            raise HTTPException(status_code=400, detail=f"Invalid region code: {region}")
        query = query.where(Mosque.region == region)
    
    if search:
        query = query.where(Mosque.name.ilike(f"%{search}%"))
    
    # Apply pagination
    query = query.offset(skip).limit(limit).order_by(Mosque.name)
    
    result = await db.execute(query)
    mosques = result.scalars().all()
    
    return {
        "mosques": [
            {
                "id": m.id,
                "name": m.name,
                "address": m.address,
                "latitude": float(m.latitude) if m.latitude else None,
                "longitude": float(m.longitude) if m.longitude else None,
                "phone": m.phone,
                "website": m.website,
                "keywords": m.keywords,
                "region": m.region,
            }
            for m in mosques
        ],
        "count": len(mosques),
        "skip": skip,
        "limit": limit,
    }


@router.get("/mosques/{mosque_id}")
async def get_mosque(
    mosque_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single mosque by ID.
    
    Path Parameters:
    - mosque_id: Unique mosque identifier
    
    Returns:
        Mosque details including contact info and location
    """
    result = await db.execute(select(Mosque).where(Mosque.id == mosque_id))
    mosque = result.scalar_one_or_none()
    
    if not mosque:
        raise HTTPException(status_code=404, detail="Mosque not found")
    
    return {
        "id": mosque.id,
        "name": mosque.name,
        "address": mosque.address,
        "latitude": float(mosque.latitude) if mosque.latitude else None,
        "longitude": float(mosque.longitude) if mosque.longitude else None,
        "phone": mosque.phone,
        "website": mosque.website,
        "keywords": mosque.keywords,
        "region": mosque.region,
        "created_at": mosque.created_at.isoformat(),
        "updated_at": mosque.updated_at.isoformat(),
    }


@router.get("/mosques/{mosque_id}/prayer-times")
async def get_mosque_prayer_times(
    mosque_id: int,
    date_param: Optional[str] = Query(None, alias="date", description="Date in YYYY-MM-DD format (defaults to today)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get prayer times for a specific mosque and date.
    
    Path Parameters:
    - mosque_id: Unique mosque identifier
    
    Query Parameters:
    - date: Date in YYYY-MM-DD format (defaults to today)
    
    Returns:
        Prayer times (adhan and iqamah) for the specified date
    """
    # Verify mosque exists
    result = await db.execute(select(Mosque).where(Mosque.id == mosque_id))
    mosque = result.scalar_one_or_none()
    if not mosque:
        raise HTTPException(status_code=404, detail="Mosque not found")
    
    # Parse date
    target_date = date.today()
    if date_param:
        try:
            target_date = date.fromisoformat(date_param)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Get prayer times
    result = await db.execute(
        select(PrayerTime)
        .where(PrayerTime.mosque_id == mosque_id)
        .where(PrayerTime.date == target_date)
    )
    prayer_time = result.scalar_one_or_none()
    
    if not prayer_time:
        raise HTTPException(status_code=404, detail="Prayer times not found for this date")
    
    return {
        "mosque_id": mosque_id,
        "mosque_name": mosque.name,
        "date": prayer_time.date.isoformat(),
        "fajr": prayer_time.fajr.strftime("%H:%M") if prayer_time.fajr else None,
        "sunrise": prayer_time.sunrise.strftime("%H:%M") if prayer_time.sunrise else None,
        "dhuhr": prayer_time.dhuhr.strftime("%H:%M") if prayer_time.dhuhr else None,
        "asr": prayer_time.asr.strftime("%H:%M") if prayer_time.asr else None,
        "maghrib": prayer_time.maghrib.strftime("%H:%M") if prayer_time.maghrib else None,
        "isha": prayer_time.isha.strftime("%H:%M") if prayer_time.isha else None,
        "iqamah_times": prayer_time.iqamah_times,
    }


@router.get("/prayer-times/today")
async def get_today_prayer_times(
    region: Optional[str] = Query(None, description="Filter by region code"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get today's prayer times for all mosques, optionally filtered by region.
    
    Query Parameters:
    - region: Filter by region code (e.g., 'jhbc')
    
    Returns:
        List of mosques with their prayer times for today
    """
    today = date.today()
    
    query = (
        select(Mosque, PrayerTime)
        .join(PrayerTime, Mosque.id == PrayerTime.mosque_id)
        .where(PrayerTime.date == today)
    )
    
    if region:
        if not is_valid_region(region):
            raise HTTPException(status_code=400, detail=f"Invalid region code: {region}")
        query = query.where(Mosque.region == region)
    
    query = query.order_by(Mosque.name)
    
    result = await db.execute(query)
    rows = result.all()
    
    return {
        "date": today.isoformat(),
        "prayer_times": [
            {
                "mosque_id": mosque.id,
                "mosque_name": mosque.name,
                "region": mosque.region,
                "fajr": pt.fajr.strftime("%H:%M") if pt.fajr else None,
                "sunrise": pt.sunrise.strftime("%H:%M") if pt.sunrise else None,
                "dhuhr": pt.dhuhr.strftime("%H:%M") if pt.dhuhr else None,
                "asr": pt.asr.strftime("%H:%M") if pt.asr else None,
                "maghrib": pt.maghrib.strftime("%H:%M") if pt.maghrib else None,
                "isha": pt.isha.strftime("%H:%M") if pt.isha else None,
                "iqamah_times": pt.iqamah_times,
            }
            for mosque, pt in rows
        ],
        "count": len(rows),
    }


@router.get("/regions")
async def list_regions():
    """
    List all supported region codes and display names.
    
    Returns:
        List of regions with codes, names, and slugs
    """
    return {
        "regions": [
            {
                "code": code,
                "name": info["name"],
                "slug": info["slug"],
            }
            for code, info in REGIONS.items()
        ]
    }


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    """
    Get statistics about mosques grouped by region.
    
    Returns:
        Mosque counts per region and total count
    """
    # Count mosques per region
    result = await db.execute(
        select(Mosque.region, func.count(Mosque.id))
        .group_by(Mosque.region)
    )
    region_counts = {row[0]: row[1] for row in result.all()}
    
    # Total count
    result = await db.execute(select(func.count(Mosque.id)))
    total = result.scalar_one()
    
    return {
        "total_mosques": total,
        "by_region": [
            {
                "region_code": code,
                "region_name": REGIONS[code]["name"],
                "mosque_count": region_counts.get(code, 0),
            }
            for code in REGIONS.keys()
        ]
    }


@router.get("/scrape/logs")
async def get_scrape_logs(
    limit: int = Query(50, ge=1, le=500, description="Maximum number of logs to return"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent scrape job audit logs.
    
    Query Parameters:
    - limit: Maximum number of logs to return
    
    Returns:
        List of scrape log entries with job details
    """
    result = await db.execute(
        select(ScrapeLog)
        .order_by(ScrapeLog.started_at.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    
    return {
        "logs": [
            {
                "id": log.id,
                "started_at": log.started_at.isoformat(),
                "finished_at": log.finished_at.isoformat() if log.finished_at else None,
                "status": log.status,
                "region": log.region,
                "mosques_scraped": log.mosques_scraped,
                "errors": log.errors,
            }
            for log in logs
        ],
        "count": len(logs),
    }
