# Japanese Car Data Scraper

Scrapes used car listings from [japanesecartrade.com](https://www.japanesecartrade.com/zenmobilityjapan/stock-list.html) using Selenium and saves structured data to a CSV file. Designed to handle large multi-page catalogs (~1,300+ pages) with resume support and automatic browser restarts.

## Features

- Headless Chrome scraping via Selenium
- Auto-resume: detects existing CSV rows and picks up from the last completed page
- Browser restarts every 100 pages to prevent memory leaks
- Failed page tracking — saves page numbers that errored to `failed_pages.txt`
- Extracts boolean feature flags (sunroof, leather, navigation, 4WD, airbag, ABS, camera)

## Output

Results are written to `car_data.csv` with the following columns:

| Column | Description |
|---|---|
| `ref_id` | Unique listing reference ID |
| `name` | Full car name |
| `chassis_code` | Chassis/model code |
| `year` | Manufacture year |
| `price_usd` | Asking price in USD |
| `price_jpy` | Asking price in JPY |
| `mileage_km` | Odometer reading (km) |
| `engine_cc` | Engine displacement (cc) |
| `fuel` | Fuel type (Petrol / Diesel) |
| `transmission` | Transmission type |
| `steering` | Steering side (Right/Left Hand Drive) |
| `vehicle_type` | Body type (SUV, Sedan, etc.) |
| `options` | Raw options string |
| `has_sunroof` | 1 if sun roof listed in options |
| `has_leather` | 1 if leather seats listed |
| `has_navigation` | 1 if navigation system listed |
| `has_alloy_wheels` | 1 if alloy wheels listed |
| `has_4wd` | 1 if 4WD mentioned |
| `has_airbag` | 1 if airbag mentioned |
| `has_abs` | 1 if ABS mentioned |
| `has_camera` | 1 if camera mentioned |
| `location` | Dealer location and shipping port |
| `date_listed` | Date the listing was posted |
| `detail_url` | Link to the full listing page |

## Requirements

- Python 3.10+
- Google Chrome + matching `chromedriver` installed at `/usr/bin/chromedriver`

Install Python dependencies:

```bash
pip install selenium pandas psycopg2-binary python-dotenv
```

## Setup

1. Clone the repo and create a virtual environment:

```bash
python -m venv cardataenv
source cardataenv/bin/activate
pip install selenium pandas psycopg2-binary python-dotenv
```

2. Create a `.env` file in the project root (required if using a downstream PostgreSQL load step):

```env
AIVEN_HOST=your-host
AIVEN_PORT=your-port
AIVEN_DB=your-database
AIVEN_USER=your-user
AIVEN_PASSWORD=your-password
```

3. Confirm `chromedriver` is available:

```bash
chromedriver --version
```

## Usage

```bash
python scrap.py
```

The scraper will:
1. Check `car_data.csv` for existing rows and resume from the appropriate page if found.
2. Scrape all pages, printing progress to stdout.
3. Write results to `car_data.csv` (append if resuming, overwrite if starting fresh).
4. Write any failed page numbers to `failed_pages.txt`.

## Configuration

Edit the constants at the top of [scrap.py](scrap.py):

| Variable | Default | Description |
|---|---|---|
| `CHROMEDRIVER_PATH` | `/usr/bin/chromedriver` | Path to chromedriver binary |
| `BASE_URL` | japanesecartrade.com stock list | Target URL |
| `OUTPUT_FILE` | `car_data.csv` | Output CSV path |
| `FAILED_PAGES_FILE` | `failed_pages.txt` | Failed pages log |
| `SLEEP_BETWEEN_PAGES` | `1.5` | Delay between pages (seconds) |
| `RESTART_EVERY_PAGES` | `100` | Browser restart interval |

## Project Structure

```
japanese-car-data-scrapping/
├── scrap.py            # Main scraper script
├── car_data.csv        # Output data (generated on run)
├── failed_pages.txt    # Pages that failed (generated if errors occur)
├── requirements.txt    # Pinned dependency list
├── .env                # Database credentials (not committed)
└── cardataenv/         # Python virtual environment
```
