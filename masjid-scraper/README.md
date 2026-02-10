# Masjid Finder Widget - Backend Service

A complete backend service that scrapes mosque data and prayer times from MasjidBoardLive.com, stores it in PostgreSQL, and exposes REST API endpoints designed to power Android (Jetpack Compose Glance) and iOS (WidgetKit) mosque finder widgets.

## 🏗️ Architecture

```
┌─────────────────┐
│  MasjidBoard    │
│   Live.com      │
└────────┬────────┘
         │ HTTP
         ▼
┌─────────────────┐
│  Async Scraper  │
│  (httpx +       │
│  BeautifulSoup) │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │
│   Database      │
│  (mosques,      │
│  prayer_times,  │
│  scrape_logs)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   FastAPI       │
│   REST API      │
│  (Core + Widget)│
└────────┬────────┘
         │ HTTP/JSON
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│Android │ │  iOS   │
│ Widget │ │ Widget │
│(Glance)│ │(WidgetKit)
└────────┘ └────────┘
```

## ✨ Features

- **Async Web Scraping**: Scrapes mosque data from MasjidBoardLive.com using httpx and BeautifulSoup
- **Scheduled Jobs**: APScheduler runs periodic scraping every 6 hours (configurable)
- **PostgreSQL Storage**: Stores mosques, prayer times, and scrape audit logs
- **REST API**: FastAPI-based endpoints for core operations and widget-specific needs
- **Geolocation Search**: Haversine formula for finding nearby mosques
- **Widget Optimization**: Endpoints designed for minimal network requests from widgets
- **Docker Support**: Full containerization with docker-compose
- **Rate Limiting**: Configurable delays between requests to respect server resources

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Python 3.12+ for local development

### Using Docker Compose (Recommended)

1. **Clone the repository**
   ```bash
   git clone https://github.com/ARMotS/Masjid-Finder-Widget.git
   cd Masjid-Finder-Widget/masjid-scraper
   ```

2. **Start the services**
   ```bash
   docker-compose up -d
   ```

   This will:
   - Start PostgreSQL database
   - Run database migrations (schema.sql)
   - Start the FastAPI application on port 8000
   - Begin scheduled scraping every 6 hours

3. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health
   - Root Endpoint: http://localhost:8000

### Local Development

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your database credentials
   ```

4. **Start PostgreSQL** (if not using Docker)
   ```bash
   # Using local PostgreSQL or Docker:
   docker run -d --name masjid-postgres \
     -e POSTGRES_USER=masjid_user \
     -e POSTGRES_PASSWORD=masjid_pass \
     -e POSTGRES_DB=masjid_db \
     -p 5432:5432 \
     postgres:16-alpine
   ```

5. **Run migrations**
   ```bash
   psql -h localhost -U masjid_user -d masjid_db -f schema.sql
   ```

6. **Start the application**
   ```bash
   uvicorn app.main:app --reload
   ```

## 📡 API Endpoints

### Core API (`/api`)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/mosques` | List mosques with filtering (`?region=`, `?search=`) and pagination |
| GET | `/api/mosques/{mosque_id}` | Get single mosque by ID |
| GET | `/api/mosques/{mosque_id}/prayer-times` | Get prayer times for a date (`?date=YYYY-MM-DD`) |
| GET | `/api/prayer-times/today` | All mosques' prayer times for today (`?region=` filter) |
| GET | `/api/regions` | List all supported region codes and names |
| GET | `/api/stats` | Mosque count grouped by region |
| GET | `/api/scrape/logs` | Recent scrape job audit logs |
| POST | `/api/scrape` | Manually trigger scraping all regions |
| POST | `/api/scrape/{region_code}` | Manually trigger scraping a specific region |

### Widget API (`/api/widget`)

| Method | Endpoint | Description | Widget Use |
|--------|----------|-------------|------------|
| GET | `/api/widget/mosques/nearby` | Find mosques near location using Haversine formula<br>Params: `lat`, `lng`, `radius_km`, `limit` | All sizes - discovery |
| GET | `/api/widget/mosques/{mosque_id}/next-prayer` | Get next prayer with countdown (SAST timezone aware)<br>Returns: prayer name, time, iqamah, countdown | Small (2×2) |
| GET | `/api/widget/mosques/{mosque_id}/timetable` | Get mosque info + full timetable in one call | Medium (4×2), Large (4×4) |
| GET | `/api/widget/nearby-timetables` | Get multiple nearby mosques with timetables<br>Params: `lat`, `lng`, `radius_km`, `limit` | Large (4×4) - swipeable cards |

## 📱 Widget-to-API Mapping

| Widget Size | Android/iOS Size | API Endpoints Used | Purpose |
|-------------|------------------|---------------------|---------|
| **Small** | 2×2 | `nearby` + `next-prayer` | Show closest mosque + countdown to next prayer |
| **Medium** | 4×2 | `nearby` + `timetable` | Show mosque + full prayer schedule for today |
| **Large** | 4×4 | `nearby-timetables` | Swipeable cards with multiple nearby mosques + their schedules |

## ⚙️ Configuration

All configuration is done via environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Async PostgreSQL connection URL | `postgresql+asyncpg://user:password@localhost:5432/masjid_db` |
| `SYNC_DATABASE_URL` | Sync PostgreSQL connection URL (for migrations) | `postgresql://user:password@localhost:5432/masjid_db` |
| `DEBUG` | Enable debug mode (verbose logging) | `False` |
| `SCRAPE_INTERVAL_HOURS` | Hours between automatic scraping runs | `6` |
| `REQUEST_DELAY_SECONDS` | Delay between HTTP requests (rate limiting) | `1.5` |
| `BASE_URL` | Base URL for MasjidBoardLive.com | `https://masjidboardlive.com` |

## 🗺️ Supported Regions

| Code | Region | URL Slug |
|------|--------|----------|
| `jhbc` | Johannesburg Central | `johannesburg-central` |
| `jhbs` | Johannesburg South | `johannesburg-south` |
| `jhbn` | Johannesburg North | `johannesburg-north` |
| `dbn` | Durban | `durban` |
| `pta` | Pretoria | `pretoria` |
| `cpt` | Cape Town | `cape-town` |
| `pe` | Port Elizabeth | `port-elizabeth` |
| `pmb` | Pietermaritzburg | `pietermaritzburg` |

## 🔍 Important Notes

### CSS Selectors
The scraper uses CSS selectors to extract data from MasjidBoardLive.com. **These selectors are illustrative and need to be adjusted** based on the actual DOM structure of the website. Before running the scraper, inspect the website and update the selectors in `app/scraper/mosque_scraper.py`.

Key methods to update:
- `_discover_mosques()` - mosque listing page selectors
- `_parse_mosque_info()` - mosque detail page selectors
- `_parse_prayer_times()` - prayer time table selectors
- `_extract_coordinates()` - map/location selectors

### Robots.txt Compliance
Before deploying, check MasjidBoardLive.com's `robots.txt` to ensure scraping is permitted. Adjust the User-Agent and rate limiting settings accordingly.

### South Africa Timezone
The `/api/widget/mosques/{mosque_id}/next-prayer` endpoint accounts for South Africa Standard Time (SAST, UTC+2) when calculating countdowns.

## 🗄️ Database Schema

### Mosques Table
- Stores mosque information with unique constraint on `(name, region)`
- Indexed on `region` and `name` for fast queries
- Coordinates stored as `DECIMAL(10,8)` and `DECIMAL(11,8)` for precision

### Prayer Times Table
- Links to mosques via foreign key with cascade delete
- Unique constraint on `(mosque_id, date)` prevents duplicates
- `iqamah_times` stored as JSONB for flexibility
- Indexed on `(mosque_id, date)` and `date` for efficient queries

### Scrape Logs Table
- Audit trail for all scraping jobs
- Tracks start time, end time, status, and errors
- Helps monitor scraping health and troubleshoot issues

## 🛠️ Development

### Project Structure
```
masjid-scraper/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app + APScheduler
│   ├── config.py                # Pydantic settings
│   ├── db/
│   │   ├── __init__.py
│   │   ├── session.py           # Async SQLAlchemy setup
│   │   └── models.py            # ORM models
│   ├── scraper/
│   │   ├── __init__.py
│   │   ├── mosque_scraper.py    # Core scraping logic
│   │   └── regions.py           # Region definitions
│   └── api/
│       ├── __init__.py
│       ├── routes.py            # Core REST API
│       └── widget_routes.py     # Widget-specific API
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── schema.sql
└── README.md
```

### Running Tests
```bash
# TODO: Add pytest configuration and tests
pytest
```

### Code Quality
```bash
# Format code
black app/

# Lint code
ruff check app/

# Type checking
mypy app/
```

## 📊 Roadmap

| Phase | Component | Status |
|-------|-----------|--------|
| Phase 1 | Backend Scraper | ✅ Complete |
| Phase 2 | REST API Layer | ✅ Complete |
| Phase 2 | Android Widget (Glance) | 🔲 Planned |
| Phase 2 | iOS Widget (WidgetKit) | 🔲 Planned |
| Phase 3 | Push Notifications | 🔲 Future |
| Phase 3 | User Preferences | 🔲 Future |
| Phase 3 | Custom Reminders | 🔲 Future |

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is for educational purposes. Please respect MasjidBoardLive.com's terms of service and robots.txt when scraping.

## 🙏 Acknowledgments

- Data source: [MasjidBoardLive.com](https://masjidboardlive.com)
- Built with [FastAPI](https://fastapi.tiangolo.com/)
- Database: [PostgreSQL](https://www.postgresql.org/)
- Scraping: [httpx](https://www.python-httpx.org/) + [BeautifulSoup](https://www.crummy.com/software/BeautifulSoup/)
