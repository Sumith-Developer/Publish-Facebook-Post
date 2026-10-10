from pathlib import Path

from extract_csv import CSVTaskStore
from workflow_schedule import WorkflowSchedule


def main():
    schedule_file = Path("data/schedule-posts.csv")
    store = CSVTaskStore(schedule_file)

    if not store.has_pending_tasks():
        workflow_file = Path(".github/workflows/post_scheduler.yml")
        workflow_schedule = WorkflowSchedule(workflow_file)
        workflow_schedule.disable()
        print("No pending tasks found. Workflow schedule has been disabled.")
    else:
        print("Pending tasks found. Workflow schedule remains active.")


if __name__ == "__main__":
    main()
