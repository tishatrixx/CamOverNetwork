import logging
import time
import socketserver
from http import server
from threading import Condition, Thread
import cv2
import argparse

# -----------------------------------------------------------------------------------------------------------------------------
#        This code is licenced under CC-BY 4.0 (https://creativecommons.org/licenses/by/4.0/deed.en WITH attribution.
# -----------------------------------------------------------------------------------------------------------------------------

argument_parser = argparse.ArgumentParser(description="Streaming service")
argument_parser.add_argument("-p", "--port", type=int, default=9842, help="Port used for localhost, defaults to 9842")

class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True

class StreamingOutput:
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def update_frame(self, frame_bytes):
        with self.condition:
            self.frame = frame_bytes
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            self.send_response(301)
            self.send_header("Location", "/stream.mjpg")
            self.end_headers()
        elif self.path == "/stream.mjpg":
            self.send_response(200)
            self.send_header('Age', str(0))
            self.send_header('Cache-Control', 'no-cache, private')
            self.send_header('Pragma', 'no-cache')
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=FRAME')
            self.end_headers()

            try:
                while True:
                    with output.condition:
                        output.condition.wait()
                        frame = output.frame
                    if frame is None:
                        continue
                    self.wfile.write(b'--FRAME\r\n')
                    self.send_header('Content-Type', 'image/jpeg')
                    self.send_header('Content-Length', str(len(frame)))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()

def thread(camera_index=0, width=640, height=480, fps=30):
    cap = None

    while True:
        if cap is None or not cap.isOpened():
            try:
                cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, fps)
                cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
                if not cap.isOpened():
                    raise RuntimeError("Camera not available")
                print("Camera initialized")
            except Exception as e:
                print(f"Failed to open camera: {e}")
                cap = None
                time.sleep(1)
                continue

        ret, frame = cap.read()
        if not ret or frame is None:
            # Camera disconnected or read failed
            print("Camera disconnected or frame read failed, retrying...")
            cap.release()
            cap = None
            time.sleep(1)
            continue

        ret, jpeg = cv2.imencode('.jpg', frame)
        if ret:
            output.update_frame(jpeg.tobytes())



if __name__ == '__main__':
    output = StreamingOutput()
    a = argument_parser.parse_args()

    t = Thread(target=thread, args=(0, 640, 480, 30))
    t.daemon = True
    t.start()

    try:
        address = ('', a.port)
        server = StreamingServer(address, StreamingHandler)
        print(f"Server started at http://localhost:{a.port}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")