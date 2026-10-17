import subprocess
import json
import logging
import os
import time
from flask import Flask, request, Response, jsonify
from urllib.parse import unquote

os.environ["PYTHONIOENCODING"] = "utf-8"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

STREAMLINK_PATH = "streamlink"

# YouTube bot engellemesini aşmak için güncellenmiş argümanlar
COMMON_HEADERS = [
    "--http-header", "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "--http-header", "Accept-Language=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
    "--youtube-backend-client=web"  # Streamlink'e YouTube web istemcisini taklit etmesini söylüyoruz
]

def get_stream_info(url, retries=3):
    for attempt in range(retries):
        logging.info(f"Fetching stream info (attempt {attempt+1})")
        
        # YouTube için ek istemci parametreleri eklenmiş komut
        cmd = [STREAMLINK_PATH, "--json"] + COMMON_HEADERS + [url]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            try:
                return json.loads(stdout.decode("utf-8", errors="replace"))
            except Exception as parse_error:
                logging.error(f"JSON Parse Error: {parse_error}")
        
        # Hatanın ne olduğunu tam görebilmek için logu genişletiyoruz
        err_msg = stderr.decode("utf-8", errors="replace").strip()
        if err_msg:
            logging.warning(f"Streamlink Warning: {err_msg}")
        time.sleep(1.5)
    return None

@app.route("/stream", methods=["GET"])
def stream():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    url = unquote(url)
    client_ip = request.remote_addr
    logging.info(f"[CLIENT CONNECT] {client_ip} → {url}")

    stream_info = get_stream_info(url)
    if not stream_info or "streams" not in stream_info:
        return jsonify({"error": "Failed to retrieve stream info. YouTube might be blocking Render.com IP or channel is offline."}), 500

    if "best" not in stream_info["streams"]:
        return jsonify({"error": "No valid streams found"}), 404

    # Yayını başlatırken de aynı bypass parametrelerini gönderiyoruz
    command = [STREAMLINK_PATH, "--hls-live-restart"] + COMMON_HEADERS + [url, "best", "--stdout"]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=8192)

    def generate():
        try:
            logging.info(f"[STREAM START] {client_ip}")
            while True:
                chunk = process.stdout.read(8192)
                if not chunk:
                    break
                yield chunk
        except GeneratorExit:
            logging.info(f"[CLIENT DISCONNECTED] {client_ip}")
        except Exception as e:
            logging.error(f"[STREAM ERROR] {e}")
        finally:
            cleanup_process(process, client_ip)

    response = Response(generate(), content_type="video/mp2t")
    @response.call_on_close
    def cleanup():
        cleanup_process(process, client_ip)
    return response

def cleanup_process(process, client_ip):
    if process.poll() is None:
        logging.info(f"[CLEANUP] Terminating process for {client_ip}")
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
    if process.stdout: process.stdout.close()
    if process.stderr: process.stderr.close()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
