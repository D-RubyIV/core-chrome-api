import datetime
import json
import os
import random
import socket
import string
import subprocess
import threading
import time
import uuid
from pathlib import Path

from flask import Flask, request
from flask_restful import Resource, Api

from proxyAuth import get_extension_folder

# Constants
ROOT_PATH = os.getcwd()
CHROME_PATH = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
CORE_PROFILE_DATA = os.path.join(ROOT_PATH, 'data', 'user', 'profiles')


def generate_random_profile_path_name():
    random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=10))
    date_part = datetime.datetime.now().strftime("%d%m%Y")  # ddMMyyyy
    return f"{random_part}-{date_part}"


def get_chrome_user_data_dir(user_id: str) -> Path:
    base = Path.cwd()
    return base / "data/user/profiles" / user_id


def get_chrome_version(state_path: str = None):
    with open(state_path, encoding='utf-8') as f:
        data = json.load(f)
        print(data)
        version = data["user_experience_metrics"]["stability"]["stats_version"]
        print("Version:", version)
        return version


class PortFinder:
    @staticmethod
    def is_port_available(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(('127.0.0.1', port))
                return True
            except socket.error:
                return False

    @staticmethod
    def get_free_ports(count=10):
        ports = []

        for _ in range(count):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                s.bind(('127.0.0.1', 0))
                port = s.getsockname()[1]
                s.close()  # Close immediately after getting port

                # Double check if port is really available
                if PortFinder.is_port_available(port):
                    ports.append(port)
                else:
                    # Try to find another port
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.bind(('127.0.0.1', 0))
                    port = s.getsockname()[1]
                    s.close()
                    ports.append(port)

            except Exception as e:
                s.close()
                raise e

        return ports

    @staticmethod
    def get_one_free_port():
        return PortFinder.get_free_ports(1)[0]


class TodoHandler(Resource):
    def __init__(self):
        self.chrome_path = CHROME_PATH
        self.core_profile_data = CORE_PROFILE_DATA

    def get(self, profile_id=None):
        if profile_id:
            return self.open_profile(profile_id)
        return self.list_profiles()

    def post(self):
        def auto_kill(process_running, delay=5):
            time.sleep(delay)
            process_running.terminate()
            print(f"Đã tự động đóng Chrome sau {delay} giây.")

        try:
            port = PortFinder.get_one_free_port()
            profile_name = str(uuid.uuid4())
            user_data_dir = os.path.join(CORE_PROFILE_DATA, f'{profile_name}')
            os.makedirs(user_data_dir, exist_ok=True)
            print(f"user_data_dir: {user_data_dir}")
            profile_dir = os.path.join(user_data_dir, profile_name)
            print(f"profile_dir: {profile_dir}")
            config_profile_path = os.path.join(user_data_dir, "config.json")

            cmd = [
                self.chrome_path,
                f'--remote-debugging-port={port}',
                '--lang=vi',
                '--mute-audio',
                '--no-first-run',
                '--no-default-browser-check',
                '--window-size=400,880',
                '--window-position=0,0',
                '--force-device-scale-factor=0.6',
                f'--user-data-dir={user_data_dir}',
                f'--profile-directory=Default',
                '--restore-last-session=false',
                'https://www.facebook.com/'
            ]
            print(" ".join(cmd))

            process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)

            threading.Thread(target=auto_kill, args=(process, 5), daemon=True).start()

            with open(config_profile_path, mode="w+", encoding="utf-8") as f:
                f.write(json.dumps({
                    "raw_proxy": "",
                    "raw_note": "",
                    "created_at": datetime.datetime.now().isoformat()
                }, ensure_ascii=False, indent=4))

            return {
                "success": True,
                "data": {
                    "name": profile_name,
                    "id": profile_name,
                    "port": port
                },
                "message": "Chrome started successfully"
            }

        except Exception as e:
            return {"success": False, "message": f"Lỗi khi khởi chạy Chrome: {str(e)}"}

    def put(self, profile_id):
        try:
            profile_path = os.path.join(self.core_profile_data, profile_id)
            config_profile_path = os.path.join(profile_path, "config.json")

            if not os.path.exists(profile_path):
                return {"success": False, "message": "Profile không tồn tại"}

            # Get the request data
            data = request.get_json()
            raw_proxy = data.get("raw_proxy", "")
            raw_note = data.get("raw_note", "")

            # Read existing config
            with open(config_profile_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

            # Update config
            config_data["raw_proxy"] = raw_proxy
            config_data["raw_note"] = raw_note

            # Write back to file
            with open(config_profile_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, ensure_ascii=False, indent=4)

            return {
                "success": True,
                "message": "Cập nhật profile thành công",
                "data": {
                    "id": profile_id,
                    "raw_proxy": raw_proxy,
                    "raw_note": raw_note
                }
            }

        except Exception as e:
            return {"success": False, "message": f"Lỗi khi cập nhật profile: {str(e)}"}

    def open_profile(self, profile_id):
        try:
            profile_path = os.path.join(self.core_profile_data, profile_id)
            config_profile_path = os.path.join(profile_path, "config.json")
            proxy_extension_dir = os.path.join(profile_path, "extension")
            if not os.path.exists(profile_path):
                return {"success": False, "message": "Profile không tồn tại"}

            port = PortFinder.get_one_free_port()
            user_data_dir = os.path.join(self.core_profile_data, profile_id)

            with open(config_profile_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)

                # Update config
            raw_proxy = config_data["raw_proxy"]
            folder = ""
            if raw_proxy != "":
                folder = get_extension_folder(
                    name=profile_id,
                    proxy=raw_proxy,
                    extension_dir=proxy_extension_dir
                )

            cmd = [
                self.chrome_path,
                f'--remote-debugging-port={port}',
                f"--load-extension={folder}",
                '--lang=vi',
                '--mute-audio',
                '--no-first-run',
                '--no-default-browser-check',
                '--window-size=400,880',
                '--window-position=0,0',
                '--force-device-scale-factor=0.6',
                f'--user-data-dir={user_data_dir}',
                f'--profile-directory=Default',
                '--restore-last-session=true',
            ]

            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=False)

            return {
                "success": True,
                "data": {
                    "id": profile_id,
                    "port": port
                },
                "message": "Chrome started successfully"
            }

        except Exception as e:
            return {"success": False, "message": f"Lỗi khi mở profile: {str(e)}"}

    def list_profiles(self):
        result = []
        raw_proxy = ""
        raw_note = ""
        created_at = ""
        try:
            profiles = os.listdir(self.core_profile_data)
            for p in profiles:
                profile_path = os.path.join(self.core_profile_data, p)
                config_profile_path = os.path.join(profile_path, "config.json")
                state_profile_path = os.path.join(profile_path, "Local State")
                print(config_profile_path)
                with open(config_profile_path, 'r', encoding='utf-8') as f:
                    profile_config_data = json.loads(f.read())
                    print(profile_config_data)
                    raw_proxy = profile_config_data["raw_proxy"]
                    raw_note = profile_config_data["raw_note"]
                    created_at = profile_config_data["created_at"]

                if os.path.isdir(os.path.join(self.core_profile_data, p)):
                    result.append({
                        "name": p,
                        "id": p,
                        "profile_path": str(get_chrome_user_data_dir(user_id=p)),
                        "browser_version": str(get_chrome_version(state_profile_path)),
                        "raw_proxy": raw_proxy,
                        "created_at": created_at,
                        "raw_note": raw_note,
                    })
            return {"success": True, "data": result, "message": "OK"}
        except Exception as e:
            return {"success": False, "message": f"Lỗi khi lấy danh sách profiles: {str(e)}"}

    @staticmethod
    def auto_kill(process_running, delay=5):
        time.sleep(delay)
        process_running.terminate()
        print(f"Đã tự động đóng Chrome sau {delay} giây.")


app = Flask(__name__)
api = Api(app)
api.add_resource(TodoHandler, '/api/v1/profiles', '/api/v1/profiles/<string:profile_id>')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
