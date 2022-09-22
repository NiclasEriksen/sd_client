import asyncio
from imaginairy import ImaginePrompt, imagine

IDLE = 0
PROCESSING = 1
DONE = 2
ERROR = 3


class IntegrityError(Exception):
    pass


class SDTask():
    prompt: str = "No prompt"
    prompt_strength: float = 0.8
    steps: int = 40
    seed: str = ""
    status: int = IDLE
    width: int = 512
    height: int = 512
    task_id: int = -1
    callback = None
    result = None

    def __init__(self, json_data=None, callback=None):
        if isinstance(json_data, dict):
            self.from_json(json_data)
        self.callback = callback

    def from_json(self, data: dict):
        self.status = IDLE

        try:
            assert "prompt" in data
            assert "task_id" in data
        except AssertionError:
            raise IntegrityError("Prompt or task_id missing from json data.")

        self.prompt = data["prompt"]
        try:
            self.task_id = int(data["task_id"])
        except ValueError:
            raise IntegrityError("Task ID is not an integer, no way to trace this back.")

        if "prompt_strength" in data:
            try:
                self.prompt_strength = min(10.0, max(0.01, float(data["prompt_strength"])))
            except ValueError:
                self.prompt_strength = 6.5
        else:
            self.prompt_strength = 6.5

        if "width" in data and "height" in data:
            try:
                self.width = int(data["width"])
                self.height = int(data["height"])
                assert self.width % 64 == 0
                assert self.height % 64 == 0
            except (ValueError, AssertionError, TypeError):
                print("Invalid value for width/height, defaulting to 512")
                self.width = 512
                self.height = 512

    @property
    def ready(self) -> bool:
        if not len(self.prompt) or not self.task_id >= 0 or self.status != IDLE:
            return False
        return True

    async def process_task(self):
        print("Starting task")
        self.status = PROCESSING

        ip = ImaginePrompt(
            self.prompt,
            prompt_strength=self.prompt_strength,
            steps=self.steps,
            width=self.width,
            height=self.height,
            seed=self.seed
        )

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, imagine_process, ip, "out.jpg")

        self.status = DONE
        if self.callback:
            self.callback(self)


def imagine_process(ip: ImaginePrompt, save_path: str):
    result = None
    for r in imagine([ip]):
        result = r
        break
    result.save(save_path)
