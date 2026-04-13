bl_info = {
    "name": "STL Import Listener",
    "author": "You",
    "version": (1, 0),
    "blender": (3, 0, 0),
    "location": "View3D > Object > Socket STL Importer",
    "description": "监听 TCP Socket，收到路径后自动导入 STL",
    "category": "Import-Export",
}

import bpy
import socket
import threading
import queue
import os

# 线程安全的消息队列
stl_queue = queue.Queue()
listener_thread = None
is_running = False
HOST, PORT = "127.0.0.1", 65432  # 监听地址与端口


def socket_listener():
    """后台线程：监听 TCP 连接，解析路径并放入队列"""
    global is_running
    is_running = True
    import json

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(1)
        s.settimeout(1.0)  # 超时防止卡死
        print(f"[Socket] 开始监听 {HOST}:{PORT}")
        while is_running:
            try:
                conn, addr = s.accept()
                with conn:
                    raw_msg = conn.recv(2048).decode("utf-8", errors="ignore").strip()
                    if raw_msg:
                        msg = json.loads(raw_msg)
                        filepath = msg["filepath"]
                        stl_queue.put(filepath)
                        print(f"[Socket] 收到路径: {filepath}")
            except socket.timeout:
                continue
            except Exception as e:
                if is_running:
                    print(f"[Socket] 错误: {e}")


def import_stl_timer():
    """主线程定时器：检查队列并导入 STL"""
    while not stl_queue.empty():
        try:
            filepath = stl_queue.get_nowait()
            if os.path.isfile(filepath) and filepath.lower().endswith(".stl"):
                # 兼容 Blender 4.2+ 新 API 与旧版 API
                try:
                    bpy.ops.wm.stl_import(filepath=filepath)
                except AttributeError:
                    bpy.ops.import_mesh.stl(filepath=filepath)
                print(f"[Import] 成功导入: {filepath}")
            else:
                print(f"[Import] 路径无效或非 STL: {filepath}")
        except queue.Empty:
            break
    return 0.5  # 0.5秒后再次执行


def start_listener():
    global listener_thread
    if not is_running:
        listener_thread = threading.Thread(target=socket_listener, daemon=True)
        listener_thread.start()
        bpy.app.timers.register(import_stl_timer)
        print("[Addon] Socket 监听已启动")


def stop_listener():
    global is_running
    is_running = False
    try:
        bpy.app.timers.unregister(import_stl_timer)
    except ValueError:
        pass  # 定时器未注册时忽略
    print("[Addon] Socket 监听已停止")


def register():
    start_listener()


def unregister():
    stop_listener()


if __name__ == "__main__":
    register()
