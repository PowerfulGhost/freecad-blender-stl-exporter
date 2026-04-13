bl_info = {
    "name": "STL Import Listener",
    "author": "You",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Object > Socket STL Importer",
    "description": "Listen to TCP Socket, automatically import STL after receiving path",
    "category": "Import-Export",
}

import bpy
import socket
import threading
import queue
import os

# Thread-safe message queue
stl_queue = queue.Queue()
listener_thread = None
is_running = False
HOST, PORT = "127.0.0.1", 65432  # Listen address and port


def socket_listener():
    """Background thread: listen to TCP connections, parse path and put into queue"""
    global is_running
    is_running = True
    import json

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        s.settimeout(1.0)  # Timeout to prevent freezing
        print(f"[Socket] Started listening on {HOST}:{PORT}")
        while is_running:
            try:
                conn, addr = s.accept()
                with conn:
                    raw_msg = conn.recv(2048).decode("utf-8", errors="ignore").strip()
                    if raw_msg:
                        msg = json.loads(raw_msg)
                        filepath = msg["filepath"]
                        stl_queue.put(filepath)
                        print(f"[Socket] Received path: {filepath}")
            except socket.timeout:
                continue
            except Exception as e:
                if is_running:
                    print(f"[Socket] Error: {e}")


def import_stl_timer():
    """Main thread timer: check queue and import STL"""
    while not stl_queue.empty():
        try:
            filepath = stl_queue.get_nowait()
            if os.path.isfile(filepath) and filepath.lower().endswith(".stl"):
                obj_name = os.path.splitext(os.path.basename(filepath))[0]
                old_obj = bpy.data.objects.get(obj_name)
                old_transform = (
                    (old_obj.location.copy(), old_obj.rotation_euler.copy())
                    if old_obj
                    else None
                )

                if old_obj:
                    bpy.data.objects.remove(old_obj, do_unlink=True)

                try:
                    bpy.ops.wm.stl_import(filepath=filepath)
                except AttributeError:
                    bpy.ops.import_mesh.stl(filepath=filepath)

                new_obj = bpy.data.objects.get(obj_name)
                if new_obj and old_transform:
                    new_obj.location = old_transform[0]
                    new_obj.rotation_euler = old_transform[1]

                print(f"[Import] Successfully imported: {filepath}")
            else:
                print(f"[Import] Invalid path or not STL: {filepath}")
        except queue.Empty:
            break
    return 0.5  # Run again after 0.5 seconds


def start_listener():
    global listener_thread
    if not is_running:
        listener_thread = threading.Thread(target=socket_listener, daemon=True)
        listener_thread.start()
        bpy.app.timers.register(import_stl_timer)
        print("[Addon] Socket listener started")


def stop_listener():
    global is_running
    is_running = False
    try:
        bpy.app.timers.unregister(import_stl_timer)
    except ValueError:
        pass  # Ignore when timer is not registered
    print("[Addon] Socket listener stopped")


def register():
    start_listener()


def unregister():
    stop_listener()


if __name__ == "__main__":
    register()
