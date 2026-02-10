# Masjid Finder Widget

A comprehensive mosque finder solution featuring a backend service that scrapes mosque data and prayer times, and provides REST API endpoints designed to power Android (Jetpack Compose Glance) and iOS (WidgetKit) widgets.

## 🏗️ Project Structure

This repository contains:

- **`masjid-scraper/`** - Backend service (Phase 1 + Phase 2 API layer)
  - FastAPI-based REST API
  - Async web scraper for MasjidBoardLive.com
  - PostgreSQL database for mosque and prayer time data
  - Docker containerization with docker-compose
  - Scheduled scraping with APScheduler

## 🚀 Quick Start

1. **Navigate to the backend service**
   ```bash
   cd masjid-scraper
   ```

2. **Start with Docker Compose**
   ```bash
   docker-compose up -d
   ```

3. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/health

For detailed documentation, see [masjid-scraper/README.md](masjid-scraper/README.md)

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

## 📱 Widget Sizes & Features

| Widget Size | Android/iOS | Features | API Endpoints |
|-------------|-------------|----------|---------------|
| **Small (2×2)** | Glance / WidgetKit | Closest mosque + countdown to next prayer | `nearby`, `next-prayer` |
| **Medium (4×2)** | Glance / WidgetKit | Mosque info + full daily prayer schedule | `nearby`, `timetable` |
| **Large (4×4)** | Glance / WidgetKit | Swipeable cards with multiple mosques | `nearby-timetables` |

## 🗺️ Supported Regions

- Johannesburg (Central, South, North)
- Durban
- Pretoria
- Cape Town
- Port Elizabeth
- Pietermaritzburg

## 🤝 Contributing

Contributions are welcome! Please see the [backend README](masjid-scraper/README.md) for development setup and guidelines.

## 📄 License

This project is for educational purposes. Please respect MasjidBoardLive.com's terms of service and robots.txt when scraping.
