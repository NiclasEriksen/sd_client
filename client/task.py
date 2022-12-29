import asyncio
import os
import random
import shutil
from tempfile import NamedTemporaryFile
from typing import Union

import requests
from PIL import Image
from requests.exceptions import SSLError
from client.logger import logger
import imaginairy.api
from imaginairy import ImaginePrompt, imagine, WeightedPrompt, samplers
from imaginairy.samplers import plms

from client.parse_prompt import parse_prompt

imaginairy.api.logger = logger
imaginairy.schema.logger = logger
# imaginairy.progress.logger = logger
plms.logger = logger

IDLE = 0
PROCESSING = 1
DONE = 2
ERROR = 3


class ModelType:
    ORIGINAL = "SD-1.4"
    NEW      = "SD-2.1"


class SamplerType:
    PLMS        = "plms"
    DDIM        = "ddim"
    KLMS        = "k_lms"
    KDPM2       = "k_dpm_2"
    KDPM2A      = "k_dpm_2_a"
    KDPMPP2M    = "k_dpmpp_2m"
    KDPMPP2SA    = "k_dpmpp_2s_a"
    K_EULER     = "k_euler"
    K_EULER_A   = "k_euler_a"
    K_HEUN      = "k_heun"


SAMPLER_TYPES = [
    SamplerType.PLMS,
    SamplerType.DDIM,
    SamplerType.KLMS,
    SamplerType.KDPM2,
    SamplerType.KDPM2A,
    SamplerType.KDPMPP2M,
    SamplerType.KDPMPP2SA,
    SamplerType.K_EULER,
    SamplerType.K_EULER_A,
    SamplerType.K_HEUN
]


class IntegrityError(Exception):
    pass


class SDTask():
    image_file: NamedTemporaryFile = None
    print_file: NamedTemporaryFile = None
    input_image_file: NamedTemporaryFile =None
    input_image_url: str = ""
    mask_image_file: NamedTemporaryFile =None
    mask_image_url: str = ""
    input_image_downloaded: bool = False
    mask_image_downloaded: bool = False
    input_image_strength: float = 0.3
    mask_prompt: str = ""
    mask_mode_replace: bool = True
    mask_mode_image: bool = False
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
    to_print: bool = False
    nsfw = False
    callback = None
    result = None
    gpu: int = 0
    progress: float = 0.0
    sampler: str = SamplerType.KDPMPP2M

    def __init__(
            self,
            out_file: NamedTemporaryFile=None,
            in_file: NamedTemporaryFile=None,
            mask_file: NamedTemporaryFile=None,
            print_file: NamedTemporaryFile=None,
            json_data=None, callback=None
    ):
        if isinstance(json_data, dict):
            self.from_json(json_data)
        self.callback = callback
        self.image_file = out_file
        self.input_image_file = in_file
        self.mask_image_file = mask_file
        self.print_file = print_file

    async def download_input_image(self):
        if len(self.input_image_url):
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

        if len(self.mask_image_url):
            try:
                try:
                    result = requests.get(self.mask_image_url)
                except SSLError:
                    logger.debug("HTTPS error, trying HTTP")
                    result = requests.get(self.mask_image_url.replace("https", "http"))
            except Exception as e:
                logger.debug(e)
                logger.error("Unable to download mask image.")
                return
            else:
                if result.status_code == 200:
                    self.mask_image_file.write(result.content)
                    logger.info("Saved mask image as a temporary file.")
                    self.mask_image_downloaded = True
                else:
                    logger.debug(result)
                    logger.error("Failure to get mask image.")

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

        if "input_image_strength" in data:
            self.input_image_strength = float(data["input_image_strength"])

        if "mask_prompt" in data:
            self.mask_prompt = data["mask_prompt"]

        if "mask_mode_replace" in data:
            self.mask_mode_replace = data["mask_mode_replace"]

        if "mask_image_url" in data:
            self.mask_image_url = data["mask_image_url"]

        if "mask_mode_image" in data:
            self.mask_mode_image = data["mask_mode_image"]

        if "to_print" in data:
            self.to_print = data["to_print"]

        if "sampler" in data:
            if data["sampler"] in SAMPLER_TYPES:
                self.sampler = data["sampler"]

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
            prompt=prompt,
            prompt_strength=self.prompt_strength,
            steps=self.steps,
            width=self.width,
            height=self.height,
            seed=self.seed,
            fix_faces=self.fix_faces,
            init_image=self.input_image_file.name if self.input_image_downloaded else None,
            mask_image=self.mask_image_file.name if (self.mask_image_downloaded and self.mask_mode_image) else None,
            init_image_strength=self.input_image_strength,
            upscale=self.upscale,
            tile_mode=self.tileable,
            mask_prompt=self.mask_prompt if len(self.mask_prompt) else None,
            mask_mode="replace" if self.mask_mode_replace else "keep",
            sampler_type=self.sampler,
            model=ModelType.NEW
        )
        if test_run:
            await asyncio.sleep(10)
            img = Image.open("client/missing.jpg", "r")
            img.save(self.image_file.name)
            # shutil.copyfile("client/missing.jpg", self.image_file.name)
        else:
            loop = asyncio.get_running_loop()
            _result = await loop.run_in_executor(None, imagine_process, ip, self)

        if self.to_print:
            file_size = os.path.getsize(self.print_file.name)
        else:
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
                img = None
                if "upscaled" in result.images:
                    logger.info("Saving upscaled image...")
                    img = result.images.get("upscaled", None)
                    # result.save(task.image_file.name, image_type="upscaled")
                elif "modified_original" in result.images:
                    logger.info("Saving modified image...")
                    img = result.images.get("modified_original", None)
                    # result.save(task.image_file.name, image_type="modified_original")
                else:
                    logger.info("Saving generated image...")
                    img = result.images.get("generated", None)
                    # result.save(task.image_file.name)
                task.nsfw = result.is_nsfw

                if img:
                    if task.to_print:
                        img.convert("CMYK").save(task.print_file, exif=result._exif(), compression=None, quality=100)
                    else:
                        img.convert("RGB").save(task.image_file.name, exif=result._exif(), quality=90)
                else:
                    raise FileNotFoundError("No image in result?")


    except Exception as e:
        logger.error(e)
        logger.error("AI generation failed.")

