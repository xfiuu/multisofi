import discord
from discord.ext import commands
import asyncio
import os
import threading
import re
from flask import Flask, request, render_template_string

# --- CẤU HÌNH WEB SERVER & HTML ---
app = Flask(__name__)

# Biến toàn cục lưu trữ cấu hình số tim tối thiểu
MIN_HEARTS_CONFIG = {"value": 1} # Mặc định nhặt từ 1 tim trở lên

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Sofi Bot Config</title>
    <style>
        body { font-family: sans-serif; background-color: #2c2f33; color: #fff; text-align: center; padding: 50px; }
        h1 { color: #7289da; }
        input[type="number"] { padding: 10px; font-size: 20px; width: 100px; text-align: center; border-radius: 5px; border: none; }
        button { padding: 10px 20px; font-size: 20px; background-color: #7289da; color: white; border: none; border-radius: 5px; cursor: pointer; margin-top: 20px; }
        button:hover { background-color: #5b6eae; }
        .status { margin-top: 30px; font-size: 18px; color: #43b581; }
    </style>
</head>
<body>
    <h1>Cấu Hình Bot Sofi</h1>
    <p>Nhập số tim tối thiểu để bot bắt đầu nhặt:</p>
    <form method="POST" action="/">
        <input type="number" name="min_hearts" min="0" value="{{ current_value }}" required>
        <br>
        <button type="submit">Lưu Cài Đặt</button>
    </form>
    {% if saved_value %}
    <div class="status">✅ Đã lưu! Bot chỉ nhặt thẻ có từ <b>{{ saved_value }}</b> tim trở lên.</div>
    {% endif %}
    <p>Giá trị hiện tại: <b>{{ current_value }}</b></p>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    saved_value = None
    if request.method == "POST":
        try:
            new_val = int(request.form.get("min_hearts"))
            MIN_HEARTS_CONFIG["value"] = new_val
            saved_value = new_val
            print(f"🌐 [WEB] Đã cập nhật MIN_HEARTS lên: {new_val}")
        except (ValueError, TypeError):
            pass
    return render_template_string(HTML_TEMPLATE, current_value=MIN_HEARTS_CONFIG["value"], saved_value=saved_value)

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
            min_hearts_needed = MIN_HEARTS_CONFIG["value"]
            best_button = None
            max_hearts = -1

            print(f"--- 📊 Phân tích thẻ (Yêu cầu: >={min_hearts_needed} tim) ---")
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
                print(f"[{account_info['channel_id']}] → ⚠️ Không có thẻ nào đủ {min_hearts_needed} tim để nhặt.")
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
        if message.author.id == SOFI_ID and str(message.channel.id) == account["channel_id"]:
            if is_main and ("dropping" in message.content.lower() or "thả" in message.content.lower()):
                print(f"🎯 {bot.user.name} phát hiện drop! Đang soi...")
                asyncio.create_task(click_and_message(message, MAIN_ACC_GRAB_DELAY, bot, account, True))

    try: await bot.start(account["token"])
    except Exception as e: print(f"❌ Lỗi login {account['token'][:5]}...: {e}")

async def drop_loop():
    while len(running_bots) < len([a for a in accounts if a.get("token")]): await asyncio.sleep(5)
    print("\n🚀 AUTO DROP BẮT ĐẦU!\n")
    i = 0
    while True:
        try:
            bot = running_bots[i % len(running_bots)]
            acc = accounts[i % len(accounts)]
            ch = bot.get_channel(int(acc["channel_id"]))
            if ch:
                await ch.send("sd")
                print(f"💬 {bot.user.name} gửi 'sd'")
            i += 1
            await asyncio.sleep(20)
        except: await asyncio.sleep(60)

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
