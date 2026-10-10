from decimal import Decimal, InvalidOperation
from math import floor


def _normalize_component(
    value: list[int] | str,
    min_value: int,
    max_value: int,
) -> list[int]:
    if value == "*":
        return list(range(min_value, max_value + 1))

    if not isinstance(value, list):
        raise TypeError(f"Expected a list or '*', got {type(value).__name__}.")

    normalized = sorted(set(value))

    if not normalized:
        raise ValueError("Cron component cannot be empty.")

    if any(value < min_value or value > max_value for value in normalized):
        raise ValueError(f"Cron values must be within {min_value}-{max_value}.")

    return normalized


def _format_component(value: list[int] | str) -> str:
    if value == "*":
        return "*"

    return ",".join(str(item) for item in sorted(set(value)))


def _shift_days_of_week(
    days_of_week: list[int] | str,
    day_shift: int,
) -> list[int] | str:
    if days_of_week == "*":
        return "*"

    if not isinstance(days_of_week, list):
        raise TypeError(f"Expected a list or '*', got {type(days_of_week).__name__}.")

    return sorted({(day + day_shift) % 7 for day in days_of_week})


def _timezone_offset_to_minutes(
    timezone_offset_hours: float,
) -> int:
    try:
        offset = Decimal(str(timezone_offset_hours))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("timezone_offset_hours must be a valid number.") from exc

    total_minutes = offset * Decimal("60.0")

    if total_minutes != total_minutes.to_integral_value():
        raise ValueError(
            "timezone_offset_hours must resolve to a whole number of minutes."
        )

    total_minutes = int(total_minutes)

    if total_minutes <= -1439 or total_minutes >= 1440:
        raise ValueError("timezone_offset_hours must be between -23:59 and +23:59.")

    return total_minutes


def create_utc_cron(
    *,
    local_minutes: list[int] | str,
    local_hours: list[int] | str,
    timezone_offset_hours: float,
    days_of_week: str | list[int] = "1-5",
    days_of_month: str | list[int] = "*",
    months: str | list[int] = "*",
) -> list[str]:
    """
    Generate one or more UTC cron expressions for GitHub Actions.

    The function returns multiple expressions when different local times
    require different UTC day-of-week shifts.

    Exact day rollover conversion is only supported when day_of_month and
    month are unrestricted ('*'). This prevents generating an incorrect
    cron expression for calendar-boundary cases that cannot be represented
    exactly by standard 5-field cron syntax.
    """
    local_minutes = [0]
    minutes = _normalize_component(local_minutes, 0, 59)
    hours = _normalize_component(local_hours, 0, 23)

    if days_of_month != "*" or months != "*":
        restricted_calendar = True
    else:
        restricted_calendar = False

    if restricted_calendar:
        normalized_calendar_values = (
            days_of_month,
            months,
        )
    else:
        normalized_calendar_values = ("*", "*")

    offset_minutes = _timezone_offset_to_minutes(timezone_offset_hours)

    groups: dict[tuple[int, int], set[int]] = {}

    for local_hour in hours:
        for local_minute in minutes:
            local_total_minutes = local_hour * 60 + local_minute

            utc_total_minutes = local_total_minutes - offset_minutes

            day_shift = floor(utc_total_minutes / 1440)

            if day_shift != 0 and restricted_calendar:
                raise ValueError(
                    "Cannot exactly convert day-of-month or month "
                    "restrictions when timezone conversion crosses "
                    "a calendar day. Use '*' for day_of_month and "
                    "month, or handle the schedule separately."
                )

            utc_minutes_of_day = utc_total_minutes % 1440

            utc_hour = utc_minutes_of_day // 60
            utc_minute = utc_minutes_of_day % 60

            key = (utc_minute, day_shift)
            groups.setdefault(key, set()).add(utc_hour)

    cron_expressions = []

    for (utc_minute, day_shift), utc_hours in sorted(
        groups.items(),
        key=lambda item: (
            item[0][1],
            item[0][0],
        ),
    ):
        shifted_days_of_week = _shift_days_of_week(
            days_of_week,
            day_shift,
        )

        hours_str = ",".join(str(hour) for hour in sorted(utc_hours))

        days_of_month_value, months_value = normalized_calendar_values

        cron_expression = (
            f"{utc_minute} "
            f"{hours_str} "
            f"{_format_component(days_of_month_value)} "
            f"{_format_component(months_value)} "
            f"{_format_component(shifted_days_of_week)}"
        )

        cron_expressions.append(cron_expression)

    return cron_expressions
