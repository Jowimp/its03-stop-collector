import asyncio
import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright

CSV_PATH = Path("Отчет_автобусы.csv")
# Понятные русские заголовки
FIELDNAMES = ["Дата", "Время", "Маршрут", "Мин_до_прибытия", "Сек_до_прибытия", "Борт_ТС"]
STOP_FLAG = threading.Event()
latest_payload = {"data": None}

def csv_writer_loop():
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';') # Используем ; для русского Excel
        writer.writeheader()
        last_state = {}
        last_log_time = 0

        while not STOP_FLAG.is_set():
            if STOP_FLAG.wait(timeout=5):
                break
            
            data = latest_payload["data"]
            if not data:
                continue

            results = []
            def walk(obj):
                if isinstance(obj, dict):
                    route = obj.get("routeNumber") or obj.get("routeShortName")
                    
                    if route:
                        time_sec = obj.get("arrivalTimeInSec")
                        vehicle = obj.get("vehicleTagIds") or obj.get("deviceCode") or "?"
                        
                        if time_sec is not None:
                            # Запоминаем маршрут, время и БОРТ (номер ТС)
                            results.append({
                                "route": str(route), 
                                "time": int(time_sec),
                                "vehicle": str(vehicle)
                            })
                            return
                    
                    for v in obj.values(): walk(v)
                elif isinstance(obj, list):
                    for item in obj: walk(item)
            
            walk(data)

            # Проверяем, изменились ли данные (сравниваем и маршрут, и время, и борт)
            current_state = {f"{item['route']}_{item['vehicle']}": item["time"] for item in results}
            
            if current_state != last_state or (time.time() - last_log_time) >= 60:
                now_dt = datetime.now()
                date_str = now_dt.strftime("%d.%m.%Y")
                time_str = now_dt.strftime("%H:%M:%S")
                
                if results:
                    for item in results:
                        mins = item["time"] // 60
                        secs = item["time"]
                            
                        row = {
                            "Дата": date_str,
                            "Время": time_str,
                            "Маршрут": item["route"],
                            "Мин_до_прибытия": mins,
                            "Сек_до_прибытия": secs,
                            "Борт_ТС": item["vehicle"]
                        }
                        writer.writerow(row)
                        print(f"[{time_str}] Маршрут {item['route']} (борт {item['vehicle']}) — через {mins} мин.")
                    f.flush()
                
                last_state = current_state
                last_log_time = time.time()

async def listen_network(context):
    async def handle_response(response):
        if "Forecast" in response.url or "apiRequest" in response.url:
            try:
                body = await response.json()
                if body:
                    latest_payload["data"] = body
            except Exception:
                pass
    context.on("response", handle_response)

async def main():
    writer_thread = threading.Thread(target=csv_writer_loop, daemon=True)
    writer_thread.start()

    def wait_for_enter():
        input("") 
        STOP_FLAG.set()
        print("\n[!] Остановка сбора...")

    threading.Thread(target=wait_for_enter, daemon=True).start()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chrome-profile-its",
            headless=False,
            channel="chrome",
        )
        await listen_network(context)
        
        page = await context.new_page()
        await page.goto("http://its03.ru/")

        print("=" * 60)
        print("1. Выберите остановку в Chrome.")
        print("2. Скрипт начнет собирать данные в файл 'Отчет_автобусы.csv'.")
        print("НЕ НАЖИМАЙТЕ ENTER, пока не захотите остановить скрипт.")
        print("=" * 60)

        try:
            while not STOP_FLAG.is_set():
                await asyncio.sleep(1)
        finally:
            await context.close()
            writer_thread.join(timeout=5)
            print(f"\nГотово. Данные сохранены в {CSV_PATH.resolve()}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        STOP_FLAG.set()