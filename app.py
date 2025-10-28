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
DOMAIN = os.getenv('DOMAIN', 'lunes.3.7.1.0.9.1.0.0.0.7.4.0.1.0.0.2.ip6.arpa').strip()
PORT = int(os.getenv('PORT', os.getenv('PORT_NUM', '3230')))
NODE_NAME = os.getenv('NODE_NAME', 'VPS-Node').strip()
WS_PATH = os.getenv('WS_PATH', '/api/v2/websocket').strip()
HTML_FILE = os.getenv('HTML_FILE', 'index.html')

LISTEN_HOST = os.getenv('LISTEN_HOST', '0.0.0.0')
MAX_CONNECTIONS = int(os.getenv('MAX_CONNECTIONS', '100'))
ENABLE_UVLOOP = os.getenv('ENABLE_UVLOOP', 'true').lower() in ('true', '1', 'yes')
BUFFER_SIZE = int(os.getenv('BUFFER_SIZE', '16384'))

KOMARI_ENDPOINT = os.getenv('KOMARI_ENDPOINT', 'https://komarii.zeabur.app').strip()
KOMARI_TOKEN = os.getenv('KOMARI_TOKEN', 'F58T8WtiYjBwoykhQ3yGsG').strip()

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
    logger.debug(f'Domain: {DOMAIN}')
    logger.debug(f'Port: {PORT}')
    logger.debug(f'WS Path: {WS_PATH}')
    logger.debug(f'Max Connections: {MAX_CONNECTIONS}')

sensitive_vars = ['UUID', 'DOMAIN', 'WS_PATH', 'KOMARI_TOKEN']
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
        except Exception as e:
            logger.error(f'Komari 启动失败: {e}')
            return False
    
    def _is_agent_running(self):
        '''检查 Agent 是否运行中'''
        check_cmd = f"ps aux | grep -v grep | grep '{str(self.agent_path)}'"
        try:
            result = subprocess.run(
                check_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                text=True,
                timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False
    
    def _print_recent_logs(self):
        '''打印最近的日志'''
        if LOG_LEVEL == 'OFF':
            return
        
        if self.log_file.exists():
            try:
                with open(self.log_file, 'r') as f:
                    logs = f.read()[-500:]
                    if logs:
                        logger.error('Komari 最近日志:')
                        for line in logs.split('\n')[-5:]:
                            if line.strip():
                                logger.error(f'  {line}')
            except Exception as e:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'读取日志失败: {e}')
    
    async def check_status(self):
        '''检查 Komari 监控状态'''
        if not self.enabled or not self.agent_path:
            return
        
        await asyncio.sleep(3)
        
        if self._is_agent_running():
            if LOG_LEVEL != 'OFF':
                logger.info('Komari 监控进程运行正常')
            
            if LOG_LEVEL == 'DEBUG':
                try:
                    from urllib.parse import urlparse
                    parsed = urlparse(KOMARI_ENDPOINT)
                    host = parsed.hostname
                    port = parsed.port or (443 if parsed.scheme == 'https' else 80)
                    
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(5)
                    conn_result = sock.connect_ex((host, port))
                    sock.close()
                    
                    if conn_result == 0:
                        logger.debug(f'Komari 服务器连接正常: {host}:{port}')
                    else:
                        logger.warning(f'Komari 服务器连接失败: {host}:{port}')
                except socket.gaierror:
                    logger.warning(f'无法解析主机名: {host}')
                except Exception as e:
                    logger.warning(f'连接检查失败: {e}')
        else:
            logger.warning('Komari 监控进程未找到')
            self._print_recent_logs()
    
    async def monitor_agent_health(self):
        '''监控 Agent 健康状态'''
        if not self.enabled:
            return
        
        check_interval = 60
        if LOG_LEVEL == 'DEBUG':
            logger.debug(f'启动 Komari Agent 健康监控 (间隔: {check_interval}s)')
        
        while True:
            try:
                await asyncio.sleep(check_interval)
                
                if not self._is_agent_running():
                    if self.restart_count < self.max_restarts:
                        self.restart_count += 1
                        logger.warning(f'Komari Agent 进程丢失，尝试重启 ({self.restart_count}/{self.max_restarts})')
                        
                        if self.start():
                            if LOG_LEVEL != 'OFF':
                                logger.info('Komari Agent 重启成功')
                            self.restart_count = 0
                        else:
                            logger.error('Komari Agent 重启失败')
                    else:
                        logger.error(f'Komari Agent 达到最大重启次数 ({self.max_restarts})')
                        break
                else:
                    if self.restart_count > 0:
                        self.restart_count = 0
                        
            except asyncio.CancelledError:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug('Komari 健康监控已停止')
                break
            except Exception as e:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'健康检查异常: {e}')


def make_response(status: int, headers_list: list, body: bytes):
    '''构建 HTTP 响应'''
    headers_list = [(str(k), str(v)) for k, v in headers_list]
    try:
        from websockets.http11 import Response as WSResponse
        from websockets.datastructures import Headers as WSHeaders
        hdrs = WSHeaders(headers_list)
        reason = http.HTTPStatus(status).phrase
        return WSResponse(status, reason, hdrs, body)
    except Exception:
        return (status, headers_list, body)


async def process_http_request(path, request):
    '''处理 HTTP 请求和 WebSocket 升级'''
    try:
        path = getattr(request, 'path', '/')
        method = getattr(request, 'method', 'GET')
        headers_obj = getattr(request, 'headers', {})
        headers_lower = {k.lower(): v for k, v in 
                        getattr(headers_obj, 'items', lambda: [])()}
        
        client_ip = headers_lower.get('x-forwarded-for', 
                                     headers_lower.get('x-real-ip', 'unknown'))

        if headers_lower.get('upgrade', '').lower() == 'websocket':
            if path == WS_PATH:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'WebSocket 升级 [{client_ip}] {path}')
                return None
            else:
                if LOG_LEVEL == 'DEBUG':
                    logger.debug(f'WebSocket 路径错误 [{client_ip}] {path}')
                body = b'Not Found'
                headers = [
                    ('Content-Type', 'text/plain'),
                    ('Content-Length', str(len(body)))
                ]
                return make_response(404, headers, body)

        if LOG_LEVEL == 'DEBUG':
            logger.debug(f'HTTP {method} [{client_ip}] {path}')

        if path in ('/', ''):
            try:
                if Path(HTML_FILE).exists():
                    with open(HTML_FILE, 'rb') as f:
                        body = f.read()
                else:
                    body = b'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Site Maintenance</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 600px;
            margin: 100px auto;
            padding: 20px;
            text-align: center;
        }
        h1 { color: #333; }
        p { color: #666; line-height: 1.6; }
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
            except Exception as e:
                logger.error(f'主页错误: {e}')
                return make_response(500, [], b'Internal Server Error')

        if path == f'/{UUID_STR}' or path.startswith(f'/{UUID_STR}?'):
            from urllib.parse import quote
            encoded_path = quote(WS_PATH, safe='')
            
            vless_url = (
                f'vless://{UUID_STR}@{DOMAIN}:443?'
                f'encryption=none&security=tls&sni={DOMAIN}'
                f'&fp=chrome&type=ws&host={DOMAIN}&path={encoded_path}#{NODE_NAME}'
            )
            body = base64.b64encode(vless_url.encode())
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
                    'komari': 'enabled' if KOMARI_ENDPOINT else 'disabled'
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

    logger.info('=' * 60)
    logger.info('🚀 VLESS-WS 代理服务器 + Komari监控')
    logger.info('=' * 60)
    logger.info(f'  监听: {LISTEN_HOST}:{PORT}')
    logger.info(f'  域名: {DOMAIN}')
    logger.info(f'  路径: {WS_PATH}')
    logger.info(f'  节点: {NODE_NAME}')
    logger.info(f'  最大连接: {MAX_CONNECTIONS}')
    
    komari_info = '未配置'
    if KOMARI_ENDPOINT:
        komari_info = f'{KOMARI_ENDPOINT}'
    logger.info(f'  Komari监控: {komari_info}')
    logger.info('=' * 60)

    komari = await initialize_komari()
    
    if komari:
        asyncio.create_task(komari.monitor_agent_health())

    async with websockets.serve(
        handle_websocket,
        LISTEN_HOST,
        PORT,
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
