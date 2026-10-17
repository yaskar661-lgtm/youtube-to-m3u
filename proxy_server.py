import subprocess
import logging
import os
from flask import Flask, request, Response, jsonify
from urllib.parse import unquote

os.environ["PYTHONIOENCODING"] = "utf-8"

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

STREAMLINK_PATH = "streamlink"

COMMON_HEADERS = [
    "--http-header", "User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "--http-header", "Accept-Language=tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7"
]

@app.route("/stream", methods=["GET"])
def stream():
    url = request.args.get("url")
    if not url:
        return jsonify({"error": "URL parameter is required"}), 400

    url = unquote(url)
    client_ip = request.remote_addr
    logging.info(f"[CLIENT CONNECT] {client_ip} → {url}")

    # Engellenen JSON kontrolünü tamamen atlayıp doğrudan tünelleme komutunu kuruyoruz
    command = [
        STREAMLINK_PATH, 
        "--hls-live-restart",
        "--retry-streams", "3",
        "--retry-open", "3"
    ] + COMMON_HEADERS + [url, "best", "--stdout"]

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
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=3)
                except: process.kill()
            if process.stdout: process.stdout.close()
            if process.stderr: process.stderr.close()

    return Response(generate(), content_type="video/mp2t")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, threaded=True)
