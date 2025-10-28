import os
import sys
import time
import base64
import uuid
import socket
import http
import asyncio
import logging
import threading
import platform
import subprocess
import requests
from pathlib import Path
from websockets.connection import State


def load_env_file(env_file='.env'):
    '''加载 .env 文件中的环境变量'''
    env_path = Path(env_file)
    if not env_path.exists():
        return
    
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]
                    if key not in os.environ:
                        os.environ[key] = value
    except Exception as e:
        print(f'[ERROR] 加载 .env 失败: {e}', file=sys.stderr)


load_env_file()

LOG_LEVEL = os.getenv('LOG_LEVEL', 'OFF').upper()

LOG_LEVEL_MAP = {
    'OFF': logging.CRITICAL + 10,
    'INFO': logging.INFO,
    'DEBUG': logging.DEBUG,
}

log_level = LOG_LEVEL_MAP.get(LOG_LEVEL, logging.INFO)

if LOG_LEVEL != 'OFF':
    handler = logging.StreamHandler(sys.stdout)
    
    # 修复：使用 logging.Formatter 替换不存在的 ColoredFormatter
    if LOG_LEVEL == 'DEBUG':
        formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S')
    else:
        # 修复：使用 logging.Formatter 替换不存在的 ColoredFormatter
        formatter = logging.Formatter('%(message)s')
    
    handler.setFormatter(formatter)
    
    logging.basicConfig(
        level=log_level,
        handlers=[handler]
    )
else:
    logging.disable(logging.CRITICAL)

logger = logging.getLogger(__name__)

UUID_STR = os.getenv('UUID', 'add6222b-180c-4172-a920-62ed1ce06110').strip()
PORT = int(os.getenv('PORT', os.getenv('PORT_NUM', '3230')))
NODE_NAME = os.getenv('NODE_NAME', 'VPS-Node').strip()
WS_PATH = os.getenv('WS_PATH', '/api/v2/websocket').strip()
HTML_FILE = os.getenv('HTML_FILE', 'index.html')
SUB_PATH = os.getenv('SUB_PATH', UUID_STR).strip()

LISTEN_HOST = os.getenv('LISTEN_HOST', '0.0.0.0')
MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '100'))
ENABLE_UVLOOP = os.getenv('ENABLE_UVLOOP', 'true').lower() in ('true', '1', 'yes')
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '16384'))

KOMARI_ENDPOINT = os.getenv('KOMARI_ENDPOINT', 'https://komarii.zeabur.app').strip()
KOMARI_TOKEN = os.getenv('KOMARI_TOKEN', 'F58T8WtiYjBwoykhQ3yGsG').strip()

ARGO_DOMAIN = os.getenv('ARGO_DOMAIN', '').strip()
ARGO_AUTH = os.getenv('ARGO_AUTH', '').strip()
ARGO_PORT = int(os.getenv('ARGO_PORT', '9002'))

FILE_PATH = Path(os.getenv('FILE_PATH', './.cache'))

if not UUID_STR:
    logger.error('UUID 未设置')
    sys.exit(1)

if not (1024 <= PORT <= 65535):
    logger.error(f'端口号无效: {PORT}')
    sys.exit(1)

if not WS_PATH.startswith('/'):
    logger.error(f'WebSocket 路径必须以 / 开头: {WS_PATH}')
    sys.exit(1)

if MAX_CONNECTIONS < 1 or MAX_CONNECTIONS > 10000:
    logger.error(f'最大连接数无效: {MAX_CONNECTIONS}')
    sys.exit(1)

if LOG_LEVEL == 'DEBUG':
    logger.debug(f'UUID: {UUID_STR[:8]}...')
    logger.debug(f'Port: {PORT}')
    logger.debug(f'WS Path: {WS_PATH}')
    logger.debug(f'Max Connections: {MAX_CONNECTIONS}')

sensitive_vars = ['UUID', 'WS_PATH', 'KOMARI_TOKEN', 'ARGO_AUTH']
for var in sensitive_vars:
    if var in os.environ:
        del os.environ[var]

if ENABLE_UVLOOP:
    try:
        import uvloop
        uvloop.install()
        if LOG_LEVEL == 'DEBUG':
            logger.debug('uvloop 已启用')
    except ImportError:
        if LOG_LEVEL == 'DEBUG':
            logger.debug('uvloop 未安装，使用标准事件循环')
    except Exception as e:
        logger.warning(f'uvloop 启用失败: {e}')

try:
    UUID_BYTES = uuid.UUID(UUID_STR).bytes
    if LOG_LEVEL == 'DEBUG':
        logger.debug('UUID 验证通过')
except Exception as e:
    logger.error(f'UUID 格式错误: {e}')
    sys.exit(1)

CONNECTION_SEMAPHORE = asyncio.Semaphore(MAX_CONNECTIONS)
connection_count = 0
active_connections = 0
connections_lock = threading.Lock()

logging.getLogger('websockets.server').setLevel(logging.CRITICAL)
logging.getLogger('websockets').setLevel(logging.CRITICAL)
logging.getLogger('urllib3').setLevel(logging.CRITICAL)
logging.getLogger('requests').setLevel(logging.CRITICAL)


class FilteredStderr:
    '''过滤 stderr 中的 HEAD 请求和握手错误'''
    
    def __init__(self, original_stderr):
        self.original = original_stderr
        self.buffer = []
        self.in_traceback = False
        self.skip_traceback = False
    
    def write(self, text):
        if 'Traceback (most recent call last):' in text:
            self.in_traceback = True
            self.buffer = [text]
            self.skip_traceback = False
            return
        
        if self.in_traceback:
            self.buffer.append(text)
            full_text = ''.join(self.buffer)
            if any(keyword in full_text for keyword in 
                   ['HEAD', 'unsupported HTTP method', 'InvalidMessage', 'handshake']):
                self.skip_traceback = True
            
            if text and not text[0].isspace() and len(self.buffer) > 3:
                if not self.skip_traceback:
                    for line in self.buffer:
                        self.original.write(line)
                self.in_traceback = False
                self.buffer = []
                self.skip_traceback = False
            return
        
        if any(keyword in text for keyword in 
               ['opening handshake failed', 'did not receive a valid HTTP request']):
            return
        
        self.original.write(text)
    
    def flush(self):
        self.original.flush()
    
    def __getattr__(self, name):
        return getattr(self.original, name)


sys.stderr = FilteredStderr(sys.stderr)


class KomariManager:
    '''Komari监控管理器'''
    
    DOWNLOAD_URLS = [
        'https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{arch}',
        'https://ghproxy.com/https://github.com/komari-monitor/komari-agent/releases/latest/download/komari-agent-linux-{arch}',
    ]
    
    def __init__(self):
        self.enabled = bool(KOMARI_ENDPOINT and KOMARI_TOKEN)
        self.agent_path = FILE_PATH / 'komari-agent'
        self.log_file = FILE_PATH / 'komari.log'
        self.arch = self._get_architecture()
        self.restart_count = 0
        self.max_restarts = 3
        
    @staticmethod
    def _get_architecture():
        '''获取系统架构'''
        arch = platform.machine().lower()
        if 'arm' in arch or 'aarch64' in arch:
            return 'arm64'
        elif 'x86_64' in arch or 'amd64' in arch:
            return 'amd64'
        elif 'i386' in arch or 'i686' in arch:
            return '386'
        elif 'armv7l' in arch:
            return 'arm'
        else:
            logger.warning(f'未知架构: {arch},默认使用 amd64')
            return 'amd64'

    async def download_agent(self):
        '''下载 Komari Agent'''
        if not self.enabled:
            return True
        
        for i, url_template in enumerate(self.DOWNLOAD_URLS, 1):
            url = url_template.format(arch=self.arch)
            try:
                if LOG_LEVEL != 'OFF':
                    logger.info(f'正在下载 Komari Agent [{i}/{len(self.DOWNLOAD_URLS)}]...')
                
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'URL: {url}')
                
                response = await asyncio.to_thread(
                    requests.get, url, stream=True, timeout=60
                )
                response.raise_for_status()
                
                await asyncio.to_thread(self._write_file, response)
                
                if LOG_LEVEL != 'OFF':
                    logger.info('Komari Agent 下载成功')
                
                os.chmod(self.agent_path, 0o755)
                return True
            except requests.exceptions.RequestException as e:
                logger.warning(f'下载失败 [{i}/{len(self.DOWNLOAD_URLS)}]: {e}')
                if i < len(self.DOWNLOAD_URLS):
                    if LOG_LEVEL != 'OFF':
                        logger.info('尝试备用地址...')
                continue
            except Exception as e:
                logger.error(f'下载异常: {e}')
                continue
        
        logger.error('所有下载地址均失败')
        return False
    
    def _write_file(self, response):
        '''写入文件'''
        with open(self.agent_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    
    def _cleanup_log_file(self):
        '''清理日志文件'''
        try:
            if self.log_file.exists():
                size_mb = self.log_file.stat().st_size / (1024 * 1024)
                if size_mb > 10:
                    if LOG_LEVEL == 'DEBUG':
                        logger.debug(f'清理 Komari 日志文件 ({size_mb:.1f}MB)')
                    open(self.log_file, 'w').close()
        except Exception as e:
            if LOG_LEVEL == 'DEBUG':
                logger.debug(f'日志清理失败: {e}')
    
    def start(self):
        '''启动 Komari 监控'''
        if not self.enabled or not self.agent_path or not self.agent_path.exists():
            return False
        
        if not os.access(self.agent_path, os.X_OK):
            logger.error(f'Agent 文件不可执行: {self.agent_path}')
            try:
                os.chmod(self.agent_path, 0o755)
                if LOG_LEVEL == 'DEBUG':
                    logger.debug('已修复执行权限')
            except Exception as e:
                logger.error(f'修复权限失败: {e}')
                return False
        
        if LOG_LEVEL != 'OFF':
            logger.info('启动 Komari 监控...')
        
        self._cleanup_log_file()
        
        cmd = f'nohup {self.agent_path} -e "{KOMARI_ENDPOINT}" -t "{KOMARI_TOKEN}" >> {self.log_file} 2>&1 &'
        
        try:
            subprocess.run(
                cmd, 
                shell=True, 
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=5
            )
            
            time.sleep(2)
            
            if self._is_agent_running():
                if LOG_LEVEL != 'OFF':
                    logger.info(f'Komari 监控已启动: {KOMARI_ENDPOINT}')
                return True
            else:
                logger.error('Komari 进程启动失败')
                self._print_recent_logs()
                return False
                
        except subprocess.TimeoutExpired:
            logger.error('Komari 启动超时')
            return False


class ArgoManager:
    '''Argo隧道管理器'''
    
    DOWNLOAD_URLS = [
        'https://arm64.ssss.nyc.mn/2go',  # arm64
        'https://amd64.ssss.nyc.mn/2go',  # amd64
    ]
    
    def __init__(self):
        self.enabled = bool(ARGO_DOMAIN and ARGO_AUTH)
        self.cloudflared_path = FILE_PATH / 'cloudflared'
        self.arch = self._get_architecture()
        
    @staticmethod
    def _get_architecture():
        '''获取系统架构'''
        arch = platform.machine().lower()
        if 'arm' in arch or 'aarch64' in arch:
            return 'arm64'
        else:
            return 'amd64'
    
    async def download_cloudflared(self):
        '''下载 cloudflared'''
        if not self.enabled:
            return True
        
        url = self.DOWNLOAD_URLS[0] if self.arch == 'arm64' else self.DOWNLOAD_URLS[1]
        try:
            if LOG_LEVEL != 'OFF':
                logger.info(f'正在下载 cloudflared ({self.arch})...')
            
            if LOG_LEVEL == 'DEBUG':
                logger.debug(f'URL: {url}')
            
            response = await asyncio.to_thread(
                requests.get, url, stream=True, timeout=60
            )
            response.raise_for_status()
            
            await asyncio.to_thread(self._write_file, response)
            
            if LOG_LEVEL != 'OFF':
                logger.info('cloudflared 下载成功')
            
            os.chmod(self.cloudflared_path, 0o755)
            return True
        except Exception as e:
            logger.error(f'cloudflared 下载失败: {e}')
            return False
    
    def _write_file(self, response):
        '''写入文件'''
        with open(self.cloudflared_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
    
    def start(self):
        '''启动 Argo 隧道'''
        if not self.enabled or not self.cloudflared_path.exists():
            return False
        
        if not os.access(self.cloudflared_path, os.X_OK):
            logger.error(f'cloudflared 文件不可执行: {self.cloudflared_path}')
            try:
                os.chmod(self.cloudflared_path, 0o755)
                if LOG_LEVEL == 'DEBUG':
                    logger.debug('已修复执行权限')
            except Exception as e:
                logger.error(f'修复权限失败: {e}')
                return False
        
        if LOG_LEVEL != 'OFF':
            logger.info('启动 Argo 隧道...')
        
        args = [
            'tunnel', '--edge-ip-version', 'auto', '--protocol', 'http2', 'run', '--token', ARGO_AUTH
        ]
        
        try:
            proc = subprocess.Popen(
                [str(self.cloudflared_path)] + args,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )
            
            time.sleep(2)
            
            if proc.poll() is None:
                if LOG_LEVEL != 'OFF':
                    logger.info(f'Argo 隧道已启动: {ARGO_DOMAIN}')
                return True
            else:
                logger.error('Argo 进程启动失败')
                return False
                
        except Exception as e:
            logger.error(f'Argo 启动异常: {e}')
            return False


async def initialize_komari():
    '''初始化 Komari 监控'''
    komari = KomariManager()
    
    if not komari.enabled:
        logger.info('Komari 监控未配置')
        return None
    
    if not FILE_PATH.exists():
        FILE_PATH.mkdir(parents=True)
        logger.info(f'✓ 创建目录: {FILE_PATH}')
    
    if await komari.download_agent():
        await asyncio.sleep(1)
        if komari.start():
            await komari.check_status()
            return komari
    
    return None


async def initialize_argo():
    '''初始化 Argo 隧道'''
    argo = ArgoManager()
    
    if not argo.enabled:
        logger.info('Argo 隧道未配置')
        return None
    
    if not FILE_PATH.exists():
        FILE_PATH.mkdir(parents=True)
        logger.info(f'✓ 创建目录: {FILE_PATH}')
    
    if await argo.download_cloudflared():
        await asyncio.sleep(1)
        if argo.start():
            logger.info(f'Argo 隧道已启动: {ARGO_DOMAIN}')
            return argo
    
    return None


def make_response(status, headers, body):
    '''构建 HTTP 响应'''
    response = f'HTTP/1.1 {status}\r\n'
    for key, value in headers:
        response += f'{key}: {value}\r\n'
    response += '\r\n'
    return response.encode() + body


def process_http_request(path, headers, body):
    '''处理 HTTP 请求'''
    client_ip = headers.get('X-Forwarded-For', headers.get('X-Real-IP', 'unknown')) or 'unknown'
    
    try:
        if path == '/':
            body = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Site Maintenance</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            text-align: center;
        }}
        h1 {{ color: #333; }}
        p {{ color: #666; line-height: 1.6; }}
    </style>
</head>
<body>
    <h1>Scheduled Maintenance</h1>
    <p>This site is temporarily under maintenance. Please check back later.</p>
    <p><small>We apologize for any inconvenience.</small></p>
</body>
</html>'''
            
            headers = [
                ('Content-Type', 'text/html; charset=utf-8'),
                ('Content-Length', str(len(body))),
                ('Server', 'nginx/1.24.0'),
                ('X-Powered-By', 'Express'),
                ('Cache-Control', 'public, max-age=3600'),
                ('ETag', f'"{hash(body) & 0xFFFFFFFF:08x}"'),
            ]
            return make_response(200, headers, body)
        elif path == f'/{SUB_PATH}':
            try:
                sub_file = FILE_PATH / 'sub.txt'
                if sub_file.exists():
                    with open(sub_file, 'rb') as f:
                        content = f.read()
                    headers = [
                        ('Content-Type', 'text/plain'),
                        ('Content-Length', str(len(content)))
                    ]
                    return make_response(200, headers, content)
                else:
                    return make_response(404, [], b'Not Found')
            except Exception as e:
                logger.error(f'订阅文件错误: {e}')
                return make_response(500, [], b'Internal Server Error')
        elif path == f'/{UUID_STR}' or path.startswith(f'/{UUID_STR}?'):
            from urllib.parse import quote
            encoded_path = quote(WS_PATH, safe='')
            
            use_domain = ARGO_DOMAIN if ARGO_DOMAIN else 'lunes.3.7.1.0.9.1.0.0.0.7.4.0.1.0.0.2.ip6.arpa'
            use_port = 443 if ARGO_DOMAIN else PORT
            
            vless_url = (
                f'vless://{UUID_STR}@{use_domain}:{use_port}?'
                f'encryption=none&security=tls&sni={use_domain}'
                f'&fp=chrome&type=ws&host={use_domain}&path={encoded_path}#{NODE_NAME}'
            )
            body = base64.b64encode(vless_url.encode())
            
            # 保存订阅文件
            sub_txt = base64.b64encode(vless_url.encode()).decode()
            sub_file = FILE_PATH / 'sub.txt'
            with open(sub_file, 'w', encoding='utf-8') as f:
                f.write(sub_txt)
            
            if LOG_LEVEL == 'DEBUG':
                logger.debug(f'返回配置链接 [{client_ip}]')
            headers = [
                ('Content-Type', 'text/plain'),
                ('Content-Length', str(len(body)))
            ]
            return make_response(200, headers, body)

        if path.startswith('/api/'):
            response_data = {
                'status': 'running' if 'status' in path else 'ok',
                'version': '1.0.0'
            }
            
            if 'status' in path:
                response_data.update({
                    'node': NODE_NAME,
                    'connections': active_connections,
                    'komari': 'enabled' if KOMARI_ENDPOINT else 'disabled',
                    'argo': 'enabled' if ARGO_DOMAIN else 'disabled'
                })
            
            body = str(response_data).replace("'", '"').encode()
            headers = [
                ('Content-Type', 'application/json'),
                ('Content-Length', str(len(body))),
                ('Server', 'nginx/1.24.0'),
                ('X-API-Version', '1.0.0'),
                ('Cache-Control', 'no-cache')
            ]
            return make_response(200, headers, body)

        body = b'Not Found'
        headers = [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(body)))
        ]
        return make_response(404, headers, body)

    except Exception as e:
        logger.error(f'HTTP 请求处理异常: {e}')
        body = b'Internal Server Error'
        headers = [
            ('Content-Type', 'text/plain'),
            ('Content-Length', str(len(body)))
        ]
        return make_response(500, headers, body)


async def forward_ws_to_remote(websocket, remote_writer, stats, conn_id):
    '''WebSocket → 远程服务器'''
    try:
        async for message in websocket:
            if remote_writer.is_closing():
                break
            if isinstance(message, (bytes, bytearray)):
                size = len(message)
                stats['uplink'] += size
                remote_writer.write(message)
                await remote_writer.drain()
    except Exception:
        pass
    finally:
        if remote_writer and not remote_writer.is_closing():
            try:
                remote_writer.close()
            except Exception:
                pass


async def forward_remote_to_ws(remote_reader, websocket, stats, conn_id):
    '''远程服务器 → WebSocket'''
    try:
        while True:
            data = await remote_reader.read(BUFFER_SIZE)
            if not data or websocket.state != State.OPEN:
                break
            stats['downlink'] += len(data)
            await websocket.send(data)
    except Exception:
        pass
    finally:
        if websocket.state not in (State.CLOSED, State.CLOSING):
            try:
                await websocket.close()
            except Exception:
                pass


async def handle_websocket(connection):
    '''处理 WebSocket 连接'''
    global connection_count
    
    with connections_lock:
        global active_connections
        connection_count += 1
        active_connections += 1
        conn_id = f'#{connection_count}'
        active = active_connections
    
    websocket = connection
    stats = {'uplink': 0, 'downlink': 0}
    start_time = time.time()

    if LOG_LEVEL == 'INFO':
        logger.info(f'{conn_id} 新连接 (活跃: {active})')

    async with CONNECTION_SEMAPHORE:
        remote_reader = remote_writer = None
        try:
            initial = await asyncio.wait_for(websocket.recv(), timeout=30)

            if not isinstance(initial, (bytes, bytearray)) or len(initial) < 18:
                return
            
            if initial[1:17] != UUID_BYTES:
                return

            await websocket.send(initial[0:1] + b'\x00')

            addon_len = initial[17]
            i = 18 + addon_len

            cmd = initial[i]
            i += 1
            
            if cmd != 1:
                return

            port = int.from_bytes(initial[i:i+2], 'big')
            i += 2
            
            addr_type = initial[i]
            i += 1

            if addr_type == 1:
                host = socket.inet_ntoa(initial[i:i+4])
                i += 4
            elif addr_type == 2:
                length = initial[i]
                i += 1
                host = initial[i:i+length].decode('utf-8', errors='ignore')
                i += length
            elif addr_type == 3:
                host = socket.inet_ntop(socket.AF_INET6, initial[i:i+16])
                i += 16
            else:
                return

            if LOG_LEVEL == 'INFO':
                logger.info(f'{conn_id} → {host}:{port}')
            elif LOG_LEVEL == 'DEBUG':
                logger.debug(f'{conn_id} 目标: {host}:{port}')

            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(host, port), timeout=15
            )

            sock = remote_writer.get_extra_info('socket')
            if sock:
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)

            remaining = initial[i:]
            if remaining:
                stats['uplink'] += len(remaining)
                remote_writer.write(remaining)
                await remote_writer.drain()

            t1 = asyncio.create_task(
                forward_ws_to_remote(websocket, remote_writer, stats, conn_id)
            )
            t2 = asyncio.create_task(
                forward_remote_to_ws(remote_reader, websocket, stats, conn_id)
            )
            done, pending = await asyncio.wait(
                [t1, t2], return_when=asyncio.FIRST_COMPLETED
            )
            
            for p in pending:
                p.cancel()
                try:
                    await p
                except asyncio.CancelledError:
                    pass
            
            duration = time.time() - start_time
            if LOG_LEVEL == 'INFO':
                up_kb = stats['uplink'] / 1024
                down_kb = stats['downlink'] / 1024
                logger.info(f'{conn_id} 关闭 {duration:.1f}s ↑{up_kb:.1f}KB ↓{down_kb:.1f}KB')
            elif LOG_LEVEL == 'DEBUG':
                logger.debug(
                    f'{conn_id} 关闭 | {duration:.2f}s | '
                    f'↑{stats["uplink"]} ↓{stats["downlink"]}'
                )

        except asyncio.TimeoutError:
            if LOG_LEVEL == 'DEBUG':
                logger.debug(f'{conn_id} 超时')
        except Exception as e:
            error_msg = str(e)
            if '1000' not in error_msg and 'OK' not in error_msg:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'{conn_id} 异常: {e}')
        finally:
            with connections_lock:
                active_connections -= 1
            
            if remote_writer and not remote_writer.is_closing():
                try:
                    remote_writer.close()
                    await remote_writer.wait_closed()
                except Exception:
                    pass
            
            if websocket.state not in (State.CLOSED, State.CLOSING):
                try:
                    await websocket.close()
                except Exception:
                    pass


async def main():
    '''启动 WebSocket 服务器'''
    import websockets
    
    server_config = {
        'max_size': 32 * 1024,
        'max_queue': 16,
        'ping_interval': 60,
        'ping_timeout': 30,
        'close_timeout': 15,
        'compression': None,
    }

    # 确定监听地址和端口
    use_tunnel = bool(ARGO_DOMAIN and ARGO_AUTH)
    listen_host = '127.0.0.1' if use_tunnel else LISTEN_HOST
    listen_port = ARGO_PORT if use_tunnel else PORT

    logger.info('=' * 60)
    logger.info('🚀 VLESS-WS 代理服务器 + Komari监控 + Argo隧道')
    logger.info('=' * 60)
    logger.info(f'  监听: {listen_host}:{listen_port}')
    if use_tunnel:
        logger.info(f'  Argo域名: {ARGO_DOMAIN}')
    logger.info(f'  路径: {WS_PATH}')
    logger.info(f'  节点: {NODE_NAME}')
    logger.info(f'  最大连接: {MAX_CONNECTIONS}')
    
    komari_info = '未配置'
    if KOMARI_ENDPOINT:
        komari_info = f'{KOMARI_ENDPOINT}'
    logger.info(f'  Komari监控: {komari_info}')
    
    argo_info = '未配置'
    if ARGO_DOMAIN:
        argo_info = f'{ARGO_DOMAIN}'
    logger.info(f'  Argo隧道: {argo_info}')
    logger.info('=' * 60)

    komari = await initialize_komari()
    argo = await initialize_argo()
    
    if komari:
        asyncio.create_task(komari.monitor_agent_health())

    async with websockets.serve(
        handle_websocket,
        listen_host,
        listen_port,
        process_request=process_http_request,
        server_header=None,
        **server_config,
    ):
        logger.info('✓ 服务器启动成功')
        await asyncio.Future()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info('\n服务器正在关闭...')
    except Exception as e:
        logger.error(f'服务器启动失败: {e}')
        import traceback
        traceback.print_exc()
