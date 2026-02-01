import socket
import v4l2capture
import select

HOST = "0.0.0.0"
PORT = 8000

video = v4l2capture.Video_device("/dev/video0")

video.set_format(640, 640, fourcc='MJPG')
video.set_fps(30)

video.create_buffers(4)
video.queue_all_buffers()
video.start()

sock = socket.socket()
sock.bind((HOST, PORT))
sock.listen(1)

print(f"Streaming at http://{HOST}:{PORT}")
conn, address = sock.accept()
print(f"Connected to: {address}")

conn.sendall(
    b"HTTP/1.0 200 OK\r\n"
    b"Cache-Control: no-cache\r\n"
    b"Pragma: no-cache\r\n"
    b"Content-Type: multipart/x-mixed-replace; boundary=FRAME\r\n\r\n"
)

while True:
    select.select((video,), (), ())

    image_data = video.read_and_queue()

    conn.sendall(b"--FRAME\r\n")
    conn.sendall(b"Content-Type: image/jpeg\r\n")
    conn.sendall(f"Content-Length: {len(image_data)}\r\n\r\n".encode())
    conn.sendall(image_data)
    conn.sendall(b"\r\n")