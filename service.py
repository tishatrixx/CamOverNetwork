import logging
import socketserver
from http import server
from threading import Condition, Thread
import cv2

PAGE = """\
<html>
<body>
<img src="stream.mjpg" width="640" height="480" />
</body>
</html>
"""

class StreamingOutput:
    """Holds the latest MJPEG frame and notifies clients."""
    def __init__(self):
        self.frame = None
        self.condition = Condition()

    def update_frame(self, frame_bytes):
        with self.condition:
            self.frame = frame_bytes
            self.condition.notify_all()


class StreamingHandler(server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(301)
            self.send_header('Location', '/index.html')
            self.end_headers()
        elif self.path == '/index.html':
            content = PAGE.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.send_header('Content-Length', len(content))
            self.end_headers()
            self.wfile.write(content)
        elif self.path == '/stream.mjpg':
            self.send_response(200)
            self.send_header('Age', 0)
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
                    self.send_header('Content-Length', len(frame))
                    self.end_headers()
                    self.wfile.write(frame)
                    self.wfile.write(b'\r\n')
            except Exception as e:
                logging.warning('Removed streaming client %s: %s', self.client_address, str(e))
        else:
            self.send_error(404)
            self.end_headers()


class StreamingServer(socketserver.ThreadingMixIn, server.HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


import time

def capture_frames(camera_index=0, width=640, height=480, fps=30):
    """Capture MJPEG frames and automatically recover if camera is unplugged."""
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

    # Start frame capture in a separate thread
    t = Thread(target=capture_frames, args=(0, 640, 480, 30))
    t.daemon = True
    t.start()

    try:
        address = ('', 8000)
        server = StreamingServer(address, StreamingHandler)
        print("Server started at http://localhost:8000")
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down...")