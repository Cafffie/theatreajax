"""Configuration for Theatre Ajax scraper."""

SITE_ID = "theatre_ajax"
BASE_URL = "https://ci.ovationtix.com/"
RUN_HEADLESS = True
DEFAULT_CURRENCY = "USD"

PAGES = [
    ("https://ci.ovationtix.com/34919", None),
]

COOKIE_BTN_XPATH = (
    "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']"
)

# Fallback venue details when a show's own page doesn't surface a distinct venue name
DEFAULT_THEATRE_DETAILS = {
    "venue": "Theatre Jacksonville",
    "address": "2032 San Marco Blvd",
    "city": "Jacksonville, FL 32207",
    "country": "United States",
}

THEATRE_DETAILS_MAP = {
    "hab": {
        "venue": "HAB",
        "address": "4001 Hendricks Avenue",
        "city": "Jacksonville, FL 32207",
        "country": "United States",
    },
}

SELECTORS = {
    "cookie_button": "//button[@id='CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll']",
    "event_description": ".prodDescriptionCollapsed p",
    "see_event_button": ".ot_ci_productionInfoSelect button.btn.ot_primaryButton.ot_prodInfoButton",
    # "title": ".ot_prodProductionCalendarListDetail h1",
    "show_card": "section.ot_prodListSection li.ot_prodListItem.ot_callout",
    "title": "section .ot_prodListSection .ot_info h1",
    "subtitle": "section.ot_prodListSection li.ot_prodListItem.ot_callout .ot_info h6",
    "terminal_date": "span.ot_ci_tag",  # .prodDescriptionCollapsed,
    "see_this_event_button": ".ot_ci_productionInfoSelect button.ot_primaryButton.ot_prodInfoButton",
    # "date_blocks2": ".ot_selectedEventInfoContainer span"
    "date_blocks": "ul li.events, .ot_selectedEventInfoContainer",
    "date_time_text": "li.events, .date",
    "date_button": "button.ot_timeSlotBtn",
    "raw_date_text": "h5.ot_eventDateTitle .date",
    "raw_time_text": "button.ot_timeSlotBtn",
    "seat": "g.ot_seat.selectable",
    "seat_group": "g.ot_seat",
    "seat_circle": "circle.bg",
    "card": "[class*='card'], [class*='seat-info'], [class*='SeatCard']",
    "card_close": "[class*='close'], button[aria-label='Remove'], svg[class*='close']",
    "sold_out": ".sold-out-message, .ot_soldOut",
    "time_buttons": "button.ot_timeSlotBtn",
    # "seatmap": "svg.seatmap, #seatmap",
    # "svg_seats": "g.ot_seat",
    "sold_out": ".sold-out-message, .ot_soldOut",
    "seatmap_container": "svg.seatmap, #seatmap, svg.ot_seatmap",
    "select_seatmap_button": "button:has(span[data-i18n-key='productionCalendar.selectSeatsFromMap'])",
                       
}
