# PHIÊN BẢN TÍCH HỢP: Quản lý Panel + Cấu hình Nhặt Thẻ
import os, requests, json, uuid, time
from flask import Flask, request, render_template_string, jsonify
from dotenv import load_dotenv
from waitress import serve

load_dotenv()

# --- CẤU HÌNH (Lấy từ code gốc) ---
# Cần biết có bao nhiêu bot chính để tạo panel
main_tokens = os.getenv("MAIN_TOKENS", "").split(",")
BOT_NAMES = ["xsyx", "sofa", "dont", "ayaya", "owo", "astra", "singo", "dia pox", "clam", "rambo", "domixi", "dogi", "sicula", "mo turn", "jan taru", "kio sama"]

# --- BIẾN TRẠNG THÁI ---
servers = [] # Đây là danh sách các panel
server_start_time = time.time()

# --- HÀM TRỢ GIÚP (Lấy từ code gốc) ---
def get_bot_name(bot_id_str):
    try:
        parts = bot_id_str.split('_')
        b_type, b_index = parts[0], int(parts[1])
        if b_type == 'main':
            return BOT_NAMES[b_index - 1] if 0 < b_index <= len(BOT_NAMES) else f"MAIN_{b_index}"
        return f"SUB_{b_index+1}"
    except (IndexError, ValueError):
        return bot_id_str.upper()

# --- LƯU & TẢI CÀI ĐẶT (JSONBIN) ---
def save_settings():
    """Lưu danh sách 'servers' hiện tại lên JSONBin.io"""
    api_key, bin_id = os.getenv("JSONBIN_API_KEY"), os.getenv("JSONBIN_BIN_ID")
    settings_data = {'servers': servers, 'last_save_time': time.time()}
    
    if not (api_key and bin_id):
        print("[Settings] ⚠️ Bỏ qua lưu: Thiếu JSONBIN_API_KEY hoặc JSONBIN_BIN_ID.", flush=True)
        return

    headers = {'Content-Type': 'application/json', 'X-Master-Key': api_key}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}"
    
    try:
        req = requests.put(url, json=settings_data, headers=headers, timeout=10)
        if req.status_code == 200:
            print("[Settings] ✅ Đã lưu danh sách 'servers' lên JSONBin.io.", flush=True)
        else:
            print(f"[Settings] ❌ Lỗi JSONBin (HTTP {req.status_code}): {req.text}", flush=True)
    except Exception as e:
        print(f"[Settings] ❌ Lỗi khi kết nối JSONBin: {e}", flush=True)

def load_settings():
    """Tải danh sách 'servers' từ JSONBin.io khi khởi động"""
    global servers
    api_key, bin_id = os.getenv("JSONBIN_API_KEY"), os.getenv("JSONBIN_BIN_ID")
    
    if not (api_key and bin_id):
        print("[Settings] ⚠️ Bỏ qua tải: Thiếu JSONBIN_API_KEY hoặc JSONBIN_BIN_ID.", flush=True)
        return

    headers = {'X-Master-Key': api_key}
    url = f"https://api.jsonbin.io/v3/b/{bin_id}/latest"
    
    try:
        req = requests.get(url, headers=headers, timeout=10)
        if req.status_code == 200:
            record = req.json().get("record", {})
            servers.clear()
            servers.extend(record.get('servers', []))
            print(f"[Settings] ✅ Đã tải {len(servers)} server(s) từ JSONBin.io.", flush=True)
        else:
            print(f"[Settings] ⚠️ Không thể tải (mã: {req.status_code}). Bắt đầu với danh sách trống.", flush=True)
    except Exception as e:
        print(f"[Settings] ⚠️ Lỗi tải từ JSONBin: {e}. Bắt đầu với danh sách trống.", flush=True)

# --- FLASK APP & GIAO DIỆN ---
app = Flask(__name__)

# Giao diện HTML đã được TÍCH HỢP
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Integrated Panel Manager</title>
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
            <h1 class="title">Integrated Panel Manager</h1>
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
                    <div class="input-group"><label>KTB Channel ID</label><input type="text" class="channel-input" data-field="ktb_channel_id" value="{{ server.ktb_channel_id or '' }}"></div>
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
                
                // Tự động lưu cài đặt sau khi có thay đổi thành công
                if (result.status === 'success' && url !== '/api/save_settings') {
                    if (window.saveTimeout) clearTimeout(window.saveTimeout);
                    // Chờ 1 chút để server xử lý rồi mới save
                    window.saveTimeout = setTimeout(() => fetch('/api/save_settings', { method: 'POST' }), 500);
                }
                
                if (result.status === 'success' && result.reload) { 
                    setTimeout(() => window.location.reload(), 500); 
                }
                // Sau khi toggle, gọi fetchStatus để cập nhật lại text của nút
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
                
                // Cập nhật Uptime
                const serverUptimeSeconds = (Date.now() / 1000) - data.server_start_time;
                updateElement(document.getElementById('uptime-timer'), { textContent: formatTime(serverUptimeSeconds) });

                // PHẦN TÍCH HỢP: Cập nhật text của các nút ENABLE/DISABLE
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
        setInterval(fetchStatus, 5000); // Cập nhật trạng thái mỗi 5 giây
        fetchStatus();

        // Lắng nghe sự kiện click
        document.querySelector('.container').addEventListener('click', e => {
            const button = e.target.closest('button');
            if (!button) return;
            
            const serverPanel = button.closest('.server-panel');
            const serverId = serverPanel ? serverPanel.dataset.serverId : null;

            // Xử lý nút XÓA server
            if (button.classList.contains('btn-delete-server')) {
                if (serverId && confirm('Bạn có chắc muốn xóa panel này?')) {
                    postData('/api/delete_server', { server_id: serverId });
                }
                return;
            }
            
            // PHẦN TÍCH HỢP: Xử lý nút Harvest Toggle
            if (button.classList.contains('harvest-toggle')) {
                if (serverId) {
                    const node = button.dataset.node;
                    postData('/api/harvest_toggle', { 
                        server_id: serverId, 
                        node: node, 
                        // Lấy giá trị min/max heart khi nhấn nút
                        threshold: serverPanel.querySelector(`.harvest-threshold[data-node="${node}"]`).value, 
                        max_threshold: serverPanel.querySelector(`.harvest-max-threshold[data-node="${node}"]`).value 
                    });
                }
                return;
            }
        });
        
        // PHẦN TÍCH HỢP: Lắng nghe sự kiện THAY ĐỔI (lưu channel ID)
        document.querySelector('.main-grid').addEventListener('change', e => {
            const target = e.target;
            const serverPanel = target.closest('.server-panel');
            // Nếu là ô input channel-input
            if (serverPanel && target.classList.contains('channel-input')) {
                const payload = { server_id: serverPanel.dataset.serverId };
                payload[target.dataset.field] = target.value; // data-field="main_channel_id"
                postData('/api/update_server_field', payload);
            }
        });

        // Xử lý nút THÊM server
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
    # PHẦN TÍCH HỢP: Cần tạo main_bots_info để template có thể lặp qua
    main_bots_count = len([t for t in main_tokens if t.strip()])
    main_bots_info = []
    for i in range(main_bots_count):
        bot_num = i + 1
        main_bots_info.append({"id": bot_num, "name": get_bot_name(f'main_{bot_num}')})
        
    return render_template_string(HTML_TEMPLATE, 
        servers=sorted(servers, key=lambda s: s.get('name', '')),
        main_bots_info=main_bots_info # Truyền thông tin bot cho template
    )

@app.route("/api/add_server", methods=['POST'])
def api_add_server():
    """API để thêm một panel server mới"""
    name = request.json.get('name')
    if not name: 
        return jsonify({'status': 'error', 'message': 'Tên server là bắt buộc.'}), 400
    
    new_server = {
        "id": f"server_{uuid.uuid4().hex}", 
        "name": name
    }
    
    # PHẦN TÍCH HỢP: Thêm các key mặc định cho nhặt thẻ vào server mới
    main_bots_count = len([t for t in main_tokens if t.strip()])
    for i in range(main_bots_count):
        bot_num = i + 1
        new_server[f'auto_grab_enabled_{bot_num}'] = False
        new_server[f'heart_threshold_{bot_num}'] = 50
        new_server[f'max_heart_threshold_{bot_num}'] = 99999
        
    servers.append(new_server)
    save_settings() # Lưu ngay lập tức
    
    return jsonify({'status': 'success', 'message': f'✅ Panel "{name}" đã được thêm.', 'reload': True})

@app.route("/api/delete_server", methods=['POST'])
def api_delete_server():
    """API để xóa một panel server"""
    server_id = request.json.get('server_id')
    servers_count_before = len(servers)
    servers[:] = [s for s in servers if s.get('id') != server_id]
    servers_count_after = len(servers)

    if servers_count_before == servers_count_after:
        return jsonify({'status': 'error', 'message': 'Không tìm thấy panel để xóa.'})

    save_settings()
    return jsonify({'status': 'success', 'message': f'🗑️ Panel đã được xóa.', 'reload': True})

# --- CÁC API MỚI ĐƯỢC TÍCH HỢP ---

def find_server(server_id): 
    """Hàm trợ giúp tìm server theo ID"""
    return next((s for s in servers if s.get('id') == server_id), None)

@app.route("/api/update_server_field", methods=['POST'])
def api_update_server_field():
    """API để cập nhật các trường input (như channel ID)"""
    data = request.json
    server = find_server(data.get('server_id'))
    if not server: 
        return jsonify({'status': 'error', 'message': 'Không tìm thấy server.'}), 404
    
    key_updated = ""
    for key, value in data.items():
        if key != 'server_id':
            server[key] = value
            key_updated = key
            
    return jsonify({'status': 'success', 'message': f'🔧 Đã cập nhật {key_updated} cho {server.get("name")}.'})

@app.route("/api/harvest_toggle", methods=['POST'])
def api_harvest_toggle():
    """API để bật/tắt nhặt thẻ và lưu threshold"""
    data = request.json
    server, node_str = find_server(data.get('server_id')), data.get('node')
    if not server or not node_str: 
        return jsonify({'status': 'error', 'message': 'Yêu cầu không hợp lệ.'}), 400
    
    node = str(node_str) # node là "1", "2", ...
    grab_key = f'auto_grab_enabled_{node}'
    threshold_key = f'heart_threshold_{node}'
    max_threshold_key = f'max_heart_threshold_{node}'
    
    # Bật/Tắt
    server[grab_key] = not server.get(grab_key, False)
    
    # Cập nhật threshold
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
    """API để JS gọi lưu cài đặt"""
    save_settings()
    return jsonify({'status': 'success', 'message': '💾 Đã lưu cài đặt.'})

@app.route("/status")
def status_endpoint():
    """API cung cấp Uptime và danh sách server cho JS"""
    return jsonify({
        'server_start_time': server_start_time,
        'servers': servers # PHẦN TÍCH HỢP: Trả về servers để JS cập nhật UI
    })

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    print("🚀 Integrated Panel Manager - Đang khởi động...", flush=True)
    load_settings() # Tải các panel đã lưu từ JSONBin

    port = int(os.environ.get("PORT", 10000))
    print(f"🌐 Máy chủ web đang chạy tại http://0.0.0.0:{port}", flush=True)
    serve(app, host="0.0.0.0", port=port)
