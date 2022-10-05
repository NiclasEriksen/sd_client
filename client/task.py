import asyncio
import os
import random
import shutil
from tempfile import NamedTemporaryFile
from typing import Union

import imaginairy.api
import requests
from requests.exceptions import SSLError
from logging import Filter
from client.logger import logger, PROGRESS_LEVEL
from imaginairy import ImaginePrompt, imagine, WeightedPrompt, samplers
from imaginairy.samplers import plms

from client.parse_prompt import parse_prompt

imaginairy.api.logger = logger
imaginairy.schema.logger = logger
plms.logger = logger

IDLE = 0
PROCESSING = 1
DONE = 2
ERROR = 3



class IntegrityError(Exception):
    pass


class SDTask():
    image_file: NamedTemporaryFile = None
    input_image_file: NamedTemporaryFile =None
    input_image_url: str = ""
    input_image_downloaded: bool = False
    prompt: str = "No prompt"
    prompt_strength: float = 0.8
    steps: int = 40
    seed: int = 0
    status: int = IDLE
    width: int = 512
    height: int = 512
    task_id: int = -1
    fix_faces: bool = False
    upscale: bool = False
    tileable: bool = False
    nsfw = False
    callback = None
    result = None
    gpu: int = 0
    progress: float = 0.0

    def __init__(self, out_file: NamedTemporaryFile=None, in_file: NamedTemporaryFile=None, json_data=None, callback=None):
        if isinstance(json_data, dict):
            self.from_json(json_data)
        self.callback = callback
        self.image_file = out_file
        self.input_image_file = in_file

    async def download_input_image(self):
        if not len(self.input_image_url):
            return
        try:
            try:
                result = requests.get(self.input_image_url)
            except SSLError:
                logger.debug("HTTPS error, trying HTTP")
                result = requests.get(self.input_image_url.replace("https", "http"))
        except Exception as e:
            logger.debug(e)
            logger.error("Unable to download input image.")
            return
        else:
            if result.status_code == 200:
                self.input_image_file.write(result.content)
                logger.info("Saved input image as a temporary file.")
                self.input_image_downloaded = True
            else:
                logger.debug(result)
                logger.error("Failure to get input image.")

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

        if "steps" in data:
            try:
                self.steps = int(data["steps"])
            except ValueError:
                self.steps = 40
        else:
            self.steps = 40


        if "seed" in data:
            try:
                self.seed = int(data["seed"])
            except ValueError:
                self.seed = random.randrange(0, 100000)
        else:
            self.seed = random.randrange(0, 100000)

        if "width" in data and "height" in data:
            try:
                self.width = int(data["width"])
                self.height = int(data["height"])
                assert self.width % 64 == 0 and self.width > 0
                assert self.height % 64 == 0 and self.height > 0
            except (ValueError, AssertionError, TypeError):
                logger.warning("Invalid value for width/height, defaulting to 512")
                self.width = 512
                self.height = 512

        if "fix_faces" in data:
            if isinstance(data["fix_faces"], bool):
                self.fix_faces = data["fix_faces"]
        if "upscale" in data:
            if isinstance(data["upscale"], bool):
                self.upscale = data["upscale"]
        if "tileable" in data:
            if isinstance(data["tileable"], bool):
                self.tileable = data["tileable"]

        if "input_image_url" in data:
            self.input_image_url = data["input_image_url"]

        logger.debug(data)

    @property
    def ready(self) -> bool:
        if not len(self.prompt) or not self.task_id >= 0:
            return False
        return True

    async def process_task(self, gpu=0, test_run=False):
        self.gpu = gpu
        # os.environ["CUDA_VISIBLE_DEVICES"] = str(gpu)
        logger.info("Starting task process (this might take a while)")
        logger.info("Prompt: \x1b[35;1m\"{0}\"\x1b[0m".format(self.prompt))
        self.status = PROCESSING
        await self.download_input_image()

        parsed_prompt = parse_prompt(self.prompt)
        if isinstance(parsed_prompt, list):
            prompt = [WeightedPrompt(p[0], weight=p[1]) for p in parsed_prompt]
        else:
            prompt = parsed_prompt

        ip = ImaginePrompt(
            prompt,
            prompt_strength=self.prompt_strength,
            steps=self.steps,
            width=self.width,
            height=self.height,
            seed=self.seed,
            fix_faces=self.fix_faces,
            init_image=self.input_image_file.name if self.input_image_downloaded else None,
            upscale=self.upscale,
            tile_mode=self.tileable
        )
        if test_run:
            await asyncio.sleep(10)
            shutil.copyfile("client/missing.jpg", self.image_file.name)
        else:
            loop = asyncio.get_running_loop()
            _result = await loop.run_in_executor(None, imagine_process, ip, self)

        file_size = os.path.getsize(self.image_file.name)
        if file_size < 100 and not test_run: # Just in case
            self.status = ERROR
        else:
            self.status = DONE
        if self.callback:
            self.callback(self)


def imagine_process(ip: ImaginePrompt, task: SDTask):

    try:
        for result in imagine([ip]):
            if result != None:
                if "upscaled" in result.images:
                    logger.info("Saving upscaled image...")
                    result.save(task.image_file.name, image_type="upscaled")
                elif "modified_original" in result.images:
                    logger.info("Saving modified image...")
                    result.save(task.image_file.name, image_type="modified_original")
                else:
                    logger.info("Saving generated image...")
                    result.save(task.image_file.name)
                task.nsfw = result.is_nsfw

    except Exception as e:
        logger.error(e)
        logger.error("AI generation failed.")

