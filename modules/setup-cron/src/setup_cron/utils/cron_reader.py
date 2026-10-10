from typing import TypedDict


def parse_cron_component(
    component: str,
    min_val: int,
    max_val: int,
) -> list[int] | str:
    """
    Parse a single cron component.

    Supports:
    - Wildcard: *
    - Lists: 1,5,10
    - Ranges: 1-5
    - Steps: */5, 1-10/2
    - Mixed expressions: 1,5-10/2,20
    """
    if not component:
        raise ValueError("Cron component cannot be empty.")

    parts = component.split(",")

    if "*" in parts and len(parts) == 1:
        return "*"

    result = set()

    for part in parts:
        if not part:
            raise ValueError(f"Invalid empty cron component in '{component}'.")

        step = 1

        if "/" in part:
            if part.count("/") != 1:
                raise ValueError(f"Invalid step expression: '{part}'.")

            base, step_text = part.split("/", 1)

            try:
                step = int(step_text)
            except ValueError as exc:
                raise ValueError(f"Invalid step value in '{part}'.") from exc

            if step <= 0:
                raise ValueError(f"Step must be greater than zero: '{part}'.")

            part = base

        if part == "*":
            start = min_val
            end = max_val
        elif "-" in part:
            if part.count("-") != 1:
                raise ValueError(f"Invalid range expression: '{part}'.")

            start_text, end_text = part.split("-", 1)

            try:
                start = int(start_text)
                end = int(end_text)
            except ValueError as exc:
                raise ValueError(f"Invalid range expression: '{part}'.") from exc

            if start < min_val or end > max_val:
                raise ValueError(
                    f"Range {start}-{end} is out of bounds ({min_val}-{max_val})."
                )

            if start > end:
                raise ValueError(
                    f"Range start cannot be greater than range end: '{part}'."
                )
        else:
            try:
                start = int(part)
            except ValueError as exc:
                raise ValueError(f"Invalid cron value: '{part}'.") from exc

            end = start

        if start < min_val or end > max_val:
            raise ValueError(
                f"Value {start}-{end} is out of bounds ({min_val}-{max_val})."
            )

        result.update(range(start, end + 1, step))

    if not result:
        raise ValueError(f"Invalid cron component: '{component}'.")

    return sorted(result)


class CronData(TypedDict):
    raw_expression: str
    minute: list[int] | str
    hour: list[int] | str
    day_of_month: list[int] | str
    month: list[int] | str
    day_of_week: list[int] | str


def read_cron_file(file_path) -> CronData | None:
    limits = [
        ("minute", 0, 59),
        ("hour", 0, 23),
        ("day_of_month", 1, 31),
        ("month", 1, 12),
        ("day_of_week", 0, 7),
    ]

    try:
        with open(file_path, "r", encoding="utf-8") as file:
            cron_string = file.read().strip()

        if not cron_string:
            raise ValueError("Cron file is empty.")

        parts = cron_string.split()

        if len(parts) != 5:
            raise ValueError(f"Expected 5 fields, found {len(parts)}.")

        cron_dict: CronData = {
            "minute": "",
            "hour": "",
            "day_of_month": "",
            "month": "",
            "day_of_week": "",
            "raw_expression": cron_string,
        }

        for i, (field_name, min_val, max_val) in enumerate(limits):
            value = parse_cron_component(
                parts[i],
                min_val,
                max_val,
            )

            if field_name == "day_of_week":
                if value == "*":
                    value = "*"
                else:
                    value = sorted({0 if day == 7 else day for day in value})

            cron_dict[field_name] = value

        return cron_dict

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' does not exist.")
        return None

    except ValueError as e:
        print(f"Error parsing file: {e}")
        return None
