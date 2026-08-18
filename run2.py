"""TheatreAjax (ci.ovationtix.com) extractor implementation using the shared framework."""

import json
import random
import re
import sys
import time

import pandas as pd
from dateutil import parser
from selenium.webdriver.common.by import By
from seleniumbase import SB

from utils.base_extractor import BaseExtractor
from utils.logger import setup_logger
from utils.scraping_helpers import (
    convert_to_24hr,
    format_datetime_key,
    get_currency_from_price,
    get_scrape_datetime,
    human_delay,
    human_scroll,
    normalize_country,
    standardize_category,
)

from .theatre_ajax_config import (
    DEFAULT_CURRENCY,
    DEFAULT_THEATRE_DETAILS,
    PAGES,
    SELECTORS,
    THEATRE_DETAILS_MAP,
)

logger = setup_logger(__name__, log_to_file=False)


class TheatreAjaxExtractor(BaseExtractor):
    """Extractor for Theatre Ajax website on OvationTix."""

    def __init__(self, local_test=False, show_count=2, **kwargs):
        super().__init__(
            site_id="theatre_ajax",
            log_to_file=False,
            log_to_terminal=True,
            local_test=local_test,
            show_count=show_count,
            **kwargs,
        )
        self.all_data = []

    def safe_get(self, sb, url, wait=10):
        try:
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

    def _get_show_details(self, sb) -> str | None:
        """Extract show title."""

        show_details= []
        try:
            show_card = sb.find_element(SELECTORS["show_card"])
            self.custom_logger.info(f"Found {len(show_card)} show cards for extraction.")
            for card in show_card:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, SELECTORS["title"])
                    titles = title_elem.text.strip() if title_elem else ""
                    self.custom_logger.info(f"Found title: {titles}")
                    
                    subtitle_elem = card.find_element(By.CSS_SELECTOR, SELECTORS["subtitle"])
                    subtitle = subtitle_elem.text.strip() if subtitle_elem else ""
                    self.custom_logger.info(f"Found subtitle: {subtitle}")

                    open_date, close_date = None, None
                    try:
                        terminal_elem = card.find_element(By.CSS_SELECTOR, SELECTORS["terminal_date"])
                        terminal_date = terminal_elem.text.strip() if terminal_elem else ""
                        if terminal_date:
                            booking_dates = parse_booking_dates(terminal_date)
                            open_date = booking_dates.get("start_date")
                            close_date = booking_dates.get("end_date")
                    except Exception:
                        pass

                    see_event_button = card.find_element(By.CSS_SELECTOR, SELECTORS["see_this_event_button"])
                
                    show_details.append({
                        "title": titles,    
                        "subtitle": subtitle,
                        "open_date": open_date,
                        "close_date": close_date,
                        "see_event_button": see_event_button
                    })

                except Exception as e:
                    self.custom_logger.debug(f"Error occurred while extracting show details: {e}")
                    continue
            
        except Exception as e:
            self.custom_logger.debug(f"Show details extraction failed: {e}")
            return show_details

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
                "Event-specific venue extraction failed, falling back to default address: %s", e
            )

        return DEFAULT_THEATRE_DETAILS



    def _extract_performances(self, sb) -> list[dict]:
        """Parses performance instances directly from single or continuous date markers."""
        performances = []
        #try:
            #see_event_button = sb.find_elements(SELECTORS["see_event_button"])
            #if see_event_button:
                #sb.execute_script("arguments[0].click();", see_event_button)
                #human_delay(2, 3)
                #self.custom_logger.info("Clicked see_event_button.")
        #except Exception as e:
            #self.custom_logger.debug(f"Failed clicking 'See Event' button: {e}")

        sb.wait_for_ready_state_complete()
        try:
            date_blocks = sb.find_elements(By.CSS_SELECTOR, SELECTORS["date_blocks"])
            self.custom_logger.info(f"Found {len(date_blocks)} performance dates")

            for block in date_blocks:
                try:
                    date_time_text = block.text.strip() or None
                    if not date_time_text:
                        continue

                    self.custom_logger.info(f"Performance date_string: {date_time_text}")

                    date_ymd = parser.parse(date_time_text, fuzzy=True).strftime("%Y-%m-%d")
                    #time_hm = convert_to_24hr(date_time_text)
                    time_hm = parser.parse(date_time_text, fuzzy=True).strftime("%H:%M")
                    self.custom_logger.info(f"parsed date and time : {date_ymd} {time_hm}")

                    performances.append(
                        {
                            "date": date_ymd,
                            "time": time_hm,
                            "element": block,
                        }
                    )
                except Exception as inner_e:
                    self.custom_logger.debug(f"Failed parsing event list row: {inner_e}")
                    continue

        except Exception as e:
            self.custom_logger.debug(f"Calendar Grid extraction failed: {e}")

        return performances

    def parse_seat_map(self, sb) -> tuple[list[dict], str | None, int | None, str]:
        """Scrapes seat attributes directly from the SVG structure without individual clicks."""
        if sb.is_element_visible(SELECTORS["sold_out"]):
            return [], None, None, "sold_out"

        if not sb.is_element_visible(SELECTORS["seatmap_container"]):
            return [], None, None, "no_seatmap"

        seats = sb.find_elements(SELECTORS["seat_group"])
        if not seats:
            return [], None, None, "no_seatmap"

        seat_list = []
        detected_currency = DEFAULT_CURRENCY
        total_capacity = len(seats)

        for seat_elem in seats:
            try:
                # Extract structured attributes provided by OvationTix SVG items
                class_attr = seat_elem.get_attribute("class") or ""
                is_available = "selectable" in class_attr and "occupied" not in class_attr and "sold" not in class_attr

                if not is_available:
                    continue

                section = seat_elem.get_attribute("data-section") or "General"
                row = seat_elem.get_attribute("data-row") or ""
                seat_num = seat_elem.get_attribute("data-seat") or seat_elem.get_attribute("data-seat-number") or ""
                price_str = seat_elem.get_attribute("data-price") or "0"

                # Parse price and currency
                price_match = re.search(r"[\d\.]+", price_str)
                price_val = float(price_match.group()) if price_match else 0.0
                curr = get_currency_from_price(price_str)
                if curr:
                    detected_currency = curr

                seat_list.append({
                    "section": section,
                    "row": row,
                    "seat": seat_num,
                    "price": price_val,
                    "status": "available",
                })
            except Exception:
                continue

        return seat_list, detected_currency, total_capacity, "seatmap"

    def extract_seat_metrics(self, sb, performances) -> tuple[dict, str | None, int | None]:
        seat_pricing = {}
        capacity = None
        currency = None

        encountered_no_seatmap = False
        encountered_sold_out = False

        for i, perf in enumerate(performances, start=1):
            key = format_datetime_key(perf["date"], perf["time"])
            if not key:
                continue

            try:
                target_btn = perf.get("element")
                if target_btn:
                    sb.execute_script("arguments[0].click();", target_btn)
                    human_delay(2.0, 3.5)

                seat_list, perf_currency, perf_capacity, status = self.parse_seat_map(sb)

                if status == "seatmap":
                    seat_pricing[key] = seat_list
                    currency = perf_currency or currency
                    capacity = perf_capacity or capacity
                elif status == "sold_out":
                    seat_pricing[key] = []
                    encountered_sold_out = True
                elif status == "no_seatmap":
                    seat_pricing[key] = []
                    encountered_no_seatmap = True

            except Exception as e:
                seat_pricing[key] = []
                encountered_no_seatmap = True
                self.custom_logger.warning(f"Seat extraction error for {key}: {e}")

        if encountered_no_seatmap and not encountered_sold_out and all(len(s) == 0 for s in seat_pricing.values()):
            seat_pricing = {}

        return seat_pricing, currency, capacity

    def _scrape_one_show(self, sb, see_btn_element, category: str) -> dict | None:
        try:
            sb.execute_script("arguments[0].scrollIntoView({block:'center'});", see_btn_element)
            sb.execute_script("arguments[0].click();", see_btn_element)
            human_delay(2, 3)
            self.custom_logger.info(f"see_btn_element clicked:")
        except Exception as e:
            self.custom_logger.warning(f"Failed opening show detail: {e}")
            return None
        
        human_delay(2, 4)

        current_url = sb.get_current_url()
        
        title = self.show_details.get("title") if self.show_details else None
        subtitle = self.show_details.get("subtitle") if self.show_details else None
        open_date = self.show_details.get("open_date") if self.show_details else None
        close_date = self.show_details.get("close_date") if self.show_details else None

        venue_url = current_url


        theatre_details = self._get_event_venue(sb) or DEFAULT_THEATRE_DETAILS
        theatre_name = theatre_details.get("venue")
        address = theatre_details.get("address")
        city = theatre_details.get("city")
        country = normalize_country(theatre_details.get("country"))

        self.accept_cookies(sb)
        human_delay(2, 4)

        self.custom_logger.info("Category: %s", category)
        self.custom_logger.info("Title: %s", title)
        self.custom_logger.info("Subtitle: %s", subtitle)
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
            self.custom_logger.warning(f"No performances found for '{title}', skipping")
            return None

        sorted_dates = sorted([p["date"] for p in performances])
        open_date = open_date or sorted_dates[0]
        close_date = close_date or sorted_dates[-1]

        seat_pricing, currency, capacity = self.extract_seat_metrics(sb, performances)

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
            "currency": currency or DEFAULT_CURRENCY,
            "is_limited_run": None,
            "scrape_datetime": get_scrape_datetime(),
        }

    def _scrape_shows(self, sb, show_links: list, category: str) -> None:
        _MAX_PASSES = 3
        pending = list(show_links)

        for _pass in range(1, _MAX_PASSES + 1):
            if not pending:
                break

            still_pending = []
            for show_url in pending:
                row = self._scrape_one_show(sb, show_url, category)
                if row is None:
                    still_pending.append(show_url)
                else:
                    self.all_data.append(row)
                    self.log_record(row)
                    human_delay(8, 15)

            pending = still_pending


    def extract(self) -> bytes:
        self.all_data = []

        with SB(
            uc=True,
            test=True,
            headless=True,
            browser="chrome",
            locale="en-US",
        ) as sb:
            self.custom_logger.info("Starting extraction from Theatre Ajax")

            for url, category in PAGES:
                if not self.safe_get(sb, url):
                    continue

                human_delay(4, 6)
                sb.maximize_window()
                self.accept_cookies(sb)

                try:
                    self.show_details = self._get_show_details(sb)
                except Exception as e:
                    self.custom_logger.warning(f"Error occurred while fetching show details: {e}")

                buttons = sb.find_elements(SELECTORS["see_event_button"])
                self.custom_logger.info(f"Found {len(buttons)} see this events buttons .")
                
                if self.local_test:
                    buttons = buttons[: self.show_count]

                for i in range(len(buttons)):
                    # Re-query elements per iteration to prevent stale reference errors
                    current_buttons = sb.find_elements(SELECTORS["see_event_button"])
                    if i < len(current_buttons):
                        row = self._scrape_one_show(sb, current_buttons[i], category)
                        if row:
                            self.all_data.append(row)
                            self.log_record(row)
                        # Return back to primary event listing page
                        self.safe_get(sb, url)

        return json.dumps(self.all_data, default=str).encode("utf-8")

    
    def _parse(self, _raw: bytes):
        df = pd.DataFrame(self.all_data)
        self.custom_logger.info("Parsing completed. Extracted %s shows", len(df))
        return df


def main():
    extractor = TheatreAjaxExtractor(save_csv_locally=False, csv_incremental_mode=False)
    result = extractor.run()
    logger.info(f"Extraction result: {result}")
    if result.get("status") != "success":
        sys.exit(1)


if __name__ == "__main__":
    main()
