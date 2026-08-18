
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
