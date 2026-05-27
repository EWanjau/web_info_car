from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

import re
import csv
import time
import os
from urllib.parse import urljoin


# =========================
# CONFIGURATION
# =========================

BASE_URL = "https://www.beforward.jp/stocklist/steering=Right/mfg_year_from=2018/view_cnt=25/page=1/sar=steering/from_stocklist=1/kmode=and/"
OUTPUT_FILE = "../data/raw/car_data.csv"
FAILED_PAGES_FILE = "failed_pages.txt"

PAGE_SIZE = 25
WAIT_TIMEOUT = 8
SLEEP_BETWEEN_PAGES = 0.2
RESTART_EVERY_PAGES = 250

# Set to 5 for testing. Use None for all pages.
MAX_PAGES = None

FIELDNAMES = [
    "ref_id",
    "name",
    "chassis_code",
    "year",
    "price_usd",
    "price_jpy",
    "mileage_km",
    "engine_cc",
    "fuel",
    "transmission",
    "steering",
    "vehicle_type",
    "options",
    "has_sunroof",
    "has_leather",
    "has_navigation",
    "has_alloy_wheels",
    "has_4wd",
    "has_airbag",
    "has_abs",
    "has_camera",
    "location",
    "date_listed",
    "detail_url",
]


# =========================
# DRIVER SETUP
# =========================

def create_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/google-chrome"

    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1366,768")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-notifications")
    chrome_options.add_argument("--disable-popup-blocking")
    chrome_options.add_argument("--blink-settings=imagesEnabled=false")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.plugins": 2,
        "profile.managed_default_content_settings.popups": 2,
        "profile.managed_default_content_settings.geolocation": 2,
        "profile.managed_default_content_settings.notifications": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    chrome_options.add_experimental_option("prefs", prefs)
    chrome_options.page_load_strategy = "eager"

    service = Service()
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(20)

    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {
            "urls": [
                "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.svg",
                "*.css", "*.woff", "*.woff2", "*.ttf",
                "*google-analytics*", "*googletagmanager*", "*doubleclick*",
                "*facebook*", "*twitter*", "*pagesense*", "*channel.io*",
                "*ads*", "*analytics*",
            ]
        })
    except Exception:
        pass

    return driver


# =========================
# HELPERS
# =========================

def clean_number(value):
    return re.sub(r"[^\d]", "", value or "")


def extract_first(patterns, text, default=""):
    for pattern in patterns:
        match = re.search(pattern, text or "", re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return default


def extract_ref_id(text, detail_url=""):
    ref_id = extract_first([
        r"\bRef\.?\s*No\.?\s*[:#]?\s*([A-Z0-9-]+)",
        r"\bRef\s*[:#]?\s*([A-Z0-9-]+)",
        r"\b([A-Z]{2}\d{6,})\b",
        r"\b([A-Z]{1,3}\d{5,})\b",
    ], text)

    if ref_id:
        return ref_id

    return extract_first([
        r"/([A-Z]{2}\d{6,})(?:/|$)",
        r"stock_no=([A-Z0-9-]+)",
    ], detail_url)


def extract_car_name(full_text):
    """
    Fixes the common bug where the first link text is the ref id.
    We scan visible lines and choose the first line that looks like a real vehicle title.
    """
    lines = [line.strip() for line in (full_text or "").splitlines() if line.strip()]

    makers = (
        "TOYOTA|NISSAN|HONDA|MAZDA|SUBARU|MITSUBISHI|SUZUKI|DAIHATSU|ISUZU|"
        "BMW|AUDI|MERCEDES|BENZ|VOLKSWAGEN|VW|VOLVO|LEXUS|LAND ROVER|"
        "RANGE ROVER|JEEP|FORD|CHEVROLET|HYUNDAI|KIA|PEUGEOT|RENAULT|"
        "PORSCHE|MINI|FIAT|JAGUAR"
    )

    skip_patterns = [
        r"^Ref\.?\s*No",
        r"^[A-Z]{1,3}\d{5,}$",
        r"^\$[\d,]+",
        r"^US\$",
        r"^\d{4}$",
        r"^\d{1,3},?\d*\s*km$",
        r"^\d{3,5}\s*cc$",
        r"^(Right|Left|Automatic|Manual|AT|MT|CVT)$",
        r"^(FOB|Price|Mileage|Engine|Steering|Transmission|Fuel|Location)",
        r"^Save$",
        r"^Inquire$",
        r"^Buy Now$",
    ]

    for line in lines:
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue

        if re.search(rf"\b({makers})\b", line, re.IGNORECASE):
            return line

    # Fallback: choose a descriptive line with letters that is not mostly numbers.
    for line in lines:
        if any(re.search(pattern, line, re.IGNORECASE) for pattern in skip_patterns):
            continue
        if len(line) >= 8 and re.search(r"[A-Za-z]", line):
            return line

    return ""


def extract_chassis_code(full_text):
    return extract_first([
        r"Chassis\s*(?:Code|No\.?)?\s*[:#]?\s*([A-Z0-9-]+)",
        r"Model\s*Code\s*[:#]?\s*([A-Z0-9-]+)",
        r"\b([A-Z]{2,4}\d{2,4}[A-Z0-9-]*)\b",
    ], full_text)


def build_page_url(page_number):
    page = page_number + 1
    if "page=" in BASE_URL:
        return re.sub(r"page=\d+", f"page={page}", BASE_URL)
    return BASE_URL.rstrip("/") + f"/page={page}/"


def get_text_from_element(element):
    try:
        return element.text.strip()
    except Exception:
        return ""


def get_best_link(element):
    """
    Get a real detail URL. Do not trust its text as the name because it can be only the ref id.
    """
    selectors = [
        "a.stock_link",
        "a[href*='/stocklist/']",
        "a[href*='/car']",
        "h3 a",
        "h2 a",
        "[class*='title'] a",
        "[class*='name'] a",
        "a",
    ]

    for selector in selectors:
        try:
            links = element.find_elements(By.CSS_SELECTOR, selector)
            for link in links:
                href = link.get_attribute("href") or ""
                text = link.text.strip()
                if href and ("beforward.jp" in href or href.startswith("/")):
                    return text, href
        except Exception:
            continue

    return "", ""


# =========================
# NAVIGATION
# =========================

def wait_for_listings(driver, wait):
    selectors = [
        ".stocklist-content-wrapper",
        "tr.stocklist_data",
        "[class*='stocklist'][class*='content']",
        "[class*='stock'][class*='item']",
    ]

    for selector in selectors:
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
            return selector
        except Exception:
            continue

    raise TimeoutError("Could not find listing containers")


def go_to_page(driver, wait, page_number):
    driver.get(build_page_url(page_number))
    wait_for_listings(driver, wait)


def get_total_pages(driver):
    try:
        total = int(driver.find_element(
            By.CSS_SELECTOR,
            "meta[name='ga_stocklist_results']"
        ).get_attribute("content"))

        pages = (total // PAGE_SIZE) + (1 if total % PAGE_SIZE else 0)
        print(f"Total records: {total} > {pages} pages")
        return pages

    except Exception as e:
        print(f"Could not read total pages: {e}")
        print("Defaulting to 1308 pages")
        return 1308


# =========================
# SCRAPING LOGIC
# =========================

def get_listing_elements(driver):
    selectors = [
        ".stocklist-content-wrapper",
        "tr.stocklist_data",
        "[class*='stocklist'][class*='content']",
        "[class*='stock'][class*='item']",
    ]

    for selector in selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        elements = [e for e in elements if get_text_from_element(e)]
        if elements:
            return elements

    return []


def parse_listing_text(full_text, link_text="", detail_url=""):
    full_text_lower = full_text.lower()

    if detail_url:
        detail_url = urljoin("https://www.beforward.jp", detail_url)

    ref_id = extract_ref_id(full_text, detail_url)

    # IMPORTANT FIX:
    # Do not use link_text as name unless it is not just a ref id.
    real_name = extract_car_name(full_text)
    if real_name:
        name = real_name
    elif link_text and link_text != ref_id and not re.fullmatch(r"[A-Z]{1,3}\d{5,}", link_text):
        name = link_text.strip()
    else:
        name = ""

    year = extract_first([
        r"\b(20\d{2}|19\d{2})\b",
        r"Year\s*[:#]?\s*(20\d{2}|19\d{2})",
    ], full_text)

    chassis_code = extract_chassis_code(full_text)

    price_usd = extract_first([
        r"(?:US\$|\$)\s*([\d,]+)",
        r"FOB\s*(?:US\$|\$)?\s*([\d,]+)",
    ], full_text)
    if price_usd:
        price_usd = "$" + price_usd

    price_jpy = extract_first([
        r"JPY\s*([\d,]+)",
        r"¥\s*([\d,]+)",
    ], full_text)

    mileage = extract_first([
        r"Mileage\s*[:#]?\s*([\d,]+\s*km)",
        r"([\d,]+\s*km)",
    ], full_text)

    engine = extract_first([
        r"Engine\s*[:#]?\s*([\d,]+\s*cc)",
        r"([\d,]+\s*cc)",
    ], full_text)

    fuel = extract_first([
        r"Fuel\s*[:#]?\s*([A-Za-z /-]+)",
        r"\b(Petrol|Diesel|Hybrid|Electric|Gasoline)\b",
    ], full_text)

    transmission = extract_first([
        r"Transmission\s*[:#]?\s*([A-Za-z0-9 /-]+)",
        r"\b(Automatic|Manual|AT|MT|CVT)\b",
    ], full_text)

    steering = extract_first([
        r"Steering\s*[:#]?\s*([A-Za-z]+)",
        r"\b(Right|Left)\b",
    ], full_text)

    vehicle_type = extract_first([
        r"Vehicle\s*Type\s*[:#]?\s*([A-Za-z0-9 /-]+)",
        r"Body\s*Type\s*[:#]?\s*([A-Za-z0-9 /-]+)",
        r"\b(SUV|Sedan|Hatchback|Wagon|Van|Truck|Coupe|Bus|Pickup)\b",
    ], full_text)

    location = extract_first([
        r"Location\s*[:#]?\s*([A-Za-z0-9 ,/-]+)",
    ], full_text)

    date_listed = extract_first([
        r"(?:Listed|Date)\s*[:#]?\s*([A-Za-z0-9 ,/-]+)",
    ], full_text)

    options_text = extract_first([
        r"Options\s*[:#]?\s*(.+)",
        r"Features\s*[:#]?\s*(.+)",
    ], full_text)

    options_lower = options_text.lower()

    return {
        "ref_id": ref_id,
        "name": name,
        "chassis_code": chassis_code,
        "year": year,
        "price_usd": price_usd,
        "price_jpy": price_jpy,
        "mileage_km": clean_number(mileage),
        "engine_cc": clean_number(engine),
        "fuel": fuel,
        "transmission": transmission,
        "steering": steering,
        "vehicle_type": vehicle_type,
        "options": options_text,
        "has_sunroof": 1 if "sun roof" in options_lower or "sunroof" in options_lower else 0,
        "has_leather": 1 if "leather" in options_lower else 0,
        "has_navigation": 1 if "navigation" in options_lower or "nav" in options_lower else 0,
        "has_alloy_wheels": 1 if "alloy" in options_lower else 0,
        "has_4wd": 1 if "4wd" in full_text_lower or "awd" in full_text_lower else 0,
        "has_airbag": 1 if "airbag" in full_text_lower else 0,
        "has_abs": 1 if "abs" in full_text_lower else 0,
        "has_camera": 1 if "camera" in full_text_lower else 0,
        "location": location,
        "date_listed": date_listed,
        "detail_url": detail_url,
    }


def scrape_page(driver):
    cars = []
    listings = get_listing_elements(driver)

    for listing in listings:
        try:
            full_text = get_text_from_element(listing)
            link_text, detail_url = get_best_link(listing)
            cars.append(parse_listing_text(full_text, link_text, detail_url))
        except Exception as e:
            print(f"  [!] Skipped listing: {e}")

    return cars


# =========================
# RESUME LOGIC
# =========================

def get_start_page():
    if not os.path.exists(OUTPUT_FILE):
        return 0, False

    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        rows = sum(1 for _ in f) - 1

    if rows <= 0:
        return 0, False

    start_page = rows // PAGE_SIZE
    print(f"Found {rows} existing records > resuming from page {start_page + 1}")
    return start_page, True


# =========================
# MAIN
# =========================

def main():
    start_page, append_mode = get_start_page()

    driver = create_driver()
    wait = WebDriverWait(driver, WAIT_TIMEOUT)

    driver.get(BASE_URL)
    wait_for_listings(driver, wait)

    total_pages = get_total_pages(driver)

    if MAX_PAGES is not None:
        total_pages = min(total_pages, start_page + MAX_PAGES)

    failed_pages = []
    total_scraped = 0

    file_mode = "a" if append_mode else "w"

    with open(OUTPUT_FILE, file_mode, newline="", encoding="utf-8") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=FIELDNAMES)

        if not append_mode:
            writer.writeheader()

        for page in range(start_page, total_pages):
            try:
                print(f"Scraping page {page + 1} of {total_pages}...")

                go_to_page(driver, wait, page)

                page_cars = scrape_page(driver)
                writer.writerows(page_cars)
                csv_file.flush()

                total_scraped += len(page_cars)

                print(f"  > {len(page_cars)} cars | Total new: {total_scraped}")

                if SLEEP_BETWEEN_PAGES:
                    time.sleep(SLEEP_BETWEEN_PAGES)

                if (page + 1) % RESTART_EVERY_PAGES == 0:
                    print("  Restarting browser to free memory...")
                    driver.quit()
                    driver = create_driver()
                    wait = WebDriverWait(driver, WAIT_TIMEOUT)

            except Exception as e:
                print(f"  [!] Failed on page {page + 1}: {e}")
                failed_pages.append(page + 1)

                try:
                    driver.quit()
                except Exception:
                    pass

                driver = create_driver()
                wait = WebDriverWait(driver, WAIT_TIMEOUT)
                continue

    driver.quit()

    print(f"\nDone! {total_scraped} new records saved to {OUTPUT_FILE}")

    if failed_pages:
        with open(FAILED_PAGES_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(map(str, failed_pages)))

        print(f"Failed pages saved to {FAILED_PAGES_FILE}: {failed_pages}")


if __name__ == "__main__":
    main()
