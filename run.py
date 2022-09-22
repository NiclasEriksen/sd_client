import asyncio
import socketio
import uuid
from socketio.exceptions import ConnectionError
from task import SDTask, DONE, ERROR

client_id: str = uuid.uuid4().__str__()
task_queue: list = []

loop = asyncio.get_event_loop()
sio = socketio.AsyncClient()


@sio.event
async def connect():
    print("I'm connected!")
    print("My UUID: " + client_id)
    await sio.emit("register_client", data={"uuid": client_id})


@sio.event
async def connect_error(data):
    print("The connection failed!")


@sio.event
async def disconnect():
    print("I'm disconnected!")


def task_callback(t: SDTask):
    if t.status == DONE:
        print("Task finished successfully")
    elif t.status == ERROR:
        print("Task seems to have failed.")
    else:
        print("Update from task {0}".format(t))


@sio.on("task")
async def receive_task(data):
    print('I received a task!!!')

    t = SDTask(json_data=data, callback=task_callback)
    if t.ready:
        task_queue.append(t)


async def run_client(stop_event) -> None:
    sio.stop_event = stop_event
    try:
        await sio.connect('https://ai.posterity.no/ws')
    except ConnectionError as e:
        print(e)
        stop_event.set()
    else:
        await sio.wait()


async def task_runner():
    while True:
        if len(task_queue):
            current_task: SDTask = task_queue[0]
            if current_task.ready:
                await current_task.process_task()
            elif current_task.status == DONE:
                await sio.emit("task_done", data=(current_task.task_id, None))
                task_queue.remove(current_task)
            elif current_task.status == ERROR:
                await sio.emit("task_error")
                task_queue.remove(current_task)
        await asyncio.sleep(0.1)


async def main():
    stop_event = asyncio.Event()
    asyncio.get_event_loop().create_task(run_client(stop_event))
    asyncio.get_event_loop().create_task(task_runner())
    await stop_event.wait()


if __name__ == "__main__":
    asyncio.run(main())