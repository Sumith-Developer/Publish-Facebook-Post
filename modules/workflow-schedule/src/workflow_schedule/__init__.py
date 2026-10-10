from pathlib import Path

from ruamel.yaml import YAML


class WorkflowSchedule:
    DISABLED = "disabled-forever-never-trigger"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.yaml = YAML()

    def update(self, cron: str, manual: bool = True) -> None:
        if len(cron.split()) != 5:
            raise ValueError("Cron expression must contain five fields.")

        with self.path.open(encoding="utf-8") as file:
            workflow = self.yaml.load(file)

        workflow["on"] = {"schedule": [{"cron": cron}]}

        if manual:
            workflow["on"]["workflow_dispatch"] = None

        with self.path.open("w", encoding="utf-8") as file:
            self.yaml.dump(workflow, file)

    def disable(self) -> None:
        with self.path.open(encoding="utf-8") as file:
            workflow = self.yaml.load(file)

        workflow["on"] = {"repository_dispatch": {"types": [self.DISABLED]}}

        with self.path.open("w", encoding="utf-8") as file:
            self.yaml.dump(workflow, file)
