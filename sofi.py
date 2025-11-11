import discord
from discord.ext import commands
import asyncio
import os
import threading
import re
from flask import Flask, request, render_template_string

# --- CẤU HÌNH WEB SERVER & HTML ---
app = Flask(__name__)

# Biến toàn cục lưu trữ cấu hình số tim
DEFAULT_MIN_HEARTS = {"value": 1} # Mặc định nhặt từ 1 tim trở lên
CHANNEL_CONFIGS = {} # Cấu hình riêng cho từng kênh: {"channel_id": {"name": "Tên Server", "hearts": 5}}


HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sofi Bot Config</title>
    <style>
        body { font-family: sans-serif; background-color: #2c2f33; color: #fff; text-align: center; padding: 20px 50px; }
        .container { max-width: 800px; margin: 0 auto; text-align: left; }
        h1 { color: #7289da; text-align: center; }
        h2 { color: #7289da; border-bottom: 2px solid #7289da; padding-bottom: 5px; margin-top: 40px; }
        input[type="number"], input[type="text"] { padding: 10px; font-size: 16px; width: 100%; box-sizing: border-box; border-radius: 5px; border: none; margin-bottom: 10px; background-color: #40444b; color: #fff; }
        input[type="number"] { width: 120px; text-align: center; }
        button { padding: 10px 20px; font-size: 16px; background-color: #7289da; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 10px; }
        button:hover { background-color: #5b6eae; }
        button.delete { background-color: #f04747; }
        button.delete:hover { background-color: #c03939; }
        .status { text-align: center; margin: 20px 0; font-size: 18px; color: #43b581; font-weight: bold; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { border: 1px solid #40444b; padding: 12px; text-align: left; }
        th { background-color: #36393f; }
        form { background-color: #36393f; padding: 20px; border-radius: 8px; }
        label { display: block; margin: 10px 0 5px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Bảng Điều Khiển Bot Sofi</h1>

        {% if status_message %}
        <div class="status">{{ status_message }}</div>
        {% endif %}

        <h2>Cấu Hình Mặc Định</h2>
        <form method="POST" action="/">
            <input type="hidden" name="action" value="set_default">
            <label for="default_hearts">Số tim mặc định (cho các kênh không có panel):</label>
            <input type="number" name="default_hearts" min="0" value="{{ default_value }}" required>
            <br>
            <button type="submit">Lưu Mặc Định</button>
            <p style="font-size: 14px; color: #999;">Giá trị hiện tại: <b>{{ default_value }}</b> tim</p>
        </form>
        
        <h2>Các Panel Đã Cấu Hình</h2>
        {% if configs %}
        <table>
            <thead>
                <tr>
                    <th>Tên Server</th>
                    <th>ID Kênh</th>
                    <th>Nhặt từ (tim)</th>
                    <th>Hành động</th>
                </tr>
            </thead>
            <tbody>
                {% for channel_id, config in configs.items() %}
                <tr>
                    <td>{{ config.name }}</td>
                    <td>{{ channel_id }}</td>
                    <td><b>{{ config.hearts }}</b></td>
                    <td>
                        <form method="POST" action="/" style="padding: 0; background: none;">
                            <input type="hidden" name="action" value="delete_config">
                            <input type="hidden" name="channel_id" value="{{ channel_id }}">
                            <button type="submit" class="delete">Xóa</button>
                        </form>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        {% else %}
        <p>Chưa có panel nào được cấu hình. Sử dụng biểu mẫu bên dưới để thêm.</p>
        {% endif %}

        <h2>Thêm / Cập Nhật Panel</h2>
        <form method="POST" action="/">
            <input type="hidden" name="action" value="add_config">
            
            <label for="server_name">Tên Server (Để bạn dễ nhớ):</label>
            <input type="text" name="server_name" placeholder="Ví dụ: Server A, Kênh farm B..." required>

            <label for="channel_id">ID Kênh (Channel ID):</label>
            <input type="text" name="channel_id" placeholder="Nhập ID của kênh cần nhặt thẻ" required>
            
            <label for="min_hearts">Số tim tối thiểu để nhặt:</label>
            <input type="number" name="min_hearts" min="0" value="1" required>
            
            <br>
            <button type="submit">Lưu Panel</button>
        </form>

    </div>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    status_message = None
    if request.method == "POST":
        action = request.form.get("action")
        
        try:
            if action == "set_default":
                new_val = int(request.form.get("default_hearts"))
                DEFAULT_MIN_HEARTS["value"] = new_val
                status_message = f"✅ Đã lưu! Mặc định nhặt từ {new_val} tim."
                print(f"🌐 [WEB] Đã cập nhật DEFAULT_HEARTS lên: {new_val}")
            
            elif action == "add_config":
                server_name = request.form.get("server_name", "Không Tên")
                channel_id = request.form.get("channel_id")
                min_hearts = int(request.form.get("min_hearts"))
                
                if not channel_id or not channel_id.isdigit():
                     status_message = "❌ Lỗi: ID Kênh phải là số và không được để trống."
                else:
                    CHANNEL_CONFIGS[channel_id] = {"name": server_name, "hearts": min_hearts}
                    status_message = f"✅ Đã lưu Panel cho '{server_name}' (ID: {channel_id}) với {min_hearts} tim."
                    print(f"🌐 [WEB] Đã thêm/cập nhật Panel: {channel_id} - {server_name} - {min_hearts} tim")
            
            elif action == "delete_config":
                channel_id_to_delete = request.form.get("channel_id")
                if channel_id_to_delete in CHANNEL_CONFIGS:
                    deleted_name = CHANNEL_CONFIGS.pop(channel_id_to_delete)["name"]
                    status_message = f"✅ Đã xóa Panel '{deleted_name}' (ID: {channel_id_to_delete})."
                    print(f"🌐 [WEB] Đã xóa Panel: {channel_id_to_delete}")
                
        except (ValueError, TypeError):
            status_message = "❌ Lỗi: Vui lòng nhập số hợp lệ cho ID Kênh và Số Tim."
        except Exception as e:
            status_message = f"❌ Lỗi máy chủ: {e}"

    return render_template_string(
        HTML_TEMPLATE, 
        default_value=DEFAULT_MIN_HEARTS["value"], 
        configs=CHANNEL_CONFIGS, 
        status_message=status_message
    )

def run_flask():
    # Chạy Flask trên port 10000 (thường dùng cho Render) hoặc port được chỉ định
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, use_reloader=False)

def keep_alive():
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

# --- CẤU HÌNH BOT ---
accounts = [
    {"token": os.getenv("TOKEN1"), "channel_id": os.getenv("CHANNEL_ID")}, # ACC CHÍNH
    {"token": os.getenv("TOKEN2"), "channel_id": os.getenv("CHANNEL_ID")}, # Acc phụ
    {"token": os.getenv("TOKEN3"), "channel_id": os.getenv("CHANNEL_ID")}, # Acc phụ
]

SOFI_ID = 853629533855809596
MAIN_ACC_GRAB_DELAY = 1.5 # Giây
running_bots = []

# --- BOT LOGIC ---
def get_heart_count(button):
    text = button.label
    if not text: return 0
    numbers = re.findall(r'\d+', str(text))
    return int("".join(numbers)) if numbers else 0

async def click_and_message(message, delay, bot, account_info, is_main_acc):
    if not is_main_acc: return
    await asyncio.sleep(delay)
    try:
        # print(f"[{account_info['channel_id']}] → 🔎 {bot.user.name} đang soi tim...")
        fetched_message = None
        found_buttons = []
        for _ in range(5):
            try:
                fetched_message = await message.channel.fetch_message(message.id)
                found_buttons = [c for row in fetched_message.components for c in row.children if isinstance(c, discord.Button)]
                if found_buttons: break
            except: pass
            await asyncio.sleep(1)

        if found_buttons:
            # === LOGIC NÂNG CẤP: LẤY CẤU HÌNH THEO KÊNH ===
            current_channel_id = str(message.channel.id)
            config = CHANNEL_CONFIGS.get(current_channel_id)
            
            if config:
                min_hearts_needed = config["hearts"]
                config_name = f"'{config['name']}'"
            else:
                min_hearts_needed = DEFAULT_MIN_HEARTS["value"]
                config_name = "Mặc Định"
            # ============================================

            best_button = None
            max_hearts = -1

            print(f"--- 📊 Phân tích thẻ (Kênh: {current_channel_id}, Cấu hình: {config_name}, Yêu cầu: >={min_hearts_needed} tim) ---")
            for idx, button in enumerate(found_buttons):
                hearts = get_heart_count(button)
                print(f"   ➤ Nút {idx+1}: {hearts} tim")
                if hearts >= min_hearts_needed and hearts > max_hearts:
                    max_hearts = hearts
                    best_button = button
                elif hearts >= min_hearts_needed and hearts == max_hearts and best_button is None:
                     best_button = button
            
            if best_button:
                await asyncio.sleep(0.5)
                await best_button.click()
                print(f"[{account_info['channel_id']}] → 🏆 ĐÃ CLICK nút {max_hearts} tim!")
            else:
                print(f"[{account_info['channel_id']}] → ⚠️ Không có thẻ nào đủ {min_hearts_needed} tim để nhặt (theo cấu hình {config_name}).")
            print("------------------------------------------------")

    except Exception as e:
        print(f"⚠️ Lỗi click: {e}")

async def run_account(account, idx, startup_delay):
    is_main = (idx == 0)
    if startup_delay > 0: await asyncio.sleep(startup_delay)
    bot = commands.Bot(command_prefix="!", self_bot=True)

    @bot.event
    async def on_ready():
        print(f"[{'ACC CHÍNH 👑' if is_main else 'Acc phụ 🤖'}] Đã đăng nhập: {bot.user}")
        running_bots.append(bot)

    @bot.event
    async def on_message(message):
        # *** LƯU Ý: Phần `account["channel_id"]` trong `accounts` giờ chỉ dùng để auto-drop "sd"
        # Logic nhặt thẻ (click_and_message) sẽ tự động áp dụng cho BẤT KỲ KÊNH NÀO
        # mà bot chính (is_main) nhìn thấy tin nhắn của Sofi.
        
        if message.author.id == SOFI_ID: # Bot sẽ phản ứng ở mọi kênh nó thấy
            if is_main and ("dropping" in message.content.lower() or "thả" in message.content.lower()):
                print(f"🎯 {bot.user.name} phát hiện drop trong kênh {message.channel.id}! Đang soi...")
                # Logic mới sẽ tự kiểm tra xem kênh này có panel không
                asyncio.create_task(click_and_message(message, MAIN_ACC_GRAB_DELAY, bot, account, True))

    try: await bot.start(account["token"])
    except Exception as e: print(f"❌ Lỗi login {account['token'][:5]}...: {e}")

async def drop_loop():
    while len(running_bots) < len([a for a in accounts if a.get("token")]): await asyncio.sleep(5)
    print("\n🚀 AUTO DROP BẮT ĐẦU!\n")
    i = 0
    while True:
        try:
            # Vẫn loop qua các channel_id trong cấu hình `accounts` để gửi 'sd'
            bot = running_bots[i % len(running_bots)]
            acc = accounts[i % len(accounts)]
            ch_id = acc.get("channel_id")
            
            if not ch_id:
                print(f"⚠️ Bỏ qua drop cho {bot.user.name} vì không có CHANNEL_ID trong cấu hình.")
                i += 1
                await asyncio.sleep(60) # Chờ 1 phút rồi thử acc tiếp
                continue
                
            ch = bot.get_channel(int(ch_id))
            if ch:
                await ch.send("sd")
                print(f"💬 {bot.user.name} gửi 'sd' đến kênh {ch_id}")
            else:
                print(f"⚠️ {bot.user.name} không tìm thấy kênh {ch_id} để gửi 'sd'")
                
            i += 1
            await asyncio.sleep(485) # Thời gian nghỉ giữa các lần drop
        except Exception as e:
            print(f"Lỗi trong drop_loop: {e}")
            await asyncio.sleep(60)

async def main():
    keep_alive() # Khởi động web server
    tasks = []
    active_accs = [acc for acc in accounts if acc.get("token")]
    for i, acc in enumerate(active_accs):
        tasks.append(run_account(acc, i, i * 5))
    if tasks:
        tasks.append(drop_loop())
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
