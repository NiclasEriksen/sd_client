import logging
import os
import tempfile
import asyncio
from typing import Union
import requests
import socket
from requests.exceptions import ConnectionError, ConnectTimeout, JSONDecodeError
from urllib3.exceptions import MaxRetryError, NewConnectionError
import uuid
from client.task import SDTask, DONE, ERROR, IDLE
from client.logger import logger
import signal


API_URL = os.environ.get("SD_API_URL", "http://127.0.0.1:5000")
UID_MISSING = False
CLIENT_UID = os.environ.get("SD_CLIENT_UID", uuid.uuid4().__str__())
CLIENT_NAME = os.environ.get("SD_CLIENT_NAME", socket.gethostname())
if not len(CLIENT_UID):
    UID_MISSING = True
    CLIENT_UID = uuid.uuid4().__str__()
TEST_MODE = os.environ.get("SD_TEST_MODE", "False").lower() in ('true', '1', 'yes', 'y')
CPU_MODE = os.environ.get("SD_CPU_MODE", "False").lower() in ('true', '1', 'yes', 'y')
try:
    VRAM = int(os.environ.get("SD_GPU_VRAM", 6))
except ValueError:
    VRAM = 6

CLIENT_VERSION = "0.4"

CLIENT_METADATA = {
    "test_mode": TEST_MODE,
    "cpu_mode": CPU_MODE,
    "vram": VRAM,
    "version": CLIENT_VERSION,
    "client_name": CLIENT_NAME,
    "client_uid": CLIENT_UID
}

messages = {
    "facefix1":     "    Fixing 😊 's in 🖼  using CodeFormer...",
    "upscale":      "    Upscaling 🖼  using real-ESRGAN...",
    "facefix2":     "    Fixing 😊 's in big 🖼  using CodeFormer...",
    "begin":        "Generating 🖼  :"
}


class ListenFilter(logging.Filter):
    def filter(self, record):
        if record.getMessage().startswith():
            pass
        return True

"    "

logger.debug(CLIENT_METADATA)
logger.debug("CUDA_VISIBLE_DEVICES={0}".format(os.environ.get("CUDA_VISIBLE_DEVICES", -1)))


loop = asyncio.get_event_loop()
current_task_id = -1


def quit_handler(signum, frame):
    msg = "A stop has been requested, attempting to kill AI process..."
    logger.warning(msg)
    if current_task_id >= 0:
        logger.info("Trying to report task as failed...")
        report_failed(current_task_id)
    loop.stop()
    exit(1)


def task_callback(t: SDTask):
    if t.status == DONE:
        logger.info("Task finished successfully")
    elif t.status == ERROR:
        logger.error("Task seems to have failed.")
    else:
        logger.info("Update from task {0}".format(t))


def run_client() -> bool:
    try:
        result = requests.put(
            API_URL + "/register_client", json=CLIENT_METADATA
        )
    except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
        logger.error(e)
        logger.critical("ERROR DURING CONNECTION")
        return False
    else:
        try:
            resp = result.json()
        except JSONDecodeError:
            logger.error("We got invalid data from server when trying to register client. Aborting")
            return False
        if "status" in resp:
            if resp["status"] != ERROR:
                logger.info("Connected and registered on server!")
                logger.info("Name: \"{0}\" UUID: \"{1}\"".format(CLIENT_NAME, CLIENT_UID))
                logger.info("Client version: \"{0}\" Reported VRAM: {1}G".format(CLIENT_VERSION, VRAM))
                if UID_MISSING:
                    logger.critical("Remember to add this UUID to your .env file!")
                return True
            elif resp["status"] == ERROR:
                if "message" in resp:
                    logger.error(resp["message"])
                else:
                    logger.error(resp)
                return False
    logger.error(resp)
    logger.critical("Unknown error when registering on server, aborting.")
    return False


async def report_done(task: SDTask):
    if task.status == DONE:
        try:
            result = requests.post(
                API_URL + "/report_complete/{0}".format(task.task_id),
                files={"file": open(task.image_file.name, 'rb')}
            )
            if result.status_code == 200:
                # logger.debug(result.json())
                resp = result.json()
                if resp["status"] == DONE:
                    logger.info("Task has been reported as done and uploaded!")
                else:
                    logger.error("Error during reporting of task:")
                    logger.error(resp["message"])

            else:
                logger.debug(result.status_code)
                logger.debug(result.content)
                logger.warning(result.reason)
                logger.warning(result.text)
                report_failed(task.task_id)

        except (
                ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError,
                JSONDecodeError
        ) as e:
            logger.debug(e)
            logger.error("Error when reporting task status, is server down?")
            report_failed(task.task_id)
    else:
        report_failed(task.task_id)


def report_failed(task_id):
    try:
        result = requests.put(
            API_URL + "/report_failed/{0}".format(task_id),
            json=CLIENT_METADATA
        )
        logger.debug(result.json())
        logger.warning("Task has been reported as failed!")
    except (
    ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError, JSONDecodeError) as e:
        logger.error("Error when reporting task failure, is server down?")


async def task_runner():
    current_task: Union[SDTask, None] = None
    global current_task_id
    while True:
        if current_task:
            current_task_id = current_task.task_id
            if current_task.ready and current_task.status == IDLE:
                await current_task.process_task(gpu=0, test_run=TEST_MODE)
            elif current_task.status == DONE or current_task.status == ERROR:
                await report_done(current_task)
                current_task.image_file.close()
                current_task.input_image_file.close()
                current_task = None
        else:
            current_task_id = -1
            try:
                result = requests.put(API_URL + "/process_task/" + CLIENT_UID, json=CLIENT_METADATA, headers={'Cache-Control': 'no-cache'})
            except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
                logger.error("Error when requesting task update, is server down? Retrying in 10 seconds.")
                await asyncio.sleep(9)
            else:
                try:
                    if "task_id" in result.json():
                        logger.info("New task received, adding to queue.")
                        image_file = tempfile.NamedTemporaryFile(
                            prefix="aigen_",
                            suffix=".jpg"
                        )
                        input_image_file = tempfile.NamedTemporaryFile(
                            prefix="aigen_input_",
                            suffix=".jpg"
                        )
                        current_task = SDTask(
                            out_file=image_file,
                            in_file=input_image_file,
                            json_data=result.json(),
                            callback=task_callback
                        )
                        current_task_id = current_task.task_id
                except JSONDecodeError:
                    logger.debug(result)
                    logger.debug(result.content)
                    logger.error("Empty response from server, invalid request?")

        await asyncio.sleep(1.0)


async def poller():
    while True:
        try:
            _result = requests.get(API_URL + "/poll", json=CLIENT_METADATA )
        except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
            logger.warning("Polling failed! Is server down?")
        await asyncio.sleep(10)


async def test_task():
    image_file = tempfile.NamedTemporaryFile(
        prefix="test_",
        suffix=".jpg"
    )
    test_data = {
        'task_id': -1, 'prompt': 'Test machines under heavy load', 'prompt_strength': 7.0, 'steps': 1,
        'seed': 123456, 'width': 64, 'height': 64, 'upscale': False, 'fix_faces': False, 'tileable': False,
        'input_image_url': '', 'status': 1
    }
    task = SDTask(
        out_file=image_file,
        json_data=test_data,
        callback=task_callback
    )
    await task.process_task()


async def main():
    connected = run_client()
    if not connected:
        return
    stop_event = asyncio.Event()
    if not TEST_MODE:
        logger.info("Running test task...")
        await test_task()
    logger.info("Starting processing task.")
    asyncio.get_event_loop().create_task(task_runner())
    logger.info("Starting polling task.")
    asyncio.get_event_loop().create_task(poller())
    logger.info("Waiting for suitable tasks from server...")
    await stop_event.wait()


if __name__ == "__main__":
    signal.signal(signal.SIGINT, quit_handler)
    signal.signal(signal.SIGTERM, quit_handler)
    asyncio.run(main())
