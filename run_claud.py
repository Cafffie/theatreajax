"""
run_extractor.py — Theatre Jacksonville / OvationTix full-site extractor.

Single script, driven entirely by config.json. Does the whole pipeline:

  1. LIST PAGE
     For each show: title, open_date, close_date, category (from the
     manual lookup table in config.json — the site never labels shows
     as play/musical anywhere in the DOM).

  2. DETAIL / CALENDAR VIEW (click "See this event")
     For each calendar day (<li class="events">): date + every time-slot
     button = one performance.

  3. SEATMAP (click a time-slot button)
     Clicking a time slot loads the seatmap into #seatSelection on the
     SAME page — there's no separate booking URL per performance, so we
     record whatever URL is present afterward (booking_link) plus a
     fallback locator (date/time text) that always works by re-clicking
     the calendar. Then every selectable seat is clicked in turn and its
     info card (Section / Row / Seat / price) is scraped.

Output:
  - one JSON file: nested show -> performances -> seats
  - one flat CSV: one row per seat, with show/performance context repeated

Run:
  pip install seleniumbase
  python run_extractor.py
"""

import csv
import json
from seleniumbase import SB

CONFIG_PATH = "config.json"


# --------------------------------------------------------------------------
# Config / small helpers
# --------------------------------------------------------------------------

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def classify_category(title, cat_cfg):
    if title in cat_cfg["musical_titles"]:
        return "musical"
    if title in cat_cfg["play_titles"]:
        return "play"

    lower_title = (title or "").lower()
    for kw in cat_cfg.get("musical_keywords", []):
        if kw in lower_title:
            return "musical"
    for kw in cat_cfg.get("play_keywords", []):
        if kw in lower_title:
            return "play"

    return cat_cfg.get("default_category", "other")


def split_date_range(date_tag_text):
    """'Sat, Nov 07 - Sun, Nov 22' -> ('Sat, Nov 07', 'Sun, Nov 22')
       'Sun, Aug 16' -> ('Sun, Aug 16', 'Sun, Aug 16')"""
    parts = [p.strip() for p in date_tag_text.split(" - ")]
    if len(parts) == 2:
        return parts[0], parts[1]
    return parts[0], parts[0]


def scrape_card_text(card_element):
    """Pull Section / Row / Seat / price out of one seatmap info-card's text."""
    text = card_element.text
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    data = {"section": None, "row": None, "seat": None, "price": None, "raw": text}
    for i, ln in enumerate(lines):
        low = ln.lower()
        if low == "section" and i + 1 < len(lines):
            data["section"] = lines[i + 1]
        elif low == "row" and i + 1 < len(lines):
            data["row"] = lines[i + 1]
        elif low == "seat" and i + 1 < len(lines):
            data["seat"] = lines[i + 1]
        elif ln.startswith("$") and data["price"] is None:
            data["price"] = ln

    return data


# --------------------------------------------------------------------------
# Stage 1: production list
# --------------------------------------------------------------------------

def scrape_show_list(sb, sel):
    items = sb.find_elements(sel["item"])
    shows = []
    for i, item in enumerate(items):
        try:
            title = item.find_element("css selector", sel["title"]).text.strip()
        except Exception:
            title = None
        try:
            date_tag = item.find_element("css selector", sel["date_tag"]).text.strip()
            open_date, close_date = split_date_range(date_tag)
        except Exception:
            open_date, close_date = None, None

        shows.append({"index": i, "title": title, "open_date": open_date, "close_date": close_date})
    return shows


# --------------------------------------------------------------------------
# Stage 2: calendar / performances
# --------------------------------------------------------------------------

def scrape_performances(sb, list_sel, detail_sel, show):
    """Click into a show's detail view and return every (date, time) slot,
    each paired with the time-slot button so stage 3 can click it directly."""
    items = sb.find_elements(list_sel["item"])
    item = items[show["index"]]
    btn = item.find_element("css selector", list_sel["see_event_button"])
    sb.execute_script("arguments[0].scrollIntoView({block:'center'});", btn)
    btn.click()
    sb.sleep(1.5)

    performances = []
    day_groups = sb.find_elements(detail_sel["event_group"])
    for day_idx, day in enumerate(day_groups):
        try:
            date_text = day.find_element("css selector", detail_sel["date_label"]).text.strip()
        except Exception:
            date_text = None

        time_buttons = day.find_elements("css selector", detail_sel["time_slot_button"])
        for time_idx, tbtn in enumerate(time_buttons):
            time_text = tbtn.text.strip()
            performances.append({
                "day_index": day_idx,
                "time_index": time_idx,
                "performance_date": date_text,
                "performance_time": time_text,
            })

    return performances


# --------------------------------------------------------------------------
# Stage 3: seatmap
# --------------------------------------------------------------------------

def open_seatmap_for_performance(sb, detail_sel, perf):
    """Re-locate and click the exact time-slot button for this performance
    (re-queried fresh, since prior clicks may have re-rendered the calendar)."""
    day_groups = sb.find_elements(detail_sel["event_group"])
    day = day_groups[perf["day_index"]]
    time_buttons = day.find_elements("css selector", detail_sel["time_slot_button"])
    tbtn = time_buttons[perf["time_index"]]

    sb.execute_script("arguments[0].scrollIntoView({block:'center'});", tbtn)
    tbtn.click()
    sb.sleep(1.5)

    return sb.get_current_url()


def scrape_seats(sb, seat_sel):
    """Click every selectable seat in the currently-loaded seatmap and
    scrape its info card. Returns a list of seat dicts."""
    seats_out = []
    seats = sb.find_elements(seat_sel["seat"])
    print(f"    {len(seats)} selectable seats found")

    for idx in range(len(seats)):
        try:
            seats = sb.find_elements(seat_sel["seat"])  # re-query: DOM re-renders on click
            seat = seats[idx]

            sb.execute_script("arguments[0].scrollIntoView({block:'center'});", seat)
            sb.sleep(0.2)

            circle = seat.find_element("css selector", seat_sel["seat_circle"])
            circle.click()

            sb.wait_for_element(seat_sel["card"], timeout=5)
            sb.sleep(0.3)

            cards = sb.find_elements(seat_sel["card"])
            if not cards:
                continue
            card = cards[-1]
            data = scrape_card_text(card)
            seats_out.append(data)

            try:
                close_btn = card.find_element("css selector", seat_sel["card_close"])
                close_btn.click()
                sb.sleep(0.2)
            except Exception:
                pass

        except Exception as e:
            print(f"    [seat {idx}] error: {e}")
            continue

    return seats_out


# --------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------

def main():
    cfg = load_config(CONFIG_PATH)
    list_sel = cfg["selectors"]["list"]
    detail_sel = cfg["selectors"]["detail"]
    seat_sel = cfg["selectors"]["seatmap"]
    venue = cfg["venue"]
    cat_cfg = cfg["categories"]

    all_shows_out = []
    seat_rows_flat = []

    with SB(uc=True, headless=False) as sb:
        sb.activate_cdp_mode(cfg["urls"]["production_list"])
        sb.sleep(3)

        shows = scrape_show_list(sb, list_sel)
        print(f"Found {len(shows)} shows")

        for show in shows:
            category = classify_category(show["title"], cat_cfg)
            print(f"\n== {show['title']} ({category}) ==")

            try:
                performances = scrape_performances(sb, list_sel, detail_sel, show)
            except Exception as e:
                print(f"  error opening detail view: {e}")
                performances = []

            show_out = {
                "title": show["title"],
                "category": category,
                "venue": venue["name"],
                "address": venue["address"],
                "open_date": show["open_date"],
                "close_date": show["close_date"],
                "performances": [],
            }

            for perf in performances:
                print(f"  -- {perf['performance_date']} {perf['performance_time']} --")
                try:
                    booking_link = open_seatmap_for_performance(sb, detail_sel, perf)
                except Exception as e:
                    print(f"    could not open seatmap: {e}")
                    booking_link = None

                booking_locator = (
                    f"show='{show['title']}' date='{perf['performance_date']}' "
                    f"time='{perf['performance_time']}'"
                )

                try:
                    seats = scrape_seats(sb, seat_sel)
                except Exception as e:
                    print(f"    error scraping seats: {e}")
                    seats = []

                perf_out = {
                    "performance_date": perf["performance_date"],
                    "performance_time": perf["performance_time"],
                    "booking_link": booking_link,
                    "booking_locator": booking_locator,
                    "seats": seats,
                }
                show_out["performances"].append(perf_out)

                for seat in seats:
                    seat_rows_flat.append({
                        "title": show["title"],
                        "category": category,
                        "venue": venue["name"],
                        "address": venue["address"],
                        "open_date": show["open_date"],
                        "close_date": show["close_date"],
                        "performance_date": perf["performance_date"],
                        "performance_time": perf["performance_time"],
                        "booking_link": booking_link,
                        "booking_locator": booking_locator,
                        **seat,
                    })

            all_shows_out.append(show_out)

            # back to the list before the next show
            sb.go_back()
            sb.sleep(1)

    # --- write outputs ---
    with open(cfg["output"]["json_path"], "w", encoding="utf-8") as f:
        json.dump(all_shows_out, f, indent=2, ensure_ascii=False)
    print(f"\nWrote nested JSON to {cfg['output']['json_path']}")

    if seat_rows_flat:
        fieldnames = list(seat_rows_flat[0].keys())
        with open(cfg["output"]["seats_csv_path"], "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(seat_rows_flat)
        print(f"Wrote flat seat CSV to {cfg['output']['seats_csv_path']}")


if __name__ == "__main__":
    main()
