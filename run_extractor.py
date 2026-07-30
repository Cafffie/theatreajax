"""TheatreAjax (qpac.com.au) extractor implementation using the shared framework."""
import json
import random
import re
import sys
import time
from datetime import datetime

import pandas as pd
from dateutil import parser
from selenium.webdriver.common.by import By
from seleniumbase import SB

from utils.base_extractor import BaseExtractor
from utils.logger import setup_logger
from utils.scraping_helpers import (
    format_datetime_key,
    get_currency_from_price,
    get_scrape_datetime,
    human_delay,
    human_scroll,
    normalize_country,
    standardize_category,
)

from .qpac_config import (
    DEFAULT_CURRENCY,
    DEFAULT_THEATRE_DETAILS,
    PAGES,
    SELECTORS,
    THEATRE_DETAILS_MAP,
)

logger = setup_logger(__name__, log_to_file=False)


class QpacExtractor(BaseExtractor):
    """Extractor for qpac website."""

    def __init__(self, local_test=False, show_count=2, **kwargs):
        super().__init__(
            site_id="qpac",
            log_to_file=False,
            log_to_terminal=True,
            local_test=local_test,
            show_count=show_count,
            **kwargs,
        )
        self.all_data = []

    def safe_get(self, sb, url, wait=10):
        try:
            # self.custom_logger.info("Loading URL: %s", url)
            sb.uc_open_with_reconnect(url, reconnect_time=wait if wait > 4 else 4)
            if (
                "captcha" in sb.get_current_url().lower()
                or "distil" in sb.get_page_source().lower()
            ):
                self.custom_logger.warning("Bot protection detected. Solving...")
                sb.uc_gui_handle_captcha()
                time.sleep(random.uniform(2, 4))
            self.custom_logger.info("Page loaded successfully: %s", url)
            return True
        except Exception as e:
            self.custom_logger.error(
                "Failed to load page: %s | Exception: %s", url, repr(e)
            )
            return None

    def accept_cookies(self, sb):
        cookie_xpath = SELECTORS["cookie_button"]
        try:
            if sb.is_element_visible(cookie_xpath):
                human_delay(1, 2.5)
                sb.click(cookie_xpath)
                human_delay(2, 3)
        except Exception:
            pass

    
    def _get_show_title(self, sb) -> str | None:
        """Extract show title."""
        try:
            return sb.get_text(SELECTORS["title"]).strip() or None
        except Exception:
            return None



    def _get_terminal_dates(self, sb):
        """Extract show header dates."""
        try:
            return sb.get_text(SELECTORS["terminal_date"]).strip() or None
        except Exception as e:
            self.custom_logger.debug(f"terminal date extraction failed: {e}")
            return None


    def _get_event_venue(self, sb) -> dict | None:
        """Extract an event-specific venue from the current show page."""

        try:
            subtitle = sb.get_text(SELECTORS["subtitle"]).strip().lower()

            for venue_name, venue_details in THEATRE_DETAILS_MAP.items():
                if venue_name.lower() in subtitle:
                    self.custom_logger.info(
                        "Event-specific venue found: %s",
                        venue_details["venue"],
                    )
                    return venue_details

        except Exception as e:
            self.custom_logger.warning(
                "Event-specific venue extraction failed: %s",
                e,
            )

        return DEFAULT_THEATRE_DETAILS

    def _extract_performances(self, sb) -> list[dict]:
        """Parses performance instances directly from qpac's single or continuous date markers."""

        performances = []

        
        sb.wait_for_ready_state_complete()
        

                        performances.append(
                            {
                                "date": date_ymd,
                                "time": time_hm,
                                "selector": selector,
                                "layout": "list",
                                "data_local_date": formatted_iso,
                            }
                        )
                    except Exception as inner_e:
                        self.custom_logger.debug(
                            f"Failed parsing event list row: {inner_e}"
                        )
                        continue

        except Exception as e:
            self.custom_logger.debug(f"Calendar Grid extraction failed: {e}")

        return performances

    def extract_price_map(self, sb) -> dict:
        """
        Extracts price level keys ('pl-1', 'pl-2', etc.) and their monetary values.
        Handles nested SVG classes (e.g., <svg class="seat--pl-1 seat">) or data attributes.
        Output example: {'pl-1': 274.0, 'pl-2': 229.0, 'pl-3': 194.0, 'pl-4': 144.0}
        """
        price_map = {}
        currency = None
        try:
            legend_items = sb.find_elements(
                By.CSS_SELECTOR, SELECTORS["price_legend_items"]
            )

            for item in legend_items:
                try:
                    item_html = item.get_attribute("outerHTML") or ""

                    # Capture price level key from class names (e.g., 'seat--pl-1') or data attributes
                    pl_match = re.search(r"seat--pl-(\d+)", item_html)
                    if not pl_match:
                        continue

                    pl_num = int(pl_match.group(1))

                    # pl_num = next(g for g in pl_match.groups() if g is not None)
                    pl_key = f"pl-{pl_num}"

                    # Extract currency value (e.g., '$274.00' -> 274.0)
                    text_content = item.text.strip()
                    price_match = re.search(
                        r"[\$£€]?\s*(\d+(?:\.\d{2})?)", text_content
                    )

                    if currency is None and text_content:
                        currency = get_currency_from_price(text_content)

                    if price_match:
                        price_map[pl_key] = float(price_match.group(1))

                except Exception as e:
                    self.custom_logger.warning("Failed to parse price: %s", e)
                    continue

        except Exception as e:
            self.custom_logger.warning("Price map extraction failed: %s", e)

        return price_map, currency

    def parse_seat_map(self, sb) -> list[dict]:
        """
        Parses active/available seat details from the SVG map.
        Only seats with active CSS color variables (e.g., style="fill: var(--color-pl-1);")
        are parsed as available.
        """
        all_seats = {}
        capacity = 0

        try:
            sb.wait_for_ready_state_complete()
            human_delay(2, 3)

            # ---------- SOLD OUT ----------
            if sb.is_element_present(SELECTORS["sold_out"]):
                self.custom_logger.info("Performance is sold out.")
                return [], None, None, "sold_out"

            # 2. Extract price map
            price_map, currency = self.extract_price_map(sb)
            self.custom_logger.info(f" Price map: {price_map}")

            # 3. Wait for and find seat elements
            sb.wait_for_element_present(SELECTORS["seatmap"], timeout=10)
            self.custom_logger.info("Seat map detected.")

            seats = sb.find_elements(By.CSS_SELECTOR, SELECTORS["svg_seats"])
            capacity = len(seats) if seats else None
            self.custom_logger.info(f" Found {len(seats)} unique seats. ")

            # 4. Iterate and extract available seats
            for seat in seats:
                try:
                    style = seat.get_attribute("style") or ""
                    seat_id = seat.get_attribute("id") or ""
                    seat_class = seat.get_attribute("class") or ""

                    # Check if seat is available via active CSS price variables or direct classes
                    pl_match = re.search(
                        r"var\(--color-(pl-\d+)\)|class=.*?['\"](?:.*?\s)?(pl-\d+)",
                        f"{style} {seat_class}",
                    )
                    if not pl_match:
                        # Secondary check specifically for style attribute
                        pl_match = re.search(r"var\(--color-(pl-\d+)\)", style)
                        if not pl_match:
                            continue

                    pl_key = (
                        pl_match.group(1) if pl_match.group(1) else pl_match.group(2)
                    )
                    price = price_map.get(pl_key)

                    # Parse seat identifier (e.g., 'Stalls-B-32' or 'LowerLeft-Box-2')
                    parts = seat_id.split("-")
                    section = parts[0] if len(parts) > 0 else None
                    row = parts[1] if len(parts) > 1 else None
                    seat_number = parts[2] if len(parts) > 2 else None

                    seat_identifier = f"{section} {row}{seat_number}".strip()

                    all_seats[seat_identifier] = {
                        "seat": seat_identifier,
                        "ticket_price": price,
                    }

                except Exception as seat_error:
                    self.custom_logger.warning(
                        "Failed to parse individual seat: %s", seat_error
                    )
                    continue

        except Exception as e:
            self.custom_logger.error("Seat map scraping failed: %s", e)
            # return [], None, None
            return None, None, None, "no_seatmap"

        seat_list = list(all_seats.values())

        self.custom_logger.info(
            f" Total capacity: {capacity} seats ({len(seat_list)} priced)"
        )
        return seat_list, currency, (capacity if capacity > 0 else None), "seatmap"

    def extract_seat_metrics(self, sb, performances):
        """Extracts seats and pricing from internal ticket frame configurations."""

        seat_pricing = {}
        capacity = None
        currency = None

        encountered_no_seatmap = False
        encountered_sold_out = False

        for i, perf in enumerate(performances, start=1):
            key = format_datetime_key(perf["date"], perf["time"])
            if not key:
                continue

            self.custom_logger.info(
                f" [{i}/{len(performances)}] Seats for {perf['date']} {perf['time']}"
            )

            try:
                selector = perf.get("selector")
                target_btn = None

                # 1. Look up performance button directly using the exact timestamp/aria selector
                if selector and isinstance(selector, str):
                    elements = sb.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        target_btn = elements[0]

                # 2. Fallback for calendar view: Re-open calendar day drawer if hidden
                if not target_btn and perf.get("layout") == "calendar":
                    day_idx = perf.get("day_index")
                    calendar_days = sb.find_elements(
                        By.CSS_SELECTOR, SELECTORS["calendar_days"]
                    )

                    if day_idx is not None and len(calendar_days) > day_idx:
                        # Click day tile to open drawer
                        sb.execute_script(
                            "arguments[0].click();", calendar_days[day_idx]
                        )
                        human_delay(1.0, 1.5)

                        # Re-search for this specific showtime button inside open drawer
                        if selector and isinstance(selector, str):
                            elements = sb.find_elements(By.CSS_SELECTOR, selector)
                            if elements:
                                target_btn = elements[0]

                if not target_btn:
                    self.custom_logger.warning(f" No clickable element found for {key}")
                    seat_pricing[key] = []
                    continue

                # Execute click safely on fresh element
                sb.execute_script("arguments[0].click();", target_btn)
                human_delay(2.0, 3.5)

                # Parse seat map
                try:
                    (
                        seat_list,
                        perf_currency,
                        perf_capacity,
                        status,
                    ) = self.parse_seat_map(sb)

                    if status == "seatmap":
                        seat_pricing[key] = seat_list
                        currency = perf_currency or currency
                        capacity = perf_capacity or capacity
                        self.custom_logger.info(
                            f" Seats: {len(seat_list)} | Capacity: {capacity} | Currency: {currency}"
                        )
                    elif status == "sold_out":
                        seat_pricing[key] = []
                        encountered_sold_out = True
                        self.custom_logger.info(f"{key} is sold out.")

                    elif status == "no_seatmap":
                        seat_pricing[key] = []
                        encountered_no_seatmap = True
                        self.custom_logger.info(f"{key} has no seat map.")

                    human_delay(1.5, 2.5)

                except Exception as parse_err:
                    seat_pricing[key] = []
                    encountered_no_seatmap = True
                    self.custom_logger.info(
                        f" No seat map layout for {key}: {parse_err}"
                    )

            except Exception as e:
                seat_pricing[key] = []
                encountered_no_seatmap = True
                self.custom_logger.warning(f" Seat extraction error for {key}: {e}")

        if (
            encountered_no_seatmap
            and not encountered_sold_out
            and all(len(seats) == 0 for seats in seat_pricing.values())
        ):
            self.custom_logger.info(
                "All performances lack a seat map layout. Resetting seat_pricing = {}"
            )
            seat_pricing = {}

        if encountered_no_seatmap and all(
            len(seats) == 0 for seats in seat_pricing.values()
        ):
            self.custom_logger.info(
                " All performances lack a seat map layout. Resetting seat_pricing = {}"
            )
            seat_pricing = {}

        self.custom_logger.info(" Seat extraction flow processed")
        return seat_pricing, currency, capacity

    def _scrape_one_show(self, sb, show_url: str, category: str) -> dict | None:
        """Scrape a single show page end-to-end.

        Returns a completed row dict on success, or None if the show page
        did not render (bot challenge, timeout) — the caller retries.
        """

        if not self.safe_get(sb, show_url):
            return None

        self.accept_cookies(sb)
        human_delay(2, 4)

        title = self._get_show_title(sb)
        if not title:
            self.custom_logger.warning("No title found for: %s", show_url)

        venue_url = sb.get_current_url()
        self.custom_logger.info("venue_url: %s", venue_url)

        terminal_date = self._get_terminal_dates(sb)
        open_date, close_date = self._parse_terminal_date(terminal_date)

        # specific theatre space, e.g. "Lyric Theatre"
        theatre_name = self._get_show_venue(sb)
        theatre_details = self._get_theatre_details(theatre_name)
        address = theatre_details.get("address")
        city = theatre_details.get("city")
        country = normalize_country(theatre_details.get("country"))

        self.accept_cookies(sb)
        human_delay(2, 4)

        self.custom_logger.info("Category: %s", category)
        self.custom_logger.info("Title: %s", title)
        self.custom_logger.info("Terminal: %s", terminal_date)

        self.custom_logger.info("Open Date: %s", open_date)
        self.custom_logger.info("Close Date: %s", close_date)
        self.custom_logger.info("Venue: %s", theatre_name)
        self.custom_logger.info("Address: %s", address)
        self.custom_logger.info("-" * 50)

        human_delay(10, 12.5)
        human_scroll(sb)
        time.sleep(3)

        performances = self._extract_performances(sb)
        if not performances:
            self.custom_logger.warning(
                f"  No performances found for '{title}', skipping"
            )
            return None

        sorted_dates = sorted([p["date"] for p in performances])
        if not open_date:
            open_date = sorted_dates[0]

        if not close_date:
            close_date = sorted_dates[-1]

        if open_date > close_date:
            self.custom_logger.warning(
                "  Open date %s is after close date %s. Adjusting open date to performance.",
            )
            open_date = sorted_dates[0]

        seat_pricing, currency, capacity = self.extract_seat_metrics(sb, performances)

        self.custom_logger.info(
            "Performances: %d | Seat keys: %d",
            len(performances),
            len(seat_pricing),
        )
        self.custom_logger.info("Venue: %s", theatre_name)
        self.custom_logger.info("Address: %s", address)
        self.custom_logger.info("City: %s", city)
        self.custom_logger.info("Country: %s", country)
        self.custom_logger.info("Capacity: %s", capacity)
        self.custom_logger.info("Currency: %s", currency)

        return {
            "title": title,
            "category": standardize_category(category),
            "venue": theatre_name,
            "venue_url": venue_url,
            "address": address,
            "city": city,
            "country": country,
            "open_date": open_date,
            "close_date": close_date,
            "booking_start_date": open_date,
            "booking_end_date": close_date,
            "upcoming_performances": [
                {"date": p["date"], "time": p["time"]} for p in performances
            ],
            "seat_pricing": seat_pricing,
            "capacity": int(capacity) if capacity is not None else None,
            "currency": DEFAULT_CURRENCY,
            "is_limited_run": None,
            "scrape_datetime": get_scrape_datetime(),  # datetime.now().strftime("%Y-%m-%d %H:%M"),
        }

    def _scrape_shows(self, sb, show_links: list, category: str) -> None:
        """Scrape individual show pages with multi-pass retry (Denver pattern)."""
        _MAX_PASSES = 3
        pending = list(show_links)

        for _pass in range(1, _MAX_PASSES + 1):
            if not pending:
                break

            self.custom_logger.info(
                "Show pass %d/%d — %d show(s)", _pass, _MAX_PASSES, len(pending)
            )
            still_pending = []

            for show_url in pending:
                row = self._scrape_one_show(sb, show_url, category)
                if row is None:
                    still_pending.append(show_url)
                    self.custom_logger.warning(
                        "Pass %d: show deferred — %s", _pass, show_url
                    )
                else:
                    self.all_data.append(row)
                    self.log_record(row)
                    human_delay(8, 15)

            pending = still_pending

            if pending and _pass < _MAX_PASSES:
                self.custom_logger.info(
                    "Pass %d complete — %d show(s) still pending. "
                    "Cooling down before pass %d",
                    _pass,
                    len(pending),
                    _pass + 1,
                )
                human_scroll(sb)
                human_delay(60, 120)

        if pending:
            self.custom_logger.warning(
                "%d show(s) could not be scraped after %d passes: %s",
                len(pending),
                _MAX_PASSES,
                pending,
            )

    def extract(self) -> bytes:
        """Open SB session, scrape all shows, populate self.all_data, return JSON bytes."""
        self.all_data = []
        seen_links = set()

        with SB(
            uc=True,
            test=True,
            headless=True,
            browser="chrome",
            locale="en-US",
            chromium_arg="--enable-features=TranslateUI",
        ) as sb:
            self.custom_logger.info("Starting extraction from qpac")

            for i, (url, category) in enumerate(PAGES):
                self.custom_logger.info(f"[Listing] {category}: {url}")
                if not self.safe_get(sb, url):
                    continue

                human_delay(4, 6)
                sb.maximize_window()
                self.accept_cookies(sb)

                show_links = self.get_show_links(sb)

                if self.local_test:
                    self.custom_logger.info(
                        "LOCAL TEST MODE: Limiting to %s shows", self.show_count
                    )
                    # show_links = ["https://www.qpac.com.au/whats-on/2026/the-lion-king"]
                    show_links = [
                        "https://www.qpac.com.au/whats-on/2026/qcgu-an-evening-in-concert-2nd-year-musical-theatre-students"
                    ]
                    # show_links = show_links[: self.show_count]

                unique_links = []
                for link in show_links:
                    if link not in seen_links:
                        seen_links.add(link)
                        unique_links.append(link)

                show_links = unique_links

                self._scrape_shows(sb, show_links, category)

        # Deduplicate rows by (title, venue) before building the final output
        deduped_data = []
        seen_keys = set()

        for row in self.all_data:
            key = (row.get("title"), row.get("venue"))
            if key not in seen_keys:
                seen_keys.add(key)
                deduped_data.append(row)
            else:
                self.custom_logger.warning(f"Dropped duplicate row for key: {key}")

        self.all_data = deduped_data

        return json.dumps(self.all_data, default=str).encode("utf-8")

    def _parse(self, _raw: bytes):
        """Build DataFrame from self.all_data collected during extract()."""
        df = pd.DataFrame(self.all_data)
        self.custom_logger.info("Parsing completed. Extracted %s shows", len(df))
        return df


def main():
    """Example usage of the qpac extractor."""
    extractor = QpacExtractor(save_csv_locally=False, csv_incremental_mode=False)
    result = extractor.run()
    logger.info(f"Extraction result: {result}")
    if result.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
