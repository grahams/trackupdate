"""Unix-socket front end for the engine: NDJSON commands in, snapshots out.

Handler threads never touch the engine's db or plugins. They only
`engine.submit` decoded commands and forward the snapshots their subscribed
writer receives. Each client has its own bounded outbound queue drained by a
sender thread, so a slow, stalled or dead client can never block the engine.
"""
import logging
import os
import queue
import socket
import socketserver
import threading

import runtime

logger = logging.getLogger("engine_server")

MAX_LINE = 1 << 20      # a client sending more than this without a newline is dropped
OUTBOX_SIZE = 16        # snapshots are complete state, so the oldest can be dropped
SEND_TIMEOUT = 10.0     # a client that won't read for this long is dropped
RECV_POLL = 1.0
FLUSH_TIMEOUT = 2.0


class _Client:
    def __init__(self, sock):
        self.sock = sock
        self.outbox = queue.Queue(maxsize=OUTBOX_SIZE)
        self.closed = False
        self._lock = threading.Lock()
        self.sender = threading.Thread(target=self._send_loop, daemon=True,
                                       name="engine-client-sender")

    def offer(self, item):
        """Queue an item without ever blocking; drop the oldest when full."""
        with self._lock:
            while True:
                try:
                    self.outbox.put_nowait(item)
                    return
                except queue.Full:
                    try:
                        self.outbox.get_nowait()
                    except queue.Empty:
                        pass

    def write(self, snapshot):
        """Engine listener: called on the engine thread."""
        if self.closed:
            return
        self.offer(runtime.encode(snapshot))

    def _send_loop(self):
        while True:
            data = self.outbox.get()
            if data is None:
                break
            try:
                self.sock.sendall(data)
            except OSError:
                break
        self.closed = True
        _shutdown(self.sock)

    def close(self, flush_timeout=0.0):
        """Stop the sender, optionally after it drains what is queued."""
        self.closed = True
        self.offer(None)
        self.sender.join(flush_timeout)
        _shutdown(self.sock)


def _shutdown(sock):
    try:
        sock.shutdown(socket.SHUT_RDWR)
    except OSError:
        pass


class _Handler(socketserver.BaseRequestHandler):
    def handle(self):
        server = self.server
        engine = server.engine
        client = _Client(self.request)
        self.request.settimeout(RECV_POLL)
        with server.clients_lock:
            server.clients.add(client)
        client.sender.start()
        engine.subscribe(client.write)
        try:
            engine.submit({"cmd": "hello"})
            self._read_loop(engine, client)
        except Exception:
            logger.exception("client handler failed")
        finally:
            engine.unsubscribe(client.write)
            with server.clients_lock:
                server.clients.discard(client)
            client.close()

    def _read_loop(self, engine, client):
        buf = b""
        while not client.closed:
            try:
                chunk = self.request.recv(65536)
            except TimeoutError:
                continue
            except OSError:
                return
            if not chunk:
                return
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    cmd = runtime.decode(line)
                except ValueError:
                    logger.warning("ignoring undecodable client line: %.80r", line)
                    continue
                engine.submit(cmd)
            if len(buf) > MAX_LINE:
                logger.warning("dropping client: line longer than %d bytes", MAX_LINE)
                return


class _Server(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    block_on_close = False


def serve(engine) -> threading.Thread:
    """Bind the engine socket and serve it on a daemon thread.

    The socket is listening by the time this returns. Stop it with `shutdown`.
    """
    path = runtime.socket_path()
    server = _Server(str(path), _Handler)
    server.engine = engine
    server.clients = set()
    server.clients_lock = threading.Lock()
    server.socket_ino = os.stat(path).st_ino
    thread = threading.Thread(target=server.serve_forever, daemon=True,
                              name="engine-server")
    thread.server = server
    thread.start()
    return thread


def shutdown(thread: threading.Thread) -> None:
    """Stop accepting, give clients a moment to receive the final snapshot,
    close everything and remove the socket file if it is still ours."""
    server = thread.server
    server.shutdown()
    thread.join()
    with server.clients_lock:
        clients = list(server.clients)
    for client in clients:
        client.close(flush_timeout=FLUSH_TIMEOUT)
    server.server_close()
    path = runtime.socket_path()
    try:
        if os.stat(path).st_ino == server.socket_ino:
            path.unlink()
    except FileNotFoundError:
        pass
