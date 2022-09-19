import asyncio

IDLE = 0
PROCESSING = 1
DONE = 2
ERROR = 3


class IntegrityError(Exception):
    pass


class SDTask():
    run_id: str = ""
    prompt: str = "No prompt"
    strength: float = 0.8
    n_samples: int = 1
    n_rows: int = 1
    n_iter: int = 1
    seed: str = ""
    status: int = IDLE
    task_id: int = -1
    callback = None

    def __init__(self, json_data=None, callback=None):
        if isinstance(json_data, dict):
            self.from_json(json_data)
        self.callback = callback

    def from_json(self, data: dict):
        self.status = IDLE

        try:
            assert "prompt" in data
            assert "run_id" in data
            assert "task_id" in data
        except AssertionError:
            raise IntegrityError("Prompt or run_id missing from json data.")

        self.prompt = data["prompt"]
        self.run_id = data["run_id"]
        try:
            self.task_id = int(data["task_id"])
        except ValueError:
            raise IntegrityError("Task ID is not an integer, no way to trace this back.")

        if "n_samples" in data:
            try:
                self.n_samples = max(1, int(data["n_samples"]))
            except ValueError:
                self.n_samples = 1
        else:
            self.n_samples = 1

        if "n_rows" in data:
            try:
                self.n_rows = int(data["n_rows"])
            except ValueError:
                self.n_rows = self.n_samples
        else:
            self.n_rows = self.n_samples


        if "n_iter" in data:
            try:
                self.n_iter = max(1, int(data["n_iter"]))
            except ValueError:
                self.n_iter = 1
        else:
            self.n_iter = 1

        if "strength" in data:
            try:
                self.strength = min(1.0, max(0.01, float(data["strength"])))
            except ValueError:
                self.strength = 0.8
        else:
            self.strength = 0.8

    @property
    def ready(self) -> bool:
        if not len(self.prompt) or not len(self.run_id) or self.status != IDLE:
            return False
        return True

    async def process_task(self):
        print("Starting task")
        self.status = PROCESSING
        await asyncio.sleep(5)
        self.status = DONE
        if self.callback:
            self.callback(self)

