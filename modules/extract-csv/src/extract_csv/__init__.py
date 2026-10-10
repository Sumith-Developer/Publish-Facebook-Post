import csv
import os
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class TaskStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"
    PENDING = "pending"


@dataclass(frozen=True, slots=True)
class CSVTask:
    row_index: int
    image_url: str
    message_string: str
    status: TaskStatus


class CSVTaskStore:
    IMAGE_URL = "IMAGE URL"
    MESSAGE_STRING = "MESSAGE STRING"
    STATUS = "STATUS"

    REQUIRED_COLUMNS = (
        IMAGE_URL,
        MESSAGE_STRING,
        STATUS,
    )

    def __init__(self, csv_path: Path | str) -> None:
        self.csv_path = Path(csv_path)

    def _read_csv(self) -> tuple[list[str], list[list[str]]]:
        with self.csv_path.open(
            mode="r",
            encoding="utf-8-sig",
            newline="",
        ) as file:
            rows = list(csv.reader(file))

        if not rows:
            return [], []

        headers = rows[0]

        if len(headers) != len(set(headers)):
            raise ValueError("CSV contains duplicate column names.")

        missing_columns = set(self.REQUIRED_COLUMNS) - set(headers)

        if missing_columns:
            raise ValueError(f"Missing required columns: {sorted(missing_columns)}")

        return headers, rows[1:]

    def _create_task(
        self,
        row_index: int,
        row: list[str],
        indexes: dict[str, int],
    ) -> CSVTask:
        if len(row) != len(indexes) and len(row) == 0:
            raise ValueError(f"Empty CSV row at index {row_index}.")

        if len(row) != self._header_length:
            raise ValueError(f"Invalid column count at data row {row_index + 1}.")

        image_url = row[indexes[self.IMAGE_URL]].strip()
        message_string = row[indexes[self.MESSAGE_STRING]].strip()
        status_value = row[indexes[self.STATUS]].strip()

        if not image_url:
            raise ValueError(f"IMAGE URL is empty at data row {row_index + 1}.")

        if not message_string:
            raise ValueError(f"MESSAGE STRING is empty at data row {row_index + 1}.")

        try:
            status = TaskStatus(status_value)
        except ValueError as exc:
            raise ValueError(
                f"Invalid STATUS at data row {row_index + 1}: {status_value!r}"
            ) from exc

        return CSVTask(
            row_index=row_index,
            image_url=image_url,
            message_string=message_string,
            status=status,
        )

    def get_all_tasks(self) -> list[CSVTask]:
        headers, rows = self._read_csv()

        if not headers:
            return []

        self._header_length = len(headers)
        indexes = {column: headers.index(column) for column in self.REQUIRED_COLUMNS}

        tasks: list[CSVTask] = []

        for row_index, row in enumerate(rows):
            if not row:
                continue

            tasks.append(self._create_task(row_index, row, indexes))

        return tasks

    def count_tasks(self) -> int:
        return len(self.get_all_tasks())

    def has_pending_tasks(self) -> bool:
        return any(task.status is TaskStatus.PENDING for task in self.get_all_tasks())

    def get_first_pending_task(self) -> CSVTask | None:
        for task in self.get_all_tasks():
            if task.status is TaskStatus.PENDING:
                return task

        return None

    def update_status(
        self,
        task: CSVTask,
        status: TaskStatus,
    ) -> CSVTask:
        headers, rows = self._read_csv()

        if not headers:
            raise ValueError("Cannot update an empty CSV file.")

        indexes = {column: headers.index(column) for column in self.REQUIRED_COLUMNS}

        self._header_length = len(headers)

        if not 0 <= task.row_index < len(rows):
            raise IndexError("Task row no longer exists.")

        row = rows[task.row_index]

        if not row:
            raise ValueError("Task row is empty.")

        current_task = self._create_task(
            task.row_index,
            row,
            indexes,
        )

        if (
            current_task.image_url != task.image_url
            or current_task.message_string != task.message_string
            or current_task.status is not task.status
        ):
            raise RuntimeError("Task has changed since it was retrieved.")

        row[indexes[self.STATUS]] = status.value

        self._write_csv(headers, rows)

        return CSVTask(
            row_index=task.row_index,
            image_url=task.image_url,
            message_string=task.message_string,
            status=status,
        )

    def _write_csv(
        self,
        headers: list[str],
        rows: list[list[str]],
    ) -> None:
        temporary_path: Path | None = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="",
                dir=self.csv_path.parent,
                delete=False,
            ) as file:
                temporary_path = Path(file.name)
                writer = csv.writer(file)
                writer.writerow(headers)
                writer.writerows(rows)

            os.replace(temporary_path, self.csv_path)

        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise
