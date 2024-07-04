# app.py
import os
from flask import Flask, request, jsonify, render_template, url_for, send_from_directory
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from moviepy.editor import VideoFileClip, AudioFileClip
import video
import imageblur
import webcam

app = Flask(__name__)
app.config.update(
    APPLICATION_ROOT='/',
    PREFERRED_URL_SCHEME='http',
    SERVER_NAME=os.environ.get('SERVER_NAME', 'localhost:5006')  # 환경 변수에서 서버 네임 읽기
)

socketio = SocketIO(app)

# 파일 업로드를 위한 디렉토리 설정
TRAIN_FOLDER = './static/trains/'
TEST_FOLDER = './static/tests/'
OUTPUT_FOLDER = './static/outputs/'
app.config['TRAIN_FOLDER'] = TRAIN_FOLDER
app.config['TEST_FOLDER'] = TEST_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

def get_latest_file(directory, file_extensions):
    latest_file = None
    latest_time = 0

    for file_extension in file_extensions:
        files = [f for f in os.listdir(directory) if f.endswith(file_extension)]
        for file in files:
            file_path = os.path.join(directory, file)
            file_time = os.path.getmtime(file_path)
            if file_time > latest_time:
                latest_time = file_time
                latest_file = file_path

    return latest_file

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/camera')
def camera():
    return render_template('camera.html')

@app.route('/gallery')
def gallery():
    return render_template('gallery.html')

@app.route('/train')
def train():
    return render_template('train.html')

@app.route('/train_camera')
def train_camera():
    return render_template('train_camera.html')

@app.route('/train_gallery')
def train_gallery():
    return render_template('train_gallery.html')

@app.route('/camera_convert')
def camera_convert():
    result_video_url = url_for('get_result_webcam_video_with_audio')
    return render_template('camera_convert.html', result_video_url=result_video_url)

@app.route('/gallery_convert')
def gallery_convert():
    latest_file = get_latest_file(app.config['OUTPUT_FOLDER'], ['.jpg', '.mp4'])
    result_image_url = None
    result_video_url = None

    if latest_file:
        if latest_file.endswith('.jpg'):
            result_image_url = url_for('static', filename=f'outputs/{os.path.basename(latest_file)}')
        elif latest_file.endswith('.mp4'):
            result_video_url = url_for('static', filename=f'outputs/{os.path.basename(latest_file)}')

    return render_template('gallery_convert.html', result_image_url=result_image_url, result_video_url=result_video_url)

@app.route('/save_exclusion_image', methods=['POST'])
def save_exclusion_image():
    if 'train_photo' not in request.files:
        return jsonify({'error': 'No photo part in the request'}), 400

    train_photo = request.files['train_photo']
    if train_photo.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    filename = 'train_photo.png'
    save_path = os.path.join(app.config['TRAIN_FOLDER'], filename)
    app.logger.info(f'Saving train_photo to {save_path}')
    try:
        train_photo.save(save_path)
        app.logger.info('Photo successfully saved')
        return jsonify({'message': 'File successfully uploaded', 'redirect_url': url_for('index')}), 200
    except Exception as e:
        app.logger.error(f'Error saving photo: {e}')
        return jsonify({'error': 'Failed to save file'}), 500

@app.route('/process_image', methods=['POST'])
def process_image():
    if 'test_photo' not in request.files:
        return jsonify({'error': 'No photo part in the request'}), 400

    test_photo = request.files['test_photo']
    if test_photo.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    test_path = os.path.join(app.config['TEST_FOLDER'], 'test_photo.png')
    train_path = os.path.join(app.config['TRAIN_FOLDER'], 'train_photo.png')
    output_path = os.path.join(app.config['OUTPUT_FOLDER'], 'result_image.jpg')
    app.logger.info(f'Saving test photo to {test_path}')
    try:
        test_photo.save(test_path)
        app.logger.info('Test photo successfully saved')

        # imageblur 모듈을 사용하여 이미지 처리
        imgTrain, _ = imageblur.input_image(train_path)
        imgToProcess, original_size = imageblur.input_image(test_path)

        try:
            imageblur.process_image(imgTrain, imgToProcess, output_path, original_size)
        except ValueError as e:
            app.logger.error(f'Error processing image: {e}')
            return jsonify({'error': str(e)}), 400

        app.logger.info(f'Processed image saved to {output_path}')
        result_image_url = url_for('get_result_image')  # Generate URL for the result image

        # 요청이 gallery.html에서 왔는지 camera.html에서 왔는지에 따라 리디렉션 URL 설정
        if request.referrer and 'gallery' in request.referrer:
            redirect_url = url_for('gallery_convert')
        else:
            redirect_url = url_for('camera_convert')

        return jsonify({'message': 'Image successfully processed', 'result_image_url': result_image_url, 'redirect_url': redirect_url}), 200
    except Exception as e:
        app.logger.error(f'Error processing image: {e}')
        return jsonify({'error': 'Failed to process image'}), 500

@app.route('/process_video', methods=['POST'])
def process_video():
    if 'test_video' not in request.files:
        return jsonify({'error': 'No video part in the request'}), 400

    test_video = request.files['test_video']
    if test_video.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    test_video_path = os.path.join(app.config['TEST_FOLDER'], 'test_video.mp4')
    train_photo_path = os.path.join(app.config['TRAIN_FOLDER'], 'train_photo.png')
    output_video_path = os.path.join(app.config['OUTPUT_FOLDER'], 'result_video.mp4')
    audio_path = os.path.join(app.config['OUTPUT_FOLDER'], 'extracted_audio.mp3')
    app.logger.info(f'Saving test video to {test_video_path}')
    try:
        test_video.save(test_video_path)
        app.logger.info('Test video successfully saved')

        # video 모듈을 사용하여 비디오 처리
        imgTrain = video.input1(train_photo_path)
        cap = video.input2(test_video_path)

        # 비디오에서 오디오 추출
        video_clip = VideoFileClip(test_video_path)
        video_clip.audio.write_audiofile(audio_path)
        video_clip.close()

        # video.py의 process_video를 백그라운드에서 실행
        socketio.start_background_task(target=video.process_video, cap=cap, imgTrain=imgTrain,
                                       result_video_path=output_video_path, audio_path=audio_path, socketio=socketio,
                                       app=app)

        result_video_url = url_for('get_result_video_with_audio', _external=True)

        return jsonify({'message': 'Video processing started', 'result_video_url': result_video_url,
                        'redirect_url': url_for('gallery_convert')}), 200
    except Exception as e:
        app.logger.error(f'Error processing video: {e}')
        return jsonify({'error': 'Failed to process video'}), 500


@app.route('/process_webcam_video', methods=['POST'])
def process_webcam_video():
    if 'test_video' not in request.files:
        return jsonify({'error': 'No video part in the request'}), 400

    test_video = request.files['test_video']
    if test_video.filename == '':
        return jsonify({'error': 'No selected file'}), 400

    test_video_path = os.path.join(app.config['TEST_FOLDER'], 'test_webcam_video.webm')
    train_photo_path = os.path.join(app.config['TRAIN_FOLDER'], 'train_photo.png')
    output_video_path = os.path.join(app.config['OUTPUT_FOLDER'], 'result_webcam_video.mp4')
    audio_path = os.path.join(app.config['OUTPUT_FOLDER'], 'extracted_audio.mp3')
    app.logger.info(f'Saving test webcam video to {test_video_path}')
    try:
        test_video.save(test_video_path)
        app.logger.info('Test webcam video successfully saved')

        # ffmpeg를 사용하여 webm을 mp4로 변환
        os.system(f"ffmpeg -y -i {test_video_path} {test_video_path.replace('.webm', '.mp4')}")

        # video 모듈을 사용하여 비디오 처리
        imgTrain = video.input1(train_photo_path)
        cap = video.input2(test_video_path.replace('.webm', '.mp4'))

        # 비디오에서 오디오 추출
        video_clip = VideoFileClip(test_video_path.replace('.webm', '.mp4'))
        video_clip.audio.write_audiofile(audio_path)
        video_clip.close()

        # video.py의 process_video를 백그라운드에서 실행
        socketio.start_background_task(target=video.process_video, cap=cap, imgTrain=imgTrain,
                                       result_video_path=output_video_path, audio_path=audio_path, socketio=socketio,
                                       app=app)

        return jsonify({'message': 'Webcam video processing started'}), 200
    except Exception as e:
        app.logger.error(f'Error processing webcam video: {e}')
        return jsonify({'error': 'Failed to process webcam video'}), 500

@socketio.on('progress')
def handle_progress(data):
    progress = data.get('progress', 0)
    app.logger.info(f'Progress: {progress}%')
    socketio.emit('progress', {'progress': progress})
    if progress == 100:
        app.logger.info('Complete event emitted.')
        socketio.emit('complete', {'url': url_for('camera_convert')})

@socketio.on('connect')
def test_connect():
    app.logger.info('Client connected')

@socketio.on('disconnect')
def test_disconnect():
    app.logger.info('Client disconnected')

@app.route('/result_image')
def get_result_image():
    return send_from_directory(app.config['OUTPUT_FOLDER'], 'result_image.jpg')

@app.route('/result_video_with_audio')
def get_result_video_with_audio():
    return send_from_directory(app.config['OUTPUT_FOLDER'], 'result_video_with_audio.mp4')

@app.route('/result_webcam_video_with_audio')
def get_result_webcam_video_with_audio():
    return send_from_directory(app.config['OUTPUT_FOLDER'], 'result_webcam_video_with_audio.mp4')

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5006, allow_unsafe_werkzeug=True)
