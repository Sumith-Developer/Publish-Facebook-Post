from pathlib import Path

from extract_csv import CSVTaskStore
from verify_token import check_page_token
from workflow_schedule import WorkflowSchedule

from .utils.cron_generator import create_utc_cron
from .utils.cron_reader import read_cron_file


def main():
    if not check_page_token():
        raise RuntimeError(
            "Facebook Page token is invalid or lacks required permissions."
        )

    file_name = Path("data/cron_timing.txt")
    cron_data = read_cron_file(file_name)

    if not cron_data:
        raise ValueError("No cron data found in the specified file.")

    timezone_offset_hours = 5.5

    cron_strings = create_utc_cron(
        timezone_offset_hours=timezone_offset_hours,
        local_minutes=cron_data["minute"],
        local_hours=cron_data["hour"],
        days_of_week=cron_data["day_of_week"],
        days_of_month=cron_data["day_of_month"],
        months=cron_data["month"],
    )

    schedule_file = Path("data/schedule-posts.csv")

    if not schedule_file.exists():
        raise FileNotFoundError(f"Schedule file '{schedule_file}' does not exist.")

    store = CSVTaskStore(schedule_file)
    workflow_schedule = WorkflowSchedule(".github/workflows/post_scheduler.yml")

    if not store.has_pending_tasks():
        workflow_schedule.disable()
        raise RuntimeError("No pending tasks found in the schedule file.")

    for cron_string in cron_strings:
        workflow_schedule.update(cron_string)

    print("Cron jobs have been successfully set up and workflow schedule updated.")


if __name__ == "__main__":
    main()
