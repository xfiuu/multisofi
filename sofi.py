# PHIÊN BẢN TÍCH HỢP: Panel + Logic Bot Nhặt Thẻ SOFI (Button-based)
import os, requests, json, uuid, time, re
import discord
from discord.ext import commands
import asyncio
import threading
from flask import Flask, request, render_template_string, jsonify
from dotenv import load_dotenv
from waitress import serve

load_dotenv()

# --- CẤU HÌNH BOT ---
main_tokens = os.getenv("MAIN_TOKENS", "").split(",")
BOT_NAMES = ["xsyx", "sofa", "dont", "ayaya", "owo", "astra", "singo", "dia pox", "clam", "rambo", "domixi", "dogi", "sicula", "mo turn", "jan taru", "kio sama"]
SOFI_ID = 853629533855809596 # ID của bot Sofi

# --- BIẾN TRẠNG THÁI & QUẢN LÝ BOT ---
servers = [] # Đây là danh sách các panel
server_start_time = time.time()

class ThreadSafeBotManager:
    """Quản lý các instance bot đang chạy trong các luồng riêng biệt"""
    def __init__(self):
        self._bots = {}
        self._lock = threading.RLock()

    def add_bot(self, bot_id, bot_data):
        with self._lock:
            self._bots[bot_id] = bot_data
            print(f"[Bot Manager] ✅ Đã thêm bot: {bot_id}", flush=True)

    def remove_bot(self, bot_id):
        with self._lock:
            bot_data = self._bots.pop(bot_id, None)
            if bot_data and bot_data.get('instance'):
                bot = bot_data['instance']
                loop = bot_data['loop']
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(bot.close(), loop)
                print(f"[Bot Manager] 🗑️ Đã xóa và yêu cầu dọn dẹp bot: {bot_id}", flush=True)
            return bot_data

    def get_bot_data(self, bot_id):
        with self._lock:
            return self._bots.get(bot_id)

bot_manager = ThreadSafeBotManager()

# --- HÀM TRỢ GIÚP ---
def get_bot_name(bot_id_str):
    try:
        parts = bot_id_str.split('_')
        b_type, b_index = parts[0], int(parts[1])
        if b_type == 'main':
            return BOT_NAMES[b_index - 1] if 0 < b_index <= len(BOT_NAMES) else f"MAIN_{b_index}"
        return f"SUB_{b_index+1}"
    except (IndexError, ValueError):
        return bot_id_str.upper()

def get_heart_count(button):
    """Trích xuất số tim từ label của button (lấy từ multisofi.py)"""
    text = button.label
    if not text: return 0
    numbers = re.findall(r'\d+', str(text))
    return int("".join(numbers)) if numbers else 0

# --- LƯU & TẢI CÀI ĐẶT (JSONBIN) ---
def save_settings():
    api_key, bin_id = os.getenv("JSONBIN_API_KEY"), os.getenv("JSONBIN_BIN_ID")
    settings_data = {'servers': servers, 'last_save_time': time.time()}
    if not (api_key and bin_id): return
    headers = {'Content-Type': 'application/json', 'X-Master-Key': api_key}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    try:
        requests.put(url, json=settings_data, headers=headers, timeout=10)
        print("[Settings] ✅ Đã lưu 'servers' lên JSONBin.io.", flush=True)
    except Exception as e:
        print(f"[Settings] ❌ Lỗi khi lưu JSONBin: {e}", flush=True)

def load_settings():
    global servers
    api_key, bin_id = os.getenv("JSONBIN_API_KEY"), os.getenv("JSONBIN_BIN_ID")
    if not (api_key and bin_id): return
    headers = {'X-Master-Key': api_key}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
    try:
        req = requests.get(url, headers=headers, timeout=10)
        if req.status_code == 200:
            record = req.json().get("record", {})
            servers.clear()
            servers.extend(record.get('servers', []))
            print(f"[Settings] ✅ Đã tải {len(servers)} server(s) từ JSONBin.io.", flush=True)
    except Exception as e:
        print(f"[Settings] ⚠️ Lỗi tải từ JSONBin: {e}. Bắt đầu với danh sách trống.", flush=True)

# --- LOGIC NHẶT THẺ (TÍCH HỢP TỪ multisofi.py) ---
async def handle_sofi_grab(bot, message, bot_num):
    channel_id = str(message.channel.id)
    
    # 1. Tìm panel server tương ứng với kênh
    target_server = next((s for s in servers if s.get('main_channel_id') == channel_id), None)
    if not target_server:
        return # Tin nhắn này không ở trong kênh main channel nào được cấu hình

    # 2. Kiểm tra xem bot này có được bật nhặt ở server này không
    bot_num_str = str(bot_num)
    grab_key = f'auto_grab_enabled_{bot_num_str}'
    if not target_server.get(grab_key, False):
        # print(f"[Sofi Grab] Bot {bot_num} đã tắt nhặt tại server {target_server.get('name')}")
        return

    # 3. Lấy cấu hình min/max hearts từ panel
    min_hearts_needed = target_server.get(f'heart_threshold_{bot_num_str}', 50)
    max_hearts_allowed = target_server.get(f'max_heart_threshold_{bot_num_str}', 99999)

    print(f"--- 📊 [Sofi Grab] Bot {bot_num} phân tích thẻ (Yêu cầu: {min_hearts_needed}♡ - {max_hearts_allowed}♡) ---")

    try:
        fetched_message = None
        found_buttons = []
        # Cố gắng fetch message vài lần để đợi button xuất hiện
        for _ in range(5):
            try:
                fetched_message = await message.channel.fetch_message(message.id)
                found_buttons = [c for row in fetched_message.components for c in row.children if isinstance(c, discord.Button)]
                if found_buttons: break
            except discord.NotFound:
                print(f"[Sofi Grab] ❌ Không tìm thấy tin nhắn {message.id}.")
                return
            except Exception as e:
                # print(f"[Sofi Grab] ⚠️ Lỗi fetch_message: {e}")
                pass
            await asyncio.sleep(0.5) # Chờ 0.5s rồi thử lại

        if found_buttons:
            best_button = None
            max_hearts = -1 # Bắt đầu từ -1 để thẻ 0 tim vẫn được xem xét

            for idx, button in enumerate(found_buttons):
                hearts = get_heart_count(button)
                # print(f"   ➤ Nút {idx+1}: {hearts} tim")
                
                # Kiểm tra xem có trong ngưỡng (min <= hearts <= max)
                if min_hearts_needed <= hearts <= max_hearts_allowed:
                    if hearts > max_hearts:
                        max_hearts = hearts
                        best_button = button
                    elif hearts == max_hearts and best_button is None: # Xử lý trường hợp nhiều thẻ = min
                         best_button = button
            
            if best_button:
                await asyncio.sleep(0.5) # Delay nhỏ trước khi click
                await best_button.click()
                print(f"[{bot.user.name}] → 🏆 ĐÃ CLICK nút {max_hearts} tim tại server {target_server.get('name')}!")
            else:
                print(f"[{bot.user.name}] → ⚠️ Không có thẻ nào đủ điều kiện ({min_hearts_needed}♡ - {max_hearts_allowed}♡).")
        else:
            print(f"[{bot.user.name}] → ⚠️ Không tìm thấy button nào trong tin nhắn.")
            
    except Exception as e:
        print(f"[{bot.user.name}] ❌ Lỗi nghiêm trọng khi click: {e}")

# --- KHỞI TẠO BOT (TÍCH HỢP) ---
def initialize_and_run_bot(token, bot_id_str, is_main):
    """Chạy mỗi bot trong một luồng riêng với event loop riêng"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Dùng commands.Bot để có thể click button
    bot = commands.Bot(command_prefix="!", self_bot=True)

    try:
        bot_identifier = int(bot_id_str.split('_')[1])
    except (IndexError, ValueError):
        bot_identifier = 99 # Giá trị dự phòng
    
    @bot.event
    async def on_ready():
        print(f"[Bot] ✅ {'[MAIN]' if is_main else '[SUB]'} Đăng nhập: {bot.user.name} ({bot_id_str})", flush=True)
        # Thêm bot vào manager để các luồng khác có thể truy cập
        bot_manager.add_bot(bot_id_str, {'instance': bot, 'loop': loop, 'thread': threading.current_thread()})
    
    if is_main:
        @bot.event
        async def on_message(message, bot_num=bot_identifier):
            # Chỉ xử lý tin nhắn từ SOFI_ID
            if message.author.id == SOFI_ID:
                # Kiểm tra trigger words (giống multisofi.py)
                if ("dropping" in message.content.lower() or "thả" in message.content.lower()):
                    # print(f"🎯 {bot.user.name} phát hiện drop! Đang soi...")
                    # Gọi hàm xử lý grab, truyền vào bot_num để biết dùng cài đặt nào
                    asyncio.create_task(handle_sofi_grab(bot, message, bot_num))
            
    try:
        loop.run_until_complete(bot.start(token))
    except discord.errors.LoginFailure:
        print(f"[Bot] ❌ Login thất bại cho {bot_id_str}. Token có thể không hợp lệ.", flush=True)
    except Exception as e:
        print(f"[Bot] ❌ Lỗi khi chạy bot {bot_id_str}: {e}", flush=True)
    finally:
        # Dọn dẹp bot khỏi manager khi nó dừng
        bot_manager.remove_bot(bot_id_str)
        loop.close()

# --- FLASK APP & GIAO DIỆN ---
app = Flask(__name__)

# Giao diện HTML (ĐÃ XÓA KTB)
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integrated Panel Manager (Sofi)</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Courier+Prime:wght@400;700&family=Orbitron:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root { --primary-bg: #0a0a0a; --secondary-bg: #1a1a1a; --panel-bg: #111111; --border-color: #333333; --blood-red: #8b0000; --dark-red: #550000; --bone-white: #f8f8ff; --necro-green: #228b22; --text-primary: #f0f0f0; --text-secondary: #cccccc; }
        body { font-family: 'Courier Prime', monospace; background: var(--primary-bg); color: var(--text-primary); margin: 0; padding: 0;}
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }
        .header { text-align: center; margin-bottom: 30px; padding: 20px; border-bottom: 2px solid var(--blood-red); }
        .title { font-family: 'Orbitron', cursive; font-size: 2.5rem; color: var(--blood-red); }
        .main-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(500px, 1fr)); gap: 20px; }
        .panel { background: var(--panel-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 25px; position: relative;}
        .panel h2 { font-family: 'Orbitron', cursive; font-size: 1.4rem; margin-bottom: 20px; border-bottom: 2px solid; padding-bottom: 10px; color: var(--bone-white); }
        .panel h2 i { margin-right: 10px; }
        .btn { background: var(--secondary-bg); border: 1px solid var(--border-color); color: var(--text-primary); padding: 10px 15px; border-radius: 4px; cursor: pointer; font-family: 'Orbitron', monospace; font-weight: 700; text-transform: uppercase; width: 100%; transition: all 0.3s ease; }
        .btn:hover { background: var(--dark-red); border-color: var(--blood-red); }
        .input-group { display: flex; align-items: stretch; gap: 10px; margin-bottom: 15px; }
        .input-group label { background: #000; border: 1px solid var(--border-color); border-right: 0; padding: 10px 15px; border-radius: 4px 0 0 4px; display:flex; align-items:center; min-width: 120px;}
        .input-group input { flex-grow: 1; background: #000; border: 1px solid var(--border-color); color: var(--text-primary); padding: 10px 15px; border-radius: 0 4px 4px 0; font-family: 'Courier Prime', monospace; }
        .grab-section { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding: 15px; background: rgba(0,0,0,0.2); border-radius: 8px;}
        .grab-section h3 { margin: 0; display: flex; align-items: center; gap: 10px; width: 80px; flex-shrink: 0; }
        .grab-section .input-group { margin-bottom: 0; flex-grow: 1; margin-left: 20px;}
        .msg-status { text-align: center; color: var(--necro-green); padding: 12px; border: 1px dashed var(--border-color); border-radius: 4px; margin-bottom: 20px; display: none; }
        .msg-status.error { color: var(--blood-red); border-color: var(--blood-red); }
        .status-panel { grid-column: 1 / -1; }
        .status-row { display: flex; justify-content: space-between; align-items: center; padding: 12px; background: rgba(0,0,0,0.4); border-radius: 8px; }
        .timer-display { font-size: 1.2em; font-weight: 700; }
        .add-server-btn { display: flex; align-items: center; justify-content: center; min-height: 200px; border: 2px dashed var(--border-color); cursor: pointer; transition: all 0.3s ease; }
        .add-server-btn:hover { background: var(--secondary-bg); border-color: var(--blood-red); }
        .add-server-btn i { font-size: 3rem; color: var(--text-secondary); }
        .btn-delete-server { position: absolute; top: 15px; right: 15px; background: var(--dark-red); border: 1px solid var(--blood-red); color: var(--bone-white); width: 30px; height: 30px; border-radius: 50%; cursor: pointer; display:flex; align-items:center; justify-content:center; }
        .server-sub-panel { border-top: 1px solid var(--border-color); margin-top: 20px; padding-top: 20px;}
        .heart-input { flex-grow: 0 !important; width: 100px; text-align: center; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 class="title">Integrated Panel Manager (Sofi)</h1>
        </div>
        <div id="msg-status-container" class="msg-status"> <span id="msg-status-text"></span></div>
        <div class="main-grid">
            <div class="panel status-panel">
                 <div class="status-row">
                    <span><i class="fas fa-server"></i> System Uptime</span>
                    <div><span id="uptime-timer" class="timer-display">--:--:--</span></div>
                </div>
            </div>
            
            {% for server in servers %}
            <div class="panel server-panel" data-server-id="{{ server.id }}">
                <button class="btn-delete-server" title="Delete Server"><i class="fas fa-times"></i></button>
                <h2><i class="fas fa-server"></i> {{ server.name }}</h2>
                
                <div class="server-sub-panel">
                    <h3><i class="fas fa-cogs"></i> Channel Config</h3>
                    <div class="input-group"><label>Main Channel ID</label><input type="text" class="channel-input" data-field="main_channel_id" value="{{ server.main_channel_id or '' }}"></div>
                </div>
                
                <div class="server-sub-panel">
                    <h3><i class="fas fa-crosshairs"></i> Soul Harvest (Card Grab)</h3>
                    {% for bot in main_bots_info %}
                    <div class="grab-section">
                        <h3>{{ bot.name }}</h3>
                        <div class="input-group">
                             <input type="number" class="harvest-threshold heart-input" data-node="{{ bot.id }}" value="{{ server['heart_threshold_' + bot.id|string] or 50 }}" min="0" placeholder="Min ♡">
                            <input type="number" class="harvest-max-threshold heart-input" data-node="{{ bot.id }}" value="{{ server['max_heart_threshold_' + bot.id|string]|default(99999) }}" min="0" placeholder="Max ♡">
                            <button type="button" class="btn harvest-toggle" data-node="{{ bot.id }}">
                                {{ 'DISABLE' if server['auto_grab_enabled_' + bot.id|string] else 'ENABLE' }}
                            </button>
                        </div>
                    </div>
                    {% endfor %}
                </div>
                
            </div>
            {% endfor %}
            
            <div class="panel add-server-btn" id="add-server-btn"> <i class="fas fa-plus"></i></div>
        </div>
    </div>
<script>
    document.addEventListener('DOMContentLoaded', function () {
        const msgStatusContainer = document.getElementById('msg-status-container');
        const msgStatusText = document.getElementById('msg-status-text');

        function showStatusMessage(message, type = 'success', duration = 4000) {
            if (!message) return;
            msgStatusText.textContent = message;
            msgStatusContainer.className = `msg-status ${type === 'error' ? 'error' : ''}`;
            msgStatusContainer.style.display = 'block';
            setTimeout(() => { msgStatusContainer.style.display = 'none'; }, duration);
        }

        async function postData(url = '', data = {}) {
            try {
                const response = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) });
                const result = await response.json();
                showStatusMessage(result.message, result.status !== 'success' ? 'error' : 'success');
                
                if (result.status === 'success' && url !== '/api/save_settings') {
                    if (window.saveTimeout) clearTimeout(window.saveTimeout);
                    window.saveTimeout = setTimeout(() => fetch('/api/save_settings', { method: 'POST' }), 500);
                }
                
                if (result.status === 'success' && result.reload) { 
                    setTimeout(() => window.location.reload(), 500); 
                }
                if (url === '/api/harvest_toggle') {
                    setTimeout(fetchStatus, 100);
                }
                return result;
            } catch (error) {
                console.error('Error:', error);
                showStatusMessage('Lỗi giao tiếp server.', 'error');
            }
        }

        function formatTime(seconds) {
            if (isNaN(seconds) || seconds < 0) return "--:--:--";
            seconds = Math.floor(seconds);
            const h = Math.floor(seconds / 3600).toString().padStart(2, '0');
            const m = Math.floor((seconds % 3600) / 60).toString().padStart(2, '0');
            const s = (seconds % 60).toString().padStart(2, '0');
            return `${h}:${m}:${s}`;
        }
        
        function updateElement(element, { textContent }) {
            if (!element) return;
            if (textContent !== undefined && element.textContent !== textContent) element.textContent = textContent;
        }

        async function fetchStatus() {
            try {
                const response = await fetch('/status');
                if (!response.ok) return;
                const data = await response.json();
                
                const serverUptimeSeconds = (Date.now() / 1000) - data.server_start_time;
                updateElement(document.getElementById('uptime-timer'), { textContent: formatTime(serverUptimeSeconds) });

                data.servers.forEach(serverData => {
                    const serverPanel = document.querySelector(`.server-panel[data-server-id="${serverData.id}"]`);
                    if (!serverPanel) return;
                    serverPanel.querySelectorAll('.harvest-toggle').forEach(btn => {
                        const node = btn.dataset.node;
                        updateElement(btn, { textContent: serverData[`auto_grab_enabled_${node}`] ? 'DISABLE' : 'ENABLE' });
                    });
                });
                
            } catch (error) { console.error('Error fetching status:', error); }
        }
        setInterval(fetchStatus, 5000);
        fetchStatus();

        document.querySelector('.container').addEventListener('click', e => {
            const button = e.target.closest('button');
            if (!button) return;
            
            const serverPanel = button.closest('.server-panel');
            const serverId = serverPanel ? serverPanel.dataset.serverId : null;

            if (button.classList.contains('btn-delete-server')) {
                if (serverId && confirm('Bạn có chắc muốn xóa panel này?')) {
                    postData('/api/delete_server', { server_id: serverId });
                }
                return;
            }
            
            if (button.classList.contains('harvest-toggle')) {
                if (serverId) {
                    const node = button.dataset.node;
                    postData('/api/harvest_toggle', { 
                        server_id: serverId, 
                        node: node, 
                        threshold: serverPanel.querySelector(`.harvest-threshold[data-node="${node}"]`).value, 
                        max_threshold: serverPanel.querySelector(`.harvest-max-threshold[data-node="${node}"]`).value 
                    });
                }
                return;
            }
        });
        
        document.querySelector('.main-grid').addEventListener('change', e => {
            const target = e.target;
            const serverPanel = target.closest('.server-panel');
            if (serverPanel && target.classList.contains('channel-input')) {
                const payload = { server_id: serverPanel.dataset.serverId };
                payload[target.dataset.field] = target.value;
                postData('/api/update_server_field', payload);
            }
        });

        document.getElementById('add-server-btn').addEventListener('click', () => {
            const name = prompt("Nhập tên cho panel server mới:", "Server Mới");
            if (name && name.trim()) { 
                postData('/api/add_server', { name: name.trim() }); 
            }
        });
    });
</script>
</body>
</html>
"""

@app.route("/")
def index():
    """Hiển thị trang chủ với các panel đã lưu"""
    main_bots_count = len([t for t in main_tokens if t.strip()])
    main_bots_info = []
    for i in range(main_bots_count):
        bot_num = i + 1
        main_bots_info.append({"id": bot_num, "name": get_bot_name(f'main_{bot_num}')})
        
    return render_template_string(HTML_TEMPLATE, 
        servers=sorted(servers, key=lambda s: s.get('name', '')),
        main_bots_info=main_bots_info
    )

@app.route("/api/add_server", methods=['POST'])
def api_add_server():
    name = request.json.get('name')
    if not name: 
        return jsonify({'status': 'error', 'message': 'Tên server là bắt buộc.'}), 400
    
    new_server = {"id": f"server_{uuid.uuid4().hex}", "name": name}
    
    # Thêm các key mặc định cho nhặt thẻ (ĐÃ XÓA KTB)
    main_bots_count = len([t for t in main_tokens if t.strip()])
    for i in range(main_bots_count):
        bot_num = i + 1
        new_server[f'auto_grab_enabled_{bot_num}'] = False
        new_server[f'heart_threshold_{bot_num}'] = 50
        new_server[f'max_heart_threshold_{bot_num}'] = 99999
        
    servers.append(new_server)
    save_settings()
    return jsonify({'status': 'success', 'message': f'✅ Panel "{name}" đã được thêm.', 'reload': True})

@app.route("/api/delete_server", methods=['POST'])
def api_delete_server():
    server_id = request.json.get('server_id')
    servers_count_before = len(servers)
    servers[:] = [s for s in servers if s.get('id') != server_id]
    servers_count_after = len(servers)
    if servers_count_before == servers_count_after:
        return jsonify({'status': 'error', 'message': 'Không tìm thấy panel để xóa.'})
    save_settings()
    return jsonify({'status': 'success', 'message': f'🗑️ Panel đã được xóa.', 'reload': True})

def find_server(server_id): 
    return next((s for s in servers if s.get('id') == server_id), None)

@app.route("/api/update_server_field", methods=['POST'])
def api_update_server_field():
    data = request.json
    server = find_server(data.get('server_id'))
    if not server: 
        return jsonify({'status': 'error', 'message': 'Không tìm thấy server.'}), 404
    key_updated = ""
    for key, value in data.items():
        if key != 'server_id':
            server[key] = value.strip() # Thêm .strip() để xóa khoảng trắng
            key_updated = key
    return jsonify({'status': 'success', 'message': f'🔧 Đã cập nhật {key_updated}.'})

@app.route("/api/harvest_toggle", methods=['POST'])
def api_harvest_toggle():
    data = request.json
    server, node_str = find_server(data.get('server_id')), data.get('node')
    if not server or not node_str: 
        return jsonify({'status': 'error', 'message': 'Yêu cầu không hợp lệ.'}), 400
    
    node = str(node_str)
    grab_key, threshold_key, max_threshold_key = f'auto_grab_enabled_{node}', f'heart_threshold_{node}', f'max_heart_threshold_{node}'
    
    server[grab_key] = not server.get(grab_key, False)
    try:
        server[threshold_key] = int(data.get('threshold', 50))
        server[max_threshold_key] = int(data.get('max_threshold', 99999))
    except (ValueError, TypeError):
        server[threshold_key] = 50
        server[max_threshold_key] = 99999
        
    status_msg = 'ENABLED' if server[grab_key] else 'DISABLED'
    bot_name = get_bot_name(f'main_{node}')
    return jsonify({'status': 'success', 'message': f"🎯 Nhặt thẻ cho {bot_name} đã {status_msg}."})

@app.route("/api/save_settings", methods=['POST'])
def api_save_settings(): 
    save_settings()
    return jsonify({'status': 'success', 'message': '💾 Đã lưu cài đặt.'})

@app.route("/status")
def status_endpoint():
    return jsonify({
        'server_start_time': server_start_time,
        'servers': servers
    })

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("🚀 Integrated Sofi Panel Manager - Đang khởi động...", flush=True)
    load_settings()

    print("🔌 Khởi tạo các bot chính (main bots)...", flush=True)
    bot_threads = []
    
    # Lọc các token hợp lệ
    valid_main_tokens = [t.strip() for t in main_tokens if t.strip()]
    
    for i, token in enumerate(valid_main_tokens):
        bot_num = i + 1
        bot_id = f"main_{bot_num}"
        # Khởi chạy mỗi bot trong một luồng riêng
        thread = threading.Thread(target=initialize_and_run_bot, args=(token, bot_id, True), daemon=True)
        bot_threads.append(thread)
        thread.start()
        
        # Thêm độ trễ giữa các lần khởi động bot để tránh bị rate limit
        delay = random.uniform(3, 5) 
        print(f"[Bot Init] ⏳ Chờ {delay:.2f}s trước khi khởi động bot tiếp theo...", flush=True)
        time.sleep(delay)

    print(f"✅ Đã khởi động {len(bot_threads)} bot chính.")
    
    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Máy chủ web đang chạy tại http://0.0.0.0:{port}", flush=True)
    serve(app, host="0.0.0.0", port=port)
