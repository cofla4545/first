import os
import subprocess
import requests
import time


def start_ngrok(port):
    # ngrok 시작
    ngrok = subprocess.Popen(['ngrok', 'http', str(port)])

    # ngrok URL을 가져오기 위해 잠시 대기
    time.sleep(2)

    # ngrok API를 통해 터널 URL 가져오기
    response = requests.get('http://localhost:4040/api/tunnels')
    tunnel_data = response.json()
    public_url = tunnel_data['tunnels'][0]['public_url']

    return public_url


if __name__ == '__main__':
    port = 5005
    public_url = start_ngrok(port)
    print(f'ngrok public URL: {public_url}')

    # Flask 애플리케이션을 ngrok URL로 시작
    os.environ['FLASK_RUN_HOST'] = '0.0.0.0'
    os.environ['FLASK_RUN_PORT'] = str(port)
    os.environ['SERVER_NAME'] = public_url.replace('http://', '').replace('https://', '')

    subprocess.call(['flask', 'run'])
