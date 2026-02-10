-- Masjid Finder Widget Database Schema

-- Mosques Table
CREATE TABLE mosques (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    address     TEXT,
    latitude    DECIMAL(10, 8),
    longitude   DECIMAL(11, 8),
    phone       VARCHAR(50),
    website     VARCHAR(500),
    keywords    TEXT,
    region      VARCHAR(50) NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW(),
    updated_at  TIMESTAMP DEFAULT NOW(),
    UNIQUE(name, region)
);

-- Prayer Times Table
CREATE TABLE prayer_times (
    id            SERIAL PRIMARY KEY,
    mosque_id     INTEGER NOT NULL REFERENCES mosques(id) ON DELETE CASCADE,
    date          DATE NOT NULL,
    fajr          TIME,
    sunrise       TIME,
    dhuhr         TIME,
    asr           TIME,
    maghrib       TIME,
    isha          TIME,
    iqamah_times  JSONB,
    created_at    TIMESTAMP DEFAULT NOW(),
    updated_at    TIMESTAMP DEFAULT NOW(),
    UNIQUE(mosque_id, date)
);

-- Scrape Logs Table
CREATE TABLE scrape_logs (
    id              SERIAL PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL DEFAULT NOW(),
    finished_at     TIMESTAMP,
    status          VARCHAR(50) DEFAULT 'running',
    region          VARCHAR(50),
    mosques_scraped INTEGER DEFAULT 0,
    errors          TEXT
);

-- Indexes for performance
CREATE INDEX idx_mosques_region ON mosques(region);
CREATE INDEX idx_mosques_name ON mosques(name);
CREATE INDEX idx_prayer_times_mosque_date ON prayer_times(mosque_id, date);
CREATE INDEX idx_prayer_times_date ON prayer_times(date);
