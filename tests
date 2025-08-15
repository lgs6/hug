#!/bin/bash

# ==============================================================================
# 固定参数配置区 (全自动无交互)
#
# 说明:
# 1. 在此区域填好您的所有配置信息。
# 2. 保存后，直接运行脚本即可，全程无需任何操作。
# 3. 如果某项配置您不需要，请保持其值为空字符串，例如: NEZHA_SERVER=""
# ==============================================================================

# --- 基础配置 (必填项) ---

# VLESS 协议的 UUID。
# 务必修改为您自己的 UUID，可从 https://www.uuidgenerator.net/ 在线生成。
# 如果留空，脚本会自动生成一个。
UUID="67ed0641-8db7-4100-acf1-20c12415d447"

# 节点名称，会显示在客户端中。
NAME="🇺🇸美国-hug"

# --- 网络配置 ---

# 对外提供服务的端口，例如 80, 443, 3000。
PORT="59870"

# Cloudflare 优选 IP 或域名。留空将默认使用 "joeyblog.net"。
CFIP="joeyblog.net"

# Cloudflare 优选端口，例如 443, 2096, 8443。
CFPORT="443"

# Argo 隧道在程序内部监听的端口，通常无需修改。
ARGO_PORT="50001"

# 生成的订阅链接的路径，例如 "sub"。
SUB_PATH="sub888"

# --- 高级配置 (按需填写) ---

# 是否启用 Hugging Face API 自动保活功能。
# 填 "true" 开启，填 "false" 或留空则关闭。
# 如果开启，下面的 HF_TOKEN 和 HF_REPO_ID 必须填写。
ENABLE_HF_KEEPALIVE="true"

# Hugging Face 的访问令牌 (Token)。
# 获取地址: https://huggingface.co/settings/tokens
HF_TOKEN="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"

# 需要保活的 Hugging Face 仓库 ID (例如: your-username/your-repo-name)。
HF_REPO_ID="enLinJi/bot"

# 哪吒监控的服务器地址。
NEZHA_SERVER="site.913391.xyz:443"

# 哪吒监控的服务器端口。
NEZHA_PORT=""

# 哪吒监控的密钥。
NEZHA_KEY="KQ81PDSW8Ib7x96R5dAz3yWuTBJYCw5u"

# Argo 固定隧道的域名 (需要您预先在 Cloudflare 配置好)。
ARGO_DOMAIN="spaces.913391.xyz"

# Argo 固定隧道的 Token (JSON 格式的密钥内容)。
ARGO_AUTH="eyJhIjoiZmJmZDk0YWY4NzlmYjgzNzA1NjEwYmQ5ZjEyZWQ1MzYiLCJ0IjoiNWMwMzYwZWYtZWRjNy00OGZlLTkxMTMtMDYzMmY0MDU0MjEzIiwicyI6IlpHTXdOVGRoT1dRdE0yTmhOeTAwT1RrMUxUazNZV010T0dSalpESTVOMkUyWWpoaiJ9"

# Telegram Bot 的 Token，用于推送通知。
BOT_TOKEN=""

# 接收通知的 Telegram Chat ID。
CHAT_ID=""


# ==============================================================================
# 脚本主体部分 - 您通常无需修改以下任何内容
# ==============================================================================

# --- 脚本环境设置 ---
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

NODE_INFO_FILE="$HOME/.xray_nodes_info"
PROJECT_DIR_NAME="python-xray-argo"

# --- 辅助函数：生成 UUID ---
generate_uuid() {
    if command -v uuidgen &> /dev/null; then
        uuidgen | tr '[:upper:]' '[:lower:]'
    elif command -v python3 &> /dev/null; then
        python3 -c "import uuid; print(str(uuid.uuid4()))"
    else
        hexdump -n 16 -e '4/4 "%08X" 1 "\n"' /dev/urandom | sed 's/\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)\(..\)/\1\2\3\4-\5\6-\7\8-\9\10-\11\12\13\14\15\16/' | tr '[:upper:]' '[:lower:]'
    fi
}

# --- 脚本主流程 ---
clear
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Python Xray Argo 部署脚本 (全自动版)  ${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo -e "${BLUE}检测到无交互模式，将使用脚本内预设的参数进行部署...${NC}"

# 1. 检查并安装依赖
echo -e "\n${YELLOW}--> 步骤 1/4: 检查并安装依赖...${NC}"
if ! command -v python3 &> /dev/null; then
    sudo apt-get update && sudo apt-get install -y python3 python3-pip
fi
if ! python3 -c "import requests" &> /dev/null; then
    pip3 install requests
fi
echo -e "${GREEN}依赖检查完成。${NC}"

# 2. 准备项目文件
echo -e "\n${YELLOW}--> 步骤 2/4: 准备项目文件...${NC}"
if [ ! -d "$PROJECT_DIR_NAME" ]; then
    echo "正在从 GitHub 下载项目..."
    if command -v git &> /dev/null; then git clone https://github.com/eooce/python-xray-argo.git "$PROJECT_DIR_NAME"; else
        wget -q https://github.com/eooce/python-xray-argo/archive/refs/heads/main.zip -O project.zip
        if ! command -v unzip &> /dev/null; then sudo apt-get install -y unzip; fi
        unzip -q project.zip && mv python-xray-argo-main "$PROJECT_DIR_NAME" && rm project.zip
    fi
else
    echo "项目目录已存在，跳过下载。"
fi
cd "$PROJECT_DIR_NAME"
cp app.py app.py.backup
echo -e "${GREEN}项目文件准备就绪。${NC}"

# 3. 应用固定配置
echo -e "\n${YELLOW}--> 步骤 3/4: 应用预设参数配置...${NC}"
# 处理 UUID
if [ -z "$UUID" ]; then
    UUID=$(generate_uuid)
    echo "UUID为空，已自动生成: $UUID"
fi
sed -i "s/UUID = os.environ.get('UUID', '[^']*')/UUID = os.environ.get('UUID', '$UUID')/" app.py

# 处理其他参数
if [ -n "$NAME" ]; then sed -i "s/NAME = os.environ.get('NAME', '[^']*')/NAME = os.environ.get('NAME', '$NAME')/" app.py; fi
if [ -n "$PORT" ]; then sed -i "s/PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or [0-9]*)/PORT = int(os.environ.get('SERVER_PORT') or os.environ.get('PORT') or $PORT)/" app.py; fi
if [ -z "$CFIP" ]; then CFIP="joeyblog.net"; fi
sed -i "s/CFIP = os.environ.get('CFIP', '[^']*')/CFIP = os.environ.get('CFIP', '$CFIP')/" app.py
if [ -n "$CFPORT" ]; then sed -i "s/CFPORT = int(os.environ.get('CFPORT', '[^']*'))/CFPORT = int(os.environ.get('CFPORT', '$CFPORT'))/" app.py; fi
if [ -n "$ARGO_PORT" ]; then sed -i "s/ARGO_PORT = int(os.environ.get('ARGO_PORT', '[^']*'))/ARGO_PORT = int(os.environ.get('ARGO_PORT', '$ARGO_PORT_INPUT'))/" app.py; fi
if [ -n "$SUB_PATH" ]; then sed -i "s/SUB_PATH = os.environ.get('SUB_PATH', '[^']*')/SUB_PATH = os.environ.get('SUB_PATH', '$SUB_PATH')/" app.py; fi
if [ -n "$NEZHA_SERVER" ]; then sed -i "s|NEZHA_SERVER = os.environ.get('NEZHA_SERVER', '[^']*')|NEZHA_SERVER = os.environ.get('NEZHA_SERVER', '$NEZHA_SERVER')|" app.py; fi
if [ -n "$NEZHA_PORT" ]; then sed -i "s|NEZHA_PORT = os.environ.get('NEZHA_PORT', '[^']*')|NEZHA_PORT = os.environ.get('NEZHA_PORT', '$NEZHA_PORT')|" app.py; fi
if [ -n "$NEZHA_KEY" ]; then sed -i "s|NEZHA_KEY = os.environ.get('NEZHA_KEY', '[^']*')|NEZHA_KEY = os.environ.get('NEZHA_KEY', '$NEZHA_KEY')|" app.py; fi
if [ -n "$ARGO_DOMAIN" ]; then sed -i "s|ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', '[^']*')|ARGO_DOMAIN = os.environ.get('ARGO_DOMAIN', '$ARGO_DOMAIN')|" app.py; fi
if [ -n "$ARGO_AUTH" ]; then sed -i "s|ARGO_AUTH = os.environ.get('ARGO_AUTH', '[^']*')|ARGO_AUTH = os.environ.get('ARGO_AUTH', '$ARGO_AUTH')|" app.py; fi
if [ -n "$BOT_TOKEN" ]; then sed -i "s|BOT_TOKEN = os.environ.get('BOT_TOKEN', '[^']*')|BOT_TOKEN = os.environ.get('BOT_TOKEN', '$BOT_TOKEN')|" app.py; fi
if [ -n "$CHAT_ID" ]; then sed -i "s|CHAT_ID = os.environ.get('CHAT_ID', '[^']*')|CHAT_ID = os.environ.get('CHAT_ID', '$CHAT_ID')|" app.py; fi
echo -e "${GREEN}所有参数已成功写入配置文件。${NC}"

# 4. 启动服务并输出结果
echo -e "\n${YELLOW}--> 步骤 4/4: 启动服务并生成节点...${NC}"

# 应用优化补丁（这部分逻辑与之前版本相同）
# ...[此处省略了与之前版本完全相同的 youtube_patch.py 创建与执行逻辑]...
cat > youtube_patch.py << 'EOF'
# coding: utf-8
import os, base64, json, subprocess, time
with open('app.py', 'r', encoding='utf-8') as f: content = f.read()
old_config = 'config ={"log":{"access":"/dev/null","error":"/dev/null","loglevel":"none",},"inbounds":[{"port":ARGO_PORT ,"protocol":"vless","settings":{"clients":[{"id":UUID ,"flow":"xtls-rprx-vision",},],"decryption":"none","fallbacks":[{"dest":3001 },{"path":"/vless-argo","dest":3002 },{"path":"/vmess-argo","dest":3003 },{"path":"/trojan-argo","dest":3004 },],},"streamSettings":{"network":"tcp",},},{"port":3001 ,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID },],"decryption":"none"},"streamSettings":{"network":"ws","security":"none"}},{"port":3002 ,"listen":"127.0.0.1","protocol":"vless","settings":{"clients":[{"id":UUID ,"level":0 }],"decryption":"none"},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/vless-argo"}},"sniffing":{"enabled":True ,"destOverride":["http","tls","quic"],"metadataOnly":False }},{"port":3003 ,"listen":"127.0.0.1","protocol":"vmess","settings":{"clients":[{"id":UUID ,"alterId":0 }]},"streamSettings":{"network":"ws","wsSettings":{"path":"/vmess-argo"}},"sniffing":{"enabled":True ,"destOverride":["http","tls","quic"],"metadataOnly":False }},{"port":3004 ,"listen":"127.0.0.1","protocol":"trojan","settings":{"clients":[{"password":UUID },]},"streamSettings":{"network":"ws","security":"none","wsSettings":{"path":"/trojan-argo"}},"sniffing":{"enabled":True ,"destOverride":["http","tls","quic"],"metadataOnly":False }},],"outbounds":[{"protocol":"freedom","tag": "direct" },{"protocol":"blackhole","tag":"block"}]}'
new_config = '''config = {"log": {"access": "/dev/null","error": "/dev/null","loglevel": "none"},"inbounds": [{"port": ARGO_PORT,"protocol": "vless","settings": {"clients": [{"id": UUID, "flow": "xtls-rprx-vision"}],"decryption": "none","fallbacks": [{"dest": 3001},{"path": "/vless-argo", "dest": 3002},{"path": "/vmess-argo", "dest": 3003},{"path": "/trojan-argo", "dest": 3004}]},"streamSettings": {"network": "tcp"}},{"port": 3001,"listen": "127.0.0.1","protocol": "vless","settings": {"clients": [{"id": UUID}],"decryption": "none"},"streamSettings": {"network": "ws", "security": "none"}},{"port": 3002,"listen": "127.0.0.1","protocol": "vless","settings": {"clients": [{"id": UUID, "level": 0}],"decryption": "none"},"streamSettings": {"network": "ws","security": "none","wsSettings": {"path": "/vless-argo"}},"sniffing": {"enabled": True,"destOverride": ["http", "tls", "quic"],"metadataOnly": False}},{"port": 3003,"listen": "127.0.0.1","protocol": "vmess","settings": {"clients": [{"id": UUID, "alterId": 0}]},"streamSettings": {"network": "ws","wsSettings": {"path": "/vmess-argo"}},"sniffing": {"enabled": True,"destOverride": ["http", "tls", "quic"],"metadataOnly": False}},{"port": 3004,"listen": "127.0.0.1","protocol": "trojan","settings": {"clients": [{"password": UUID}]},"streamSettings": {"network": "ws","security": "none","wsSettings": {"path": "/trojan-argo"}},"sniffing": {"enabled": True,"destOverride": ["http", "tls", "quic"],"metadataOnly": False}}],"outbounds": [{"protocol": "freedom", "tag": "direct"},{"protocol": "vmess","tag": "youtube","settings": {"vnext": [{"address": "172.233.171.224","port": 16416,"users": [{"id": "8c1b9bea-cb51-43bb-a65c-0af31bbbf145","alterId": 0}]}]},"streamSettings": {"network": "tcp"}},{"protocol": "blackhole", "tag": "block"}],"routing": {"domainStrategy": "IPIfNonMatch","rules": [{"type": "field","domain": ["youtube.com", "youtu.be", "googlevideo.com", "ytimg.com", "gstatic.com", "googleapis.com", "ggpht.com", "googleusercontent.com"],"outboundTag": "youtube"}]}}'''
content = content.replace(old_config, new_config)
old_generate_function = '''# Generate links and subscription content
async def generate_links(argo_domain):
    meta_info = subprocess.run(['curl', '-s', 'https://speed.cloudflare.com/meta'], capture_output=True, text=True)
    meta_info = meta_info.stdout.split('"')
    ISP = f"{meta_info[25]}-{meta_info[17]}".replace(' ', '_').strip()
    time.sleep(2)
    VMESS = {"v": "2", "ps": f"{NAME}-{ISP}", "add": CFIP, "port": CFPORT, "id": UUID, "aid": "0", "scy": "none", "net": "ws", "type": "none", "host": argo_domain, "path": "/vmess-argo?ed=2560", "tls": "tls", "sni": argo_domain, "alpn": "", "fp": "chrome"}
    list_txt = f"""
vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{NAME}-{ISP}
  
vmess://{ base64.b64encode(json.dumps(VMESS).encode('utf-8')).decode('utf-8')}

trojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{NAME}-{ISP}
    """
    with open(os.path.join(FILE_PATH, 'list.txt'), 'w', encoding='utf-8') as list_file: list_file.write(list_txt)
    sub_txt = base64.b64encode(list_txt.encode('utf-8')).decode('utf-8')
    with open(os.path.join(FILE_PATH, 'sub.txt'), 'w', encoding='utf-8') as sub_file: sub_file.write(sub_txt)
    print(sub_txt)
    print(f"{FILE_PATH}/sub.txt saved successfully")
    send_telegram()
    upload_nodes()
    return sub_txt'''
new_generate_function = '''# Generate links and subscription content
async def generate_links(argo_domain):
    meta_info = subprocess.run(['curl', '-s', 'https://speed.cloudflare.com/meta'], capture_output=True, text=True)
    meta_info = meta_info.stdout.split('"')
    ISP = f"{meta_info[25]}-{meta_info[17]}".replace(' ', '_').strip()
    time.sleep(2)
    VMESS_TLS = {"v": "2", "ps": f"{NAME}-{ISP}-TLS", "add": CFIP, "port": CFPORT, "id": UUID, "aid": "0", "scy": "none", "net": "ws", "type": "none", "host": argo_domain, "path": "/vmess-argo?ed=2560", "tls": "tls", "sni": argo_domain, "alpn": "", "fp": "chrome"}
    VMESS_80 = {"v": "2", "ps": f"{NAME}-{ISP}-80", "add": CFIP, "port": "80", "id": UUID, "aid": "0", "scy": "none", "net": "ws", "type": "none", "host": argo_domain, "path": "/vmess-argo?ed=2560", "tls": "", "sni": "", "alpn": "", "fp": ""}
    list_txt = f"""
vless://{UUID}@{CFIP}:{CFPORT}?encryption=none&security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{NAME}-{ISP}-TLS
  
vmess://{ base64.b64encode(json.dumps(VMESS_TLS).encode('utf-8')).decode('utf-8')}

trojan://{UUID}@{CFIP}:{CFPORT}?security=tls&sni={argo_domain}&fp=chrome&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{NAME}-{ISP}-TLS

vless://{UUID}@{CFIP}:80?encryption=none&security=none&type=ws&host={argo_domain}&path=%2Fvless-argo%3Fed%3D2560#{NAME}-{ISP}-80

vmess://{ base64.b64encode(json.dumps(VMESS_80).encode('utf-8')).decode('utf-8')}

trojan://{UUID}@{CFIP}:80?security=none&type=ws&host={argo_domain}&path=%2Ftrojan-argo%3Fed%3D2560#{NAME}-{ISP}-80
    """
    with open(os.path.join(FILE_PATH, 'list.txt'), 'w', encoding='utf-8') as list_file: list_file.write(list_txt)
    sub_txt = base64.b64encode(list_txt.encode('utf-8')).decode('utf-8')
    with open(os.path.join(FILE_PATH, 'sub.txt'), 'w', encoding='utf-8') as sub_file: sub_file.write(sub_txt)
    print(sub_txt)
    print(f"{FILE_PATH}/sub.txt saved successfully")
    send_telegram()
    upload_nodes()
    return sub_txt'''
content = content.replace(old_generate_function, new_generate_function)
with open('app.py', 'w', encoding='utf-8') as f: f.write(content)
EOF
python3 youtube_patch.py && rm youtube_patch.py

pkill -f "python3 app.py" > /dev/null 2>&1 && sleep 2
nohup python3 app.py > app.log 2>&1 &
APP_PID=$(pgrep -f "python3 app.py" | head -1)
echo "服务已在后台启动 (PID: $APP_PID)。"

if [[ "$ENABLE_HF_KEEPALIVE" == "true" ]] && [ -n "$HF_TOKEN" ] && [ -n "$HF_REPO_ID" ]; then
    echo "正在启动 Hugging Face 保活任务..."
    pkill -f "keep_alive_task.sh" > /dev/null 2>&1
    echo "#!/bin/bash" > keep_alive_task.sh
    echo "while true; do curl -s -o /dev/null -w \"%{http_code}\" --header \"Authorization: Bearer $HF_TOKEN\" \"https://huggingface.co/api/spaces/$HF_REPO_ID\" &> keep_alive_status.log; sleep 120; done" >> keep_alive_task.sh
    chmod +x keep_alive_task.sh && nohup ./keep_alive_task.sh >/dev/null 2>&1 &
    echo "保活任务已启动。"
fi

echo "正在等待 Argo 隧道建立并生成节点 (最长等待10分钟)..."
MAX_WAIT=600; WAIT_COUNT=0; NODE_INFO=""
while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if [ -f ".cache/sub.txt" ]; then NODE_INFO=$(cat .cache/sub.txt 2>/dev/null); fi
    if [ -z "$NODE_INFO" ] && [ -f "sub.txt" ]; then NODE_INFO=$(cat sub.txt 2>/dev/null); fi
    if [ -n "$NODE_INFO" ]; then break; fi
    sleep 5; WAIT_COUNT=$((WAIT_COUNT + 5))
done

if [ -z "$NODE_INFO" ]; then
    echo -e "${RED}错误: 等待超时，未能获取到节点信息。请检查日志。${NC}"
    exit 1
fi

# --- 输出最终结果 ---
PUBLIC_IP=$(curl -s https://api.ipify.org || echo "YOUR_PUBLIC_IP")
DECODED_NODES=$(echo "$NODE_INFO" | base64 -d 2>/dev/null || echo "$NODE_INFO")
echo -e "\n${GREEN}========================================${NC}"
echo -e "${GREEN}                🎉 部署完成 🎉                ${NC}"
echo -e "${GREEN}========================================${NC}"
echo -e "\n${YELLOW}--- 节点订阅信息 ---${NC}"
echo -e "${BLUE}订阅地址: ${GREEN}http://$PUBLIC_IP:$PORT/$SUB_PATH${NC}"
echo -e "\n${YELLOW}--- 节点分享链接 ---${NC}"
echo "$DECODED_NODES"
SAVE_INFO="
--- 节点信息备份 @ $(date) ---
订阅地址: http://$PUBLIC_IP:$PORT/$SUB_PATH
--- 节点链接 ---
$DECODED_NODES"
echo "$SAVE_INFO" > "$NODE_INFO_FILE"
echo -e "\n${GREEN}节点信息已备份至: $NODE_INFO_FILE${NC}"
exit 0
