"""FastAPI application with scheduled scraping and REST API endpoints."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import engine, get_db
from app.db.models import Base
from app.api.routes import router as core_router
from app.api.widget_routes import router as widget_router
from app.scraper.mosque_scraper import MasjidBoardScraper
from app.scraper.regions import is_valid_region


# Global scheduler instance
scheduler = AsyncIOScheduler()


async def scheduled_scrape_all():
    """
    Scheduled job to scrape all regions.
    
    This function is called by APScheduler at regular intervals.
    """
    print(f"Starting scheduled scrape at {settings.SCRAPE_INTERVAL_HOURS}h interval...")
    
    # Create a new database session for this job
    from app.db.session import async_session_factory
    
    async with async_session_factory() as session:
        async with MasjidBoardScraper(session) as scraper:
            try:
                total, errors = await scraper.scrape_all_regions()
                print(f"Scheduled scrape completed: {total} mosques scraped")
                if errors:
                    print(f"Errors encountered: {len(errors)}")
                    for error in errors[:5]:  # Print first 5 errors
                        print(f"  - {error}")
            except Exception as e:
                print(f"Scheduled scrape failed: {str(e)}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    
    Startup:
    - Create database tables
    - Start APScheduler for periodic scraping
    
    Shutdown:
    - Stop scheduler
    """
    # Startup
    print("Starting up...")
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created/verified")
    
    # Start scheduler
    scheduler.add_job(
        scheduled_scrape_all,
        "interval",
        hours=settings.SCRAPE_INTERVAL_HOURS,
        id="scrape_all_regions",
        replace_existing=True,
    )
    scheduler.start()
    print(f"Scheduler started (interval: {settings.SCRAPE_INTERVAL_HOURS}h)")
    
    yield
    
    # Shutdown
    print("Shutting down...")
    scheduler.shutdown()
    print("Scheduler stopped")


# Create FastAPI app
app = FastAPI(
    title="Masjid Finder Widget API",
    description="Backend service for scraping mosque data and providing REST API for Android/iOS widgets",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
# NOTE: In production, configure allowed_origins to specific domains only
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Tighten this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(core_router)
app.include_router(widget_router)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Masjid Finder Widget API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "core_api": "/api",
            "widget_api": "/api/widget",
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy"}


@app.post("/api/scrape")
async def trigger_scrape_all(db: AsyncSession = Depends(get_db)):
    """
    Manually trigger a scrape of all regions.
    
    Returns:
        Summary of scraping results
    """
    async with MasjidBoardScraper(db) as scraper:
        total, errors = await scraper.scrape_all_regions()
    
    return {
        "status": "completed",
        "mosques_scraped": total,
        "errors": errors,
        "error_count": len(errors),
    }


@app.post("/api/scrape/{region_code}")
async def trigger_scrape_region(
    region_code: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Manually trigger a scrape of a specific region.
    
    Path Parameters:
    - region_code: Region code to scrape (e.g., 'jhbc')
    
    Returns:
        Summary of scraping results for the region
    """
    if not is_valid_region(region_code):
        raise HTTPException(status_code=400, detail=f"Invalid region code: {region_code}")
    
    async with MasjidBoardScraper(db) as scraper:
        count = await scraper.scrape_region(region_code)
    
    return {
        "status": "completed",
        "region": region_code,
        "mosques_scraped": count,
    }
