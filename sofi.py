import discord
from discord.ext import commands
import asyncio
import os
import threading
from keep_alive import keep_alive
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()

# --- Cấu hình ---
# CHỈ CẦN 1 TOKEN CHO ACC CHÍNH
TOKEN = os.getenv("TOKEN_MAIN")
CHANNEL_ID = os.getenv("CHANNEL_ID")

# ID bot Sofi
SOFI_ID = 853629533855809596

# --- Khởi tạo Bot với Intents ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", self_bot=True, intents=intents)

# --- Hàm xử lý chính ---
async def click_hottest_card(message, delay):
    """Đợi và click vào thẻ có số tim CAO NHẤT."""
    await asyncio.sleep(delay)
    print(f"🔎 {bot.user.name} đang soi thẻ hot...")

    try:
        # Thử fetch tin nhắn vài lần
        fetched_message = None
        found_buttons = []
        for i in range(5):
            try:
                fetched_message = await message.channel.fetch_message(message.id)
                found_buttons = []
                if fetched_message.components:
                    for action_row in fetched_message.components:
                        for component in action_row.children:
                            if isinstance(component, discord.Button):
                                found_buttons.append(component)
                
                if len(found_buttons) >= 3:
                    break
            except:
                 pass
            await asyncio.sleep(1.5)

        if len(found_buttons) >= 3:
            # --- PHÂN TÍCH TÌM THẺ HOT NHẤT ---
            best_button = None
            max_hearts = -1
            
            print(f"📊 Phân tích {len(found_buttons)} thẻ:")
            for i, button in enumerate(found_buttons):
                heart_count = 0
                if button.label and button.label.isdigit():
                     heart_count = int(button.label)
                
                print(f"   → Vị trí {i+1}: {heart_count} tim")

                if heart_count > max_hearts:
                    max_hearts = heart_count
                    best_button = button
                elif heart_count == max_hearts and best_button is None:
                     best_button = button

            if best_button:
                await asyncio.sleep(0.5)
                await best_button.click()
                print(f"🎯 {bot.user.name} ĐÃ CLICK thẻ vị trí {found_buttons.index(best_button)+1} ({max_hearts} tim)!")
            else:
                 print(f"⚠️ Không tìm thấy thẻ nào khả thi.")

        else:
             print(f"❌ Không tìm thấy đủ 3 nút bấm.")

    except Exception as e:
        print(f"⚠️ Lỗi khi săn thẻ: {e}")

@bot.event
async def on_ready():
    print(f"✅ Acc chính {bot.user} đã sẵn sàng săn hàng hot!")

@bot.event
async def on_message(message):
    if message.author.id == SOFI_ID and str(message.channel.id) == CHANNEL_ID:
        content = message.content.lower()
        if "dropping" in content or "thả" in content:
            print(f"🔥 Phát hiện drop! Đang đợi 4s để mọi người thả tim...")
            asyncio.create_task(click_hottest_card(message, delay=4.0))

async def main_drop_loop():
    await bot.wait_until_ready()
    channel = bot.get_channel(int(CHANNEL_ID))
    while not bot.is_closed():
        try:
            if channel:
                await channel.send("sd")
                print(f"⏰ {bot.user.name} đã gửi lệnh 'sd'")
            await asyncio.sleep(250) 
        except Exception as e:
            print(f"Lỗi vòng lặp drop: {e}")
            await asyncio.sleep(60)

async def main():
    # Chạy server keep_alive (tùy chọn)
    threading.Thread(target=keep_alive, daemon=True).start()
    
    # Chạy song song bot và vòng lặp drop
    await asyncio.gather(
        bot.start(TOKEN),
        main_drop_loop()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Đã dừng bot.")