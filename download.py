from sse_manager import clients
from queue import Queue, Empty
import threading
import requests
import m3u8
import ffmpeg
import os
import uuid

MAX_SIZE_MB = 1024  # 设置最大文件大小限制
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024  # 转换为字节

thread_local = threading.local()

def send_message(file_uuid,message,event_type):
    if file_uuid not in clients:
        clients[file_uuid] = Queue(maxsize=1)
    try:
        # 尝试将消息放入队列，如果队列已满，先清空再放入新消息
        clients[file_uuid].put_nowait((event_type, message))
    except:
        clients[file_uuid].get()  # 清空队列
        clients[file_uuid].put_nowait((event_type, message))
    

def check_total_size(m3u8_url):
    send_message(thread_local.file_uuid,"正在检测视频大小...","progress")
    try:
        m3u8_obj = m3u8.load(m3u8_url)
    except Exception as e:
        send_message(thread_local.file_uuid,"视频下载失败,请检查链接是否正确","error")
        return False, 0

    total_size = 0

    for segment in m3u8_obj.segments:
        ts_url = segment.uri
        if not ts_url.startswith('http'):
            ts_url = m3u8_obj.base_uri + ts_url
        response = requests.head(ts_url)
        if 'Content-Length' in response.headers:
            total_size += int(response.headers['Content-Length'])

        # 检查是否超过大小限制
        if total_size > MAX_SIZE_BYTES:
            return False, total_size

    return True, total_size

def download_ts_files(m3u8_url):
    send_message(thread_local.file_uuid,"开始下载视频...","progress")
    m3u8_obj = m3u8.load(m3u8_url)
    
    total_segments = len(m3u8_obj.segments)


    ts_files = []
    for index,segment in enumerate(m3u8_obj.segments):
        send_message(thread_local.file_uuid,f"正在下载({index + 1}/{total_segments})","progress")
        # print(f"正在下载第 {index + 1}个,一共{total_segments}个")
        ts_url = segment.uri
        if not ts_url.startswith('http'):
            ts_url = m3u8_obj.base_uri + ts_url

        ts_content = requests.get(ts_url).content
        ts_filename = f"{uuid.uuid4()}.ts"
        with open(ts_filename, 'wb') as f:
            f.write(ts_content)
        ts_files.append(ts_filename)
    return ts_files

def merge_ts_to_mp4(ts_files, output_filename):
    send_message(thread_local.file_uuid,"开始合并视频...","progress")
    input_files = '|'.join(ts_files)
    ffmpeg.input(f"concat:{input_files}").output(output_filename, c='copy').run(overwrite_output=True)

def async_download_video(file_uuid,m3u8_url,download_url):

    thread_local.file_uuid = file_uuid
    is_size_ok, total_size = check_total_size(m3u8_url)
    if not is_size_ok:
        send_message(file_uuid,"视频过大,暂不支持","error")
        return


    ts_files = download_ts_files(m3u8_url)
    output_filename = f"{file_uuid}.mp4"
    merge_ts_to_mp4(ts_files, output_filename)
    for ts_file in ts_files:
        os.remove(ts_file)
    send_message(file_uuid,download_url,"success")