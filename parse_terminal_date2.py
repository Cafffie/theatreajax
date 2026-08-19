import datetime
import re
from dateutil import parser


def _parse_terminal_date(self, date_str: str | None) -> tuple[str | None, str | None]:
    """
    Parses date strings missing year information, such as:
      - 'Tue, Sep 01'
      - 'Sat, Sep 05 - Sat, Nov 07'
      - 'Sat, Sep 19 - Sun, Oct 04'
      - 'Sat, Jun 12 - Sun, Jun 27'

    Returns (open_date_ymd, close_date_ymd).
    """
    if not date_str:
        return None, None

    try:
        current_year = datetime.datetime.now().year  # 2026

        def _parse_single_token(token: str, year: int) -> datetime.date | None:
            """Cleans and converts a date string token like 'Sat, Sep 05' into a date object."""
            cleaned = token.strip()
            # Match standard pattern "Day, Month DD" e.g., "Sat, Sep 05"
            match = re.search(r"([A-Za-z]{3},\s+[A-Za-z]{3}\s+\d{1,2})", cleaned)
            if not match:
                return None

            date_with_year = f"{match.group(1)} {year}"
            return parser.parse(date_with_year).date()

        # Handle Date Ranges separated by '-'
        if "-" in date_str:
            parts = date_str.split("-")
            start_dt = _parse_single_token(parts[0], current_year)
            end_dt = _parse_single_token(parts[1], current_year)

            if start_dt and end_dt:
                # If end date is prior to start date (e.g., Nov 20 -> Jan 05 across new year),
                # increment the end year by 1
                if end_dt < start_dt:
                    end_dt = _parse_single_token(parts[1], current_year + 1)

                return start_dt.strftime("%Y-%m-%d"), end_dt.strftime("%Y-%m-%d")

        # Handle Single Date
        else:
            single_dt = _parse_single_token(date_str, current_year)
            if single_dt:
                date_ymd = single_dt.strftime("%Y-%m-%d")
                return date_ymd, date_ymd

    except Exception as e:
        self.custom_logger.debug(f"Failed parsing terminal date range '{date_str}': {e}")

    return None, None
