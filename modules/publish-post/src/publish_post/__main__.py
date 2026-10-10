from pathlib import Path

from extract_csv import CSVTaskStore, TaskStatus
from verify_token import check_page_token

from .utils.download_image import download_google_drive_image
from .utils.publish_post import publish_page_photo


def main():
    if not check_page_token():
        raise RuntimeError(
            "Facebook Page token is invalid or lacks required permissions."
        )

    schedule_file = Path("data/schedule-posts.csv")
    store = CSVTaskStore(schedule_file)

    if not store.has_pending_tasks():
        raise RuntimeError("No pending tasks found in the schedule file.")

    task = store.get_first_pending_task()

    if task is None:
        raise RuntimeError("No pending tasks found in the schedule file.")

    try:
        downloaded_image = download_google_drive_image(task.image_url)
    except Exception as exc:
        store.update_status(task, TaskStatus.FAILED)
        raise RuntimeError(f"Failed to download image: {exc}") from exc

    try:
        result = publish_page_photo(task.message_string, downloaded_image)
    except Exception as exc:
        store.update_status(task, TaskStatus.FAILED)
        raise RuntimeError(f"Failed to publish post: {exc}") from exc
    else:
        store.update_status(task, TaskStatus.COMPLETED)
        print(f"Post published successfully: {result}")


if __name__ == "__main__":
    main()
