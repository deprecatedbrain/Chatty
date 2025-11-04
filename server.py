import subprocess
import threading
import time
import requests
import json
import os
import atexit
import signal
from pathlib import Path
from flask import Flask, send_from_directory, request, jsonify

FRONTEND_DIR = "./frontend"
LLAMA_HOST = "127.0.0.1"
LLAMA_PORT = 8080
APP_PORT = 3000

LLAMA_PROC = None

def load_llama_model(llama_bin: str, mmj_path: str):
    global LLAMA_PROC
    data = None
    mmj_path_p = Path(mmj_path)

    # Attempt to load the .mmj file
    try:
        with mmj_path_p.open('r') as file:
            data = json.load(file)
    except FileNotFoundError:
        print(f'{mmj_path} is not a valid .mmj file!')
        return False
    except json.JSONDecodeError:
        print(f'{mmj_path} is an invalid file!')
        return False

    if not data:
        return False

    model_path = data.get('files', {}).get('gguf')

    if not model_path:
        print('Provided .mmj does not have a valid model path!')
        return False

    # Resolve model path relative to the .mmj file location if it's not absolute
    model_path_p = Path(model_path)
    if not model_path_p.is_absolute():
        model_path_p = (mmj_path_p.parent / model_path_p).resolve(strict=False)
    else:
        model_path_p = model_path_p.resolve(strict=False)

    model_path_str = str(model_path_p)
    print("Resolved model path:", model_path_str)

    cmd = [
        f"{llama_bin}/llama-server",
        "-m", model_path_str,
        "--port", str(LLAMA_PORT),
    ]

    print("starting llama-server:", " ".join(cmd))
    # start_new_session=True makes the process a session leader so we can kill its process group
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
    except Exception as e:
        print("Failed to start llama-server:", e)
        return False

    LLAMA_PROC = proc
    return True

def stop_llama_server(timeout: float = 5.0):
    global LLAMA_PROC
    if not LLAMA_PROC:
        return
    try:
        if LLAMA_PROC.poll() is None:
            print("Stopping llama-server...")
            try:
                # kill the process group (works on POSIX)
                os.killpg(LLAMA_PROC.pid, signal.SIGTERM)
            except Exception:
                # fallback to terminate the single process
                try:
                    LLAMA_PROC.terminate()
                except Exception:
                    pass
            # wait for graceful exit
            try:
                LLAMA_PROC.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                print("llama-server did not exit, killing...")
                try:
                    os.killpg(LLAMA_PROC.pid, signal.SIGKILL)
                except Exception:
                    try:
                        LLAMA_PROC.kill()
                    except Exception:
                        pass
                LLAMA_PROC.wait(timeout=1)
    except Exception as e:
        print("Error while stopping llama-server:", e)
    finally:
        LLAMA_PROC = None

def wait_for_llama():
    for _ in range(30):
        try:
            r = requests.get(f'http://{LLAMA_HOST}:{LLAMA_PORT}/v1/models', timeout=2)
            if r.status_code == 200:
                print("llama server ready")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(2)
    print("llama-server not responding")
    return False

app = Flask(__name__, static_folder=FRONTEND_DIR)

def _signal_handler(sig, frame):
    stop_llama_server()
    # restore default and re-raise to allow normal termination if needed
    signal.signal(sig, signal.SIG_DFL)
    os.kill(os.getpid(), sig)

# register cleanup handlers
atexit.register(stop_llama_server)
signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

if __name__ == "__main__":
    llama_bin = "./bin"
    mmj_path = "./models/Qwen3 VL 4B Thinking/model.mmj"
    loader_thread = threading.Thread(target=load_llama_model, args=(llama_bin, mmj_path), daemon=True)
    loader_thread.start()

    # wait for the server to become ready (blocks main thread)
    if wait_for_llama():
        print("Proceeding to start the app...")
        try:
            app.run(host="0.0.0.0", port=APP_PORT)
        finally:
            # ensure we stop the llama process if app.run returns/raises
            stop_llama_server()
    else:
        print("Failed to start llama server.")
        stop_llama_server()