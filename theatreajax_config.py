"""Configuration for Hallforcornwall Theatre scraper."""

SITE_ID = "hall_for_cornwall"
BASE_URL = "https://www.hallforcornwall.co.uk/"
RUN_HEADLESS = True
DEFAULT_CURRENCY = "GBP"

PAGES = [
    (f"{BASE_URL}whats-on/?category=plays-drama", "Play"),
    

PAGES = [
    ("https://ci.ovationtix.com/34919", None),
]


COOKIE_BTN_XPATH = (
    "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']"
)

DEFAULT_CURRENCY = "USD"

# Fallback venue details when a show's own page doesn't surface a distinct
# venue name (most mainstage shows are at the home venue below).
DEFAULT_THEATRE_DETAILS = {
    "venue": "Theatre Jacksonville",
    "address": "2032 San Marco Blvd",
    "city": "Jacksonville, FL 32207",
    "country": "United States",
}

# Keyed by a lowercase substring that might appear in a show's venue text.
# "HAB" matched the "Theatre for Babies 2026" listing subtitle
# ("at HAB 4001 Hendricks Avenue Jacksonville, FL 32207") — a different
# building than the main house. Add more overrides here as they surface.
THEATRE_DETAILS_MAP = {
    "hab": {
        "venue": "HAB",
        "address": "4001 Hendricks Avenue",
        "city": "Jacksonville, FL 32207",
        "country": "United States",
    },
}

# Single listing page; category isn't split across separate listing URLs the
# way qpac's whats-on pages are, so category is classified per-title instead
# (see CATEGORY_MAP below). Kept as a list of (url, category) tuples so the
# extractor loop shape matches qpac's — category is just always None here.



SELECTORS = {
    "cookie_button": "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']",
    "event_description": ".prodDescriptionCollapsed p",
    "see_event_button": ".ot_ci_productionInfoSelect button.btn.ot_primaryButton.ot_prodInfoButton,
    "title": "section.ot_prodListSection .ot_info h1",
    "subtitle": "section.ot_prodListSection .ot_info h6",
    "terminal_date": ".ot_ci_productionInfoSelect span.ot_ci_tag",
    "date_blocks": "li.events",
    "booking_url": ".BookingList_btn a",
    "raw_date_text": "h5.ot_eventDateTitle .date",
    "raw_time_text": "div.ot_calendarTimeSlots button.ot_timeSlotBtn",
    "seat": "g.ot_seat.selectable",
    "seat_circle": "circle.bg",
    "card": "[class*='card'], [class*='seat-info'], [class*='SeatCard']",
    "card_close": "[class*='close'], button[aria-label='Remove'], svg[class*='close']",
}
