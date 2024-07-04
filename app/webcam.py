# webcam.py
import numpy as np
import cv2
import face_recognition
from moviepy.editor import VideoFileClip, AudioFileClip
from flask import current_app, url_for


def input_image(img_path):
    img = face_recognition.load_image_file(img_path)
    img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return img


def blur_face(image, face):
    (startY, endX, endY, startX) = face
    face_img = image[startY:endY, startX:endX]
    blurred_face = cv2.GaussianBlur(face_img, (99, 99), 30)
    image[startY:endY, startX:endX] = blurred_face
    return image


def webcam_face_blur(exclusion_img, save_video_path, audio_path, output_video_path, socketio, app):
    cap = cv2.VideoCapture(save_video_path)
    if not cap.isOpened():
        raise Exception("Unable to open video file")

    imgTrain = exclusion_img
    faceLoc = face_recognition.face_locations(imgTrain)[0]
    encodeimg = face_recognition.face_encodings(imgTrain)[0]

    w = round(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = round(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(output_video_path, fourcc, fps, (w, h))

    frame_num = 0
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        rgbframe = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        faces = face_recognition.face_encodings(rgbframe)

        results = []
        for face in faces:
            dic = face_recognition.face_distance([encodeimg], face)
            results.append(dic < 0.4)

        face_locations = face_recognition.face_locations(frame)
        for index, result in enumerate(results):
            if index < len(face_locations):
                index_face_location = face_locations[index]
                if not result:
                    blur_face(frame, index_face_location)

        writer.write(frame)
        frame_num += 1
        progress = int((frame_num / total_frames) * 100)
        socketio.emit('progress', {'progress': progress})

        if frame_num >= total_frames:
            break

    writer.release()
    cap.release()

    combine_audio_video(output_video_path, audio_path, socketio, app)
    socketio.emit('progress', {'progress': 100})  # 작업 완료 신호 보내기


def combine_audio_video(video_path, audio_path, socketio, app):
    video_clip = VideoFileClip(video_path)
    audio_clip = AudioFileClip(audio_path)
    final_clip = video_clip.set_audio(audio_clip)
    final_clip.write_videofile(video_path.replace('.mp4', '_with_audio.mp4'), codec='libx264', audio_codec='aac')
    video_clip.close()
    audio_clip.close()

    with app.app_context():
        socketio.emit('complete', {'url': url_for('camera_convert')})
