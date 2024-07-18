from flask import Flask, g,request, send_file, jsonify, url_for,Response
import os
from flask_cors import CORS
import uuid
from flask import Blueprint
from queue import Queue, Empty
import threading
from download import async_download_video,SAVE_DIR
from sse_manager import clients,remove_client
import logging
from logging.handlers import RotatingFileHandler
import time

#日志配置
#确保logs文件夹存在，如果不存在则创建
log_folder = './logs'
os.makedirs(log_folder, exist_ok=True)

# 将文件大小设置为 10MB
max_size_mb = 10
max_size_bytes = max_size_mb * 1024 * 1024

# 配置 RotatingFileHandler，设置日志文件名、大小和备份数量
handler = RotatingFileHandler(f'{log_folder}/app.log', maxBytes=max_size_bytes, backupCount=3)

# 配置日志记录器，添加 RotatingFileHandler
logging.basicConfig(
    level=logging.DEBUG,  # 日志级别
    format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',  # 日志格式
    handlers=[handler]  # 添加 RotatingFileHandler
)

# 蓝图
vd_blueprint = Blueprint('vd_blueprint', __name__)
app = Flask(__name__)

#处理跨域
CORS(app)


@vd_blueprint.route('/download', methods=['POST'])
def download_video():
    """
    处理视频下载请求，创建新线程执行下载任务

    返回包含下载视频 UUID 的 json 响应

    """
    
    data = request.json
    m3u8_url = data['m3u8_url']
    logging.debug(f"Received request with m3u8_url: {m3u8_url}")

    file_uuid = str(uuid.uuid4())

    download_url = url_for('vd_blueprint.download_file', filename=os.path.basename(f"{file_uuid}.mp4"), _external=True)


    download_thread = threading.Thread(target=async_download_video, args=(file_uuid,m3u8_url,download_url))
    download_thread.start()

    return jsonify({'file_uuid': file_uuid})

@vd_blueprint.route('/downloads/<filename>')
def download_file(filename):
    """
    处理视频下载请求，返回视频文件
    """
    return send_file(os.path.join(SAVE_DIR,filename),as_attachment=True)

@vd_blueprint.route('/stream/<file_uuid>')
def stream(file_uuid):
    """
    实时获取下载进度
    """

    def event_stream(file_uuid):
        while True:
            logging.debug(f"event_stream:{file_uuid}")
            try:
                event_type, msg = clients[file_uuid].get_nowait()
                if event_type == 'error' or event_type == 'success':
                    remove_client(file_uuid)

                yield f'event: {event_type}\ndata: {msg}\n\n'
            except Empty:
                continue
            except KeyError:
                break
            finally:
                time.sleep(0.1)


    if file_uuid not in clients:
        clients[file_uuid] = Queue(maxsize=1)
    

    return Response(event_stream(file_uuid), mimetype="text/event-stream")

app.register_blueprint(vd_blueprint,url_prefix='/vd')
if __name__ == '__main__':
    app.run(debug=True)
