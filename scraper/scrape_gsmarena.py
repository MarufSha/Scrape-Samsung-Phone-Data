import re
import sys
import requests
from bs4 import BeautifulSoup
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from database.db import SessionLocal
from database.models import Phone, PhoneVariant

LISTING_BASE_URL = "https://www.gsmarena.com/samsung-phones-9.php"
GSMARENA_BASE_URL = "https://www.gsmarena.com"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def fetch_phone_urls_from_listing(limit: int) -> list[str]:
    urls: list[str] = []
    page = 1

    while len(urls) < limit:
        if page == 1:
            listing_url = LISTING_BASE_URL
        else:
            listing_url = f"{GSMARENA_BASE_URL}/samsung-phones-9-0-p{page}.php"

        print(f"Fetching listing page {page}: {listing_url}")
        soup = fetch_page(listing_url)

        makers_div = soup.select_one("div.makers")
        if not makers_div:
            break

        links = makers_div.select("li > a[href]")
        if not links:
            break

        for link in links:
            if len(urls) >= limit:
                break
            href = link["href"]
            full_url = f"{GSMARENA_BASE_URL}/{href}"
            urls.append(full_url)

        # Check if there's a next page
        next_link = soup.select_one("a.pages-next")
        if not next_link:
            break

        page += 1

    return urls


def ensure_schema_columns(db: Session) -> None:
    inspector = inspect(db.bind)

    phone_columns = {column["name"] for column in inspector.get_columns("phones")}
    if "image_url" not in phone_columns:
        db.execute(text("ALTER TABLE phones ADD COLUMN image_url TEXT"))

    variant_columns = {
        column["name"] for column in inspector.get_columns("phone_variants")
    }
    if "price" not in variant_columns:
        db.execute(text("ALTER TABLE phone_variants ADD COLUMN price VARCHAR(255)"))

    db.commit()


def fetch_page(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def extract_specs_by_section(soup: BeautifulSoup) -> dict:
    specs_by_section = {}
    current_section = None

    rows = soup.select("table tr")

    for row in rows:
        section_cell = row.find("th")
        if section_cell:
            section_name = section_cell.get_text(" ", strip=True)
            if section_name:
                current_section = section_name
                specs_by_section.setdefault(current_section, {})

        label_cell = row.select_one("td.ttl")
        value_cell = row.select_one("td.nfo")

        if current_section and label_cell and value_cell:
            label = label_cell.get_text(" ", strip=True)
            value = value_cell.get_text(" ", strip=True)

            if label:
                specs_by_section[current_section][label] = value

    return specs_by_section


def get_section_value(specs_by_section: dict, section_name: str, label: str) -> str | None:
    return specs_by_section.get(section_name, {}).get(label)


def get_camera_label_and_count(section_specs: dict) -> tuple[str | None, int | None]:
    label_order = {
        "Single": 1,
        "Dual": 2,
        "Triple": 3,
        "Quad": 4,
    }

    for label, count in label_order.items():
        if label in section_specs:
            return label, count

    return None, None


def normalize_media_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("//"):
        return f"https:{url}"
    return url


def parse_variants(internal_value: str | None) -> list[dict]:
    if not internal_value:
        return []

    variants = []
    entries = [item.strip() for item in internal_value.split(",") if item.strip()]

    for entry in entries:
        match = re.search(r"(?P<storage>\S+)\s+(?P<ram>\S+)\s+RAM", entry, re.IGNORECASE)
        if match:
            variants.append(
                {
                    "storage": match.group("storage"),
                    "ram": match.group("ram"),
                }
            )

    return variants


def normalize_variant_key(storage: str, ram: str) -> tuple[str, str]:
    normalized_storage = re.sub(r"\s+", "", storage).lower()
    normalized_ram = re.sub(r"\s+", "", ram).lower()
    return normalized_storage, normalized_ram


def parse_variant_price_rows(soup: BeautifulSoup) -> dict[tuple[str, str], str]:
    variant_prices: dict[tuple[str, str], str] = {}

    # Price widgets are not consistently wrapped in `table.prices` across pages,
    # so we look for any row that has RAM/storage in the first cell and one or
    # more outgoing store links in the other cells.
    for row in soup.select("tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        variant_cell = cells[0].get_text(" ", strip=True)
        variant_match = re.search(
            r"(?P<storage>\S+)\s+(?P<ram>\S+)\s+RAM",
            variant_cell,
            re.IGNORECASE,
        )
        if not variant_match:
            continue

        storage = variant_match.group("storage")
        ram = variant_match.group("ram")

        listed_prices = []
        for price_cell in cells[1:]:
            anchor = price_cell.find("a", href=True)
            if not anchor:
                continue

            price_text = anchor.get_text(" ", strip=True)
            if not price_text:
                continue

            listed_prices.append(price_text)

        if listed_prices:
            variant_prices[normalize_variant_key(storage, ram)] = " | ".join(listed_prices)

    return variant_prices


def extract_phone_data(url: str) -> dict:
    soup = fetch_page(url)
    specs_by_section = extract_specs_by_section(soup)

    title_tag = soup.find("h1")
    name = title_tag.get_text(strip=True) if title_tag else "Unknown"
    main_image_tag = soup.select_one('a[href*="-pictures-"] img')
    image_url = normalize_media_url(main_image_tag.get("src") if main_image_tag else None)

    main_camera_section = specs_by_section.get("Main Camera", {})
    selfie_camera_section = specs_by_section.get("Selfie camera", {})

    main_camera_label, main_camera_count = get_camera_label_and_count(main_camera_section)
    selfie_camera_label, selfie_camera_count = get_camera_label_and_count(selfie_camera_section)

    main_camera_value = main_camera_section.get(main_camera_label) if main_camera_label else None
    selfie_camera_value = selfie_camera_section.get(selfie_camera_label) if selfie_camera_label else None

    internal_value = get_section_value(specs_by_section, "Memory", "Internal")
    variants = parse_variants(internal_value)
    variant_prices = parse_variant_price_rows(soup)

    for variant in variants:
        variant["price"] = variant_prices.get(
            normalize_variant_key(variant["storage"], variant["ram"])
        )

    phone_data = {
        "name": name,
        "brand": "Samsung",
        "display": get_section_value(specs_by_section, "Display", "Size"),
        "resolution": get_section_value(specs_by_section, "Display", "Resolution"),
        "protection": get_section_value(specs_by_section, "Display", "Protection"),
        "chipset": get_section_value(specs_by_section, "Platform", "Chipset"),
        "gpu": get_section_value(specs_by_section, "Platform", "GPU"),
        "os": get_section_value(specs_by_section, "Platform", "OS"),
        "rear_camera": main_camera_value,
        "rear_camera_count": main_camera_count,
        "rear_camera_video": get_section_value(specs_by_section, "Main Camera", "Video"),
        "selfie_camera": selfie_camera_value,
        "selfie_camera_count": selfie_camera_count,
        "selfie_camera_video": get_section_value(specs_by_section, "Selfie camera", "Video"),
        "battery": get_section_value(specs_by_section, "Battery", "Type"),
        "weight": get_section_value(specs_by_section, "Body", "Weight"),
        "build": get_section_value(specs_by_section, "Body", "Build"),
        "colors": get_section_value(specs_by_section, "Misc", "Colors"),
        "price": get_section_value(specs_by_section, "Misc", "Price"),
        "release_date": get_section_value(specs_by_section, "Launch", "Status"),
        "image_url": image_url,
        "phone_url": url,
        "variants": variants,
    }

    return phone_data


def save_phone_to_db(db: Session, phone_data: dict) -> None:
    existing_phone = db.query(Phone).filter(Phone.name == phone_data["name"]).first()

    if existing_phone:
        print(f"Skipped existing phone: {phone_data['name']}")
        return

    new_phone = Phone(
        name=phone_data["name"],
        brand=phone_data["brand"],
        display=phone_data["display"],
        resolution=phone_data["resolution"],
        protection=phone_data["protection"],
        chipset=phone_data["chipset"],
        gpu=phone_data["gpu"],
        os=phone_data["os"],
        rear_camera=phone_data["rear_camera"],
        rear_camera_count=phone_data["rear_camera_count"],
        rear_camera_video=phone_data["rear_camera_video"],
        selfie_camera=phone_data["selfie_camera"],
        selfie_camera_count=phone_data["selfie_camera_count"],
        selfie_camera_video=phone_data["selfie_camera_video"],
        battery=phone_data["battery"],
        weight=phone_data["weight"],
        build=phone_data["build"],
        colors=phone_data["colors"],
        price=phone_data["price"],
        release_date=phone_data["release_date"],
        image_url=phone_data["image_url"],
        phone_url=phone_data["phone_url"],
    )

    db.add(new_phone)
    db.commit()
    db.refresh(new_phone)

    for variant in phone_data["variants"]:
        new_variant = PhoneVariant(
            phone_id=new_phone.id,
            storage=variant["storage"],
            ram=variant["ram"],
            price=variant.get("price"),
        )
        db.add(new_variant)

    db.commit()
    print(f"Saved: {phone_data['name']}")


def main(limit: int = 15):
    db = SessionLocal()

    try:
        ensure_schema_columns(db)
        db.query(PhoneVariant).delete()
        db.query(Phone).delete()
        db.commit()
        print("Wiped existing phone dataset.")

        phone_urls = fetch_phone_urls_from_listing(limit)
        print(f"Found {len(phone_urls)} phone URLs to scrape.")

        for url in phone_urls:
            try:
                phone_data = extract_phone_data(url)
                save_phone_to_db(db, phone_data)
            except Exception as e:
                db.rollback()
                print(f"Failed for {url}")
                print(f"Error: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 15
    main(limit)
