from flask import Flask, request, send_file, jsonify, url_for

import requests
import m3u8
import os
import ffmpeg
from flask_cors import CORS
import uuid
from flask import Blueprint

# 创建一个蓝图实例
vd_blueprint = Blueprint('vd_blueprint', __name__)

app = Flask(__name__)


CORS(app)

MAX_SIZE_MB = 10  # 设置最大文件大小限制
MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024  # 转换为字节

def check_total_size(m3u8_url):
    m3u8_obj = m3u8.load(m3u8_url)
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
    m3u8_obj = m3u8.load(m3u8_url)
    print(m3u8_obj)

    total_segments = len(m3u8_obj.segments)


    ts_files = []
    for index,segment in enumerate(m3u8_obj.segments):
        print(f"正在下载第 {index + 1}个,一共{total_segments}个")
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
    input_files = '|'.join(ts_files)
    ffmpeg.input(f"concat:{input_files}").output(output_filename, c='copy').run(overwrite_output=True)

@vd_blueprint.route('/download', methods=['POST'])
def download_video():
    data = request.json
    m3u8_url = data['m3u8_url']

    is_size_ok, total_size = check_total_size(m3u8_url)
    if not is_size_ok:
        return jsonify({'error': '暂不支持大视频,请见谅...'}), 400
    
    # Step 1: Download ts files
    ts_files = download_ts_files(m3u8_url)
    
    # Step 2: Merge ts files into mp4
    output_filename = f"{uuid.uuid4()}.mp4"
    merge_ts_to_mp4(ts_files, output_filename)
    
    # Step 3: Cleanup ts files
    for ts_file in ts_files:
        os.remove(ts_file)
    
    # Step 4: Send the mp4 file to the user
    download_url = url_for('vd_blueprint.download_file', filename=os.path.basename(output_filename), _external=True)

    return jsonify({'download_url': download_url})

@vd_blueprint.route('/downloads/<filename>')
def download_file(filename):
    return send_file(filename,as_attachment=True)

if __name__ == '__main__':
    app.register_blueprint(vd_blueprint,url_prefix='/vd')
    app.run(debug=True)
