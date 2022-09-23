import os
import tempfile
import asyncio
import json
import requests
from requests.exceptions import ConnectionError, ConnectTimeout, JSONDecodeError
from urllib3.exceptions import MaxRetryError, NewConnectionError
import uuid
from client.task import SDTask, DONE, ERROR, IDLE
from client.logger import logger

API_URL = os.environ.get("SD_API_URL", "http://127.0.0.1:5000")

task_queue: list = []

loop = asyncio.get_event_loop()
client_uid = ""
client_name = ""


def apply_settings():
    data = {}
    if os.path.exists("client_info.json"):
        with open("client_info.json", "r+") as f:
            data = json.load(f)
    if not "client_uid" in data or not "client_name" in data:
        data = {"client_uid": "", "client_name": ""}
    if not len(data["client_uid"]):
        data["client_uid"] = uuid.uuid4().__str__()
    if not len(data["client_name"]):
        data["client_name"] = input("Pick a name for this client:\n").strip()

    global client_uid
    global client_name

    client_uid = data["client_uid"]
    client_name = data["client_name"].strip()

    with open("client_info.json", "w") as f:
        json.dump(data, f)


def task_callback(t: SDTask):
    if t.status == DONE:
        logger.info("Task finished successfully")
    elif t.status == ERROR:
        logger.error("Task seems to have failed.")
    else:
        logger.info("Update from task {0}".format(t))


def run_client() -> bool:
    resp = {}
    try:
        result = requests.put(
            API_URL + "/register_client/{0}".format(client_name), json={"client_uid": client_uid}
        )
    except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
        logger.error(e)
        logger.critical("ERROR DURING CONNECTION")
        return False
    else:
        resp = result.json()
        if "status" in resp:
            if resp["status"] != ERROR:
                logger.info("Connected and registered on server!")
                logger.info("Name: \"{0}\" UUID: \"{1}\"".format(client_name, client_uid))
                return True
    logger.error(resp)
    logger.critical("Unknown error when registering on server, aborting.")
    return False


async def report_done(task: SDTask):
    try:
        result = requests.post(
            API_URL + "/report_complete/{0}".format(task.task_id),
            files={"file": open(task.image_file.name,'rb')}
        )
        logger.debug(result.json())
        logger.info("Task has been reported as done and uploaded!")
    except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
        logger.error("Error when requesting task update, is server down? Retrying in 10 seconds.")


async def task_runner():
    while True:
        if len(task_queue):
            current_task: SDTask = task_queue[0]
            if current_task.ready and current_task.status == IDLE:
                await current_task.process_task()
            elif current_task.status == DONE:
                await report_done(current_task)
                current_task.image_file.close()
                task_queue.remove(current_task)
            elif current_task.status == ERROR:
                task_queue.remove(current_task)
        else:
            try:
                result = requests.get(API_URL + "/process_task", json={"client_uid": client_uid})
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
                        task = SDTask(image_file, json_data=result.json(), callback=task_callback)
                        task_queue.append(task)
                except JSONDecodeError:
                    logger.error("Empty response from server, invalid request?")
        await asyncio.sleep(1.0)


async def poller():
    while True:
        try:
            result = requests.get(API_URL + "/poll", json={"client_uid": client_uid})
        except (ConnectionError, ConnectTimeout, ConnectionRefusedError, MaxRetryError, NewConnectionError) as e:
            logger.warning("Polling failed! Is server down?")
        await asyncio.sleep(10)


async def main():
    connected = run_client()
    if not connected:
        return
    stop_event = asyncio.Event()
    logger.info("Starting processing task.")
    asyncio.get_event_loop().create_task(task_runner())
    logger.info("Starting polling task.")
    asyncio.get_event_loop().create_task(poller())
    logger.info("Waiting for tasks from server...")
    await stop_event.wait()


if __name__ == "__main__":
    apply_settings()
    asyncio.run(main())
