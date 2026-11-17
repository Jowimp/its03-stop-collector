import asyncio
import csv
import threading
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright
import pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment

# ================= НАСТРОЙКИ =================
CSV_PATH = Path("Яндекс_расписание.csv")
XLSX_PATH = Path("Яндекс_расписание.xlsx") 
FIELDNAMES = ["Время_замера", "Остановка", "Маршрут", "Направление", "Время_прибытия"]
STOP_FLAG = threading.Event()
latest_payload = {"data": None}
seen_schedules = set()

def csv_writer_loop():
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES, delimiter=';')
        writer.writeheader()
        
        while not STOP_FLAG.is_set():
            if STOP_FLAG.wait(timeout=5): # Опрос раз в 5 секунд
                break
            
            data = latest_payload["data"]
            if not data or "data" not in data:
                continue

            now_dt = datetime.now()
            time_str = now_dt.strftime("%d.%m.%Y %H:%M:%S")
            
            stop_name = data["data"].get("name", "Неизвестно")
            transports = data["data"].get("transports", [])
            
            new_records_found = False

            for transport in transports:
                route_name = transport.get("name", "?")
                
                for thread in transport.get("threads", []):
                    stops = thread.get("EssentialStops", [])
                    direction = stops[-1].get("name", "Неизвестно") if stops else ""
                    
                    events = thread.get("BriefSchedule", {}).get("Events", [])
                    for event in events:
                        scheduled = event.get("Scheduled", {})
                        arrival_time = scheduled.get("text")
                        
                        if arrival_time:
                            unique_key = (stop_name, route_name, direction, arrival_time)
                            
                            if unique_key not in seen_schedules:
                                row = {
                                    "Время_замера": time_str,
                                    "Остановка": stop_name,
                                    "Маршрут": str(route_name),
                                    "Направление": direction,
                                    "Время_прибытия": arrival_time
                                }
                                writer.writerow(row)
                                seen_schedules.add(unique_key)
                                new_records_found = True
            
            if new_records_found:
                f.flush()
                print(f"[{time_str}] Данные обновлены.")
            else:
                print(f"[{time_str}] Новых рейсов нет.")

async def listen_network(context):
    async def handle_response(response):
        if "getStopInfo" in response.url or "masstransit" in response.url:
            try:
                body = await response.json()
                if body and "data" in body and "transports" in body["data"]:
                    latest_payload["data"] = body
            except Exception:
                pass
    context.on("response", handle_response)

def create_beautiful_excel():
    """Конвертирует CSV в красивый Excel-файл с правильной кодировкой"""
    if not CSV_PATH.exists():
        return

    try:
        # Читаем CSV с принудительной правильной кодировкой
        df = pd.read_csv(CSV_PATH, sep=';', encoding='utf-8-sig')
        
        # Сортируем по времени прибытия для красоты
        if 'Время_прибытия' in df.columns:
            df = df.sort_values(by='Время_прибытия')

        # Сохраняем в Excel
        df.to_excel(XLSX_PATH, index=False, engine='openpyxl')

        # --- Делаем файл красивым ---
        wb = load_workbook(XLSX_PATH)
        ws = wb.active

        # Красим шапку
        header_fill = PatternFill(start_color="4F81BD", end_color="4F81BD", fill_type="solid")
        header_font = Font(bold=True, color="FFFFFF")
        
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center", vertical="center")

        # Автоматически расширяем колонки (решает проблему с ###)
        for col in ws.columns:
            max_length = 0
            column_letter = col[0].column_letter
            for cell in col:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            # Добавляем немного места (например, +3 символа)
            ws.column_dimensions[column_letter].width = max_length + 3

        wb.save(XLSX_PATH)
        print(f"\n✅ Готово! Красивый Excel-файл сохранен: {XLSX_PATH.resolve()}")
        
    except Exception as e:
        print(f"\nОшибка при создании Excel: {e}")

async def main():
    writer_thread = threading.Thread(target=csv_writer_loop, daemon=True)
    writer_thread.start()

    def wait_for_enter():
        input("") 
        STOP_FLAG.set()
        print("\n[!] Остановка сбора. Создаю Excel-файл...")

    threading.Thread(target=wait_for_enter, daemon=True).start()

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chrome-profile-yandex",
            headless=False,
            channel="chrome",
        )
        await listen_network(context)
        page = await context.new_page()
        await page.goto("https://yandex.ru/maps/")

        print("=" * 60)
        print("1. В Chrome найдите остановку и кликните на неё.")
        print("2. Данные собираются каждые 3 минуты.")
        print("НЕ НАЖИМАЙТЕ ENTER, пока не захотите остановить скрипт.")
        print("=" * 60)

        try:
            while not STOP_FLAG.is_set():
                await asyncio.sleep(1)
        finally:
            await context.close()
            writer_thread.join(timeout=5)
            create_beautiful_excel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        STOP_FLAG.set()
