clients = {}
from queue import Queue, Empty


def send_message(file_uuid,message,event_type):
    if file_uuid not in clients:
        clients[file_uuid] = Queue(maxsize=1)
    try:
        # 尝试将消息放入队列，如果队列已满，先清空再放入新消息
        clients[file_uuid].put_nowait((event_type, message))
    except:
        clients[file_uuid].get()  # 清空队列
        clients[file_uuid].put_nowait((event_type, message))

