def _parse_terminal_date(self, date_str: str | None) -> tuple[str | None, str | None]:
    """
    Parses complex date strings like:
    'February 27, 28, March 4, 5, 6, 7, 11, 12, 13, 14, 2027'
    'April 17, 18, 22, 23, 24, 25, 29, 30, May 1, 2, 2027'
    Returns (open_date_ymd, close_date_ymd).
    """
    if not date_str:
        return None, None

    try:
        # Extract trailing 4-digit year
        year_match = re.search(r"\b(20\d\d)\b", date_str)
        if not year_match:
            return None, None
        year = year_match.group(1)

        # Remove the year from the processing text
        clean_text = date_str[:year_match.start()].strip()

        # Split into individual date segments by matching "[Month] [Day]" or isolated numbers
        # Pattern captures month names followed by day numbers, or standalone comma-separated days
        tokens = [t.strip() for t in clean_text.split(",") if t.strip()]

        parsed_dates = []
        current_month = None

        for token in tokens:
            # Check if token contains a Month name
            month_match = re.search(r"([A-Za-z]+)\s*(\d{1,2})?", token)
            if month_match:
                month_name = month_match.group(1)
                # Ensure it's a valid month string
                if month_name.lower() in [
                    "january", "february", "march", "april", "may", "june",
                    "july", "august", "september", "october", "november", "december"
                ]:
                    current_month = month_name
                
                # Extract day number if attached to the month name (e.g., 'February 27' or 'May 1')
                day_match = re.search(r"\d{1,2}", token)
                if day_match and current_month:
                    day = day_match.group(0)
                    dt = parser.parse(f"{current_month} {day}, {year}")
                    parsed_dates.append(dt)
            else:
                # Token is just a day number (e.g., '28' or '5')
                day_match = re.search(r"^\d{1,2}$", token)
                if day_match and current_month:
                    day = day_match.group(0)
                    dt = parser.parse(f"{current_month} {day}, {year}")
                    parsed_dates.append(dt)

        if not parsed_dates:
            return None, None

        parsed_dates.sort()
        open_date = parsed_dates[0].strftime("%Y-%m-%d")
        close_date = parsed_dates[-1].strftime("%Y-%m-%d")

        return open_date, close_date

    except Exception as e:
        self.custom_logger.debug(f"Failed parsing terminal date '{date_str}': {e}")
        return None, None
