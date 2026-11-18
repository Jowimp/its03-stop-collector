import asyncio
import aiohttp
import json
import pandas as pd
from datetime import datetime
from pathlib import Path

# ================= НАСТРОЙКИ =================
# Сюда вставьте ID остановок, которые вы собрали на Этапе 1
STOP_IDS = [
    "1543346528",  # Площадь Советов (пример)
    "1543346495",  # Элеватор (пример)
    # ... добавьте остальные ID
]

# Внутренний API Яндекс.Карт (тот же, что использует браузер)
API_URL = "https://yandex.ru/maps/api/masstransit/getStopInfo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://yandex.ru/maps/",
    "Accept": "application/json",
}

CSV_PATH = Path("all_stops_schedule.csv")
FIELDNAMES = ["Время_замера", "Остановка_ID", "Название_остановки", "Маршрут", "Направление", "Время_прибытия"]
# =============================================

async def fetch_stop(session, stop_id):
    """Асинхронно запрашивает данные по одной остановке."""
    params = {"id": stop_id, "lang": "ru_RU"}
    try:
        async with session.get(API_URL, params=params, headers=HEADERS) as response:
            if response.status == 200:
                data = await response.json()
                return stop_id, data
            else:
                print(f"[{stop_id}] HTTP ошибка: {response.status}")
                return stop_id, None
    except Exception as e:
        print(f"[{stop_id}] Ошибка запроса: {e}")
        return stop_id, None

def parse_stop_data(stop_id, data, time_str):
    """Извлекает расписание из JSON-ответа (та же логика, что и в браузере)."""
    rows = []
    if not data or "data" not in data:
        return rows
    
    stop_info = data["data"]
    stop_name = stop_info.get("name", "Неизвестно")
    
    for transport in stop_info.get("transports", []):
        route_name = transport.get("name", "?")
        for thread in transport.get("threads", []):
            stops = thread.get("EssentialStops", [])
            direction = stops[-1].get("name", "Неизвестно") if stops else ""
            
            events = thread.get("BriefSchedule", {}).get("Events", [])
            for event in events:
                scheduled = event.get("Scheduled", {})
                arrival_time = scheduled.get("text")
                if arrival_time:
                    rows.append({
                        "Время_замера": time_str,
                        "Остановка_ID": stop_id,
                        "Название_остановки": stop_name,
                        "Маршрут": str(route_name),
                        "Направление": direction,
                        "Время_прибытия": arrival_time
                    })
    return rows

async def main():
    print(f"Запуск асинхронного опроса {len(STOP_IDS)} остановок...")
    
    # Используем aiohttp для параллельных запросов
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_stop(session, sid) for sid in STOP_IDS]
        results = await asyncio.gather(*tasks)

    now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
    all_rows = []
    
    for stop_id, data in results:
        rows = parse_stop_data(stop_id, data, now_str)
        all_rows.extend(rows)

    if not all_rows:
        print("Не удалось собрать данные. Проверьте ID остановок.")
        return

    # Сохраняем в CSV и Excel
    df = pd.DataFrame(all_rows)
    df.to_csv(CSV_PATH, index=False, encoding="utf-8-sig", sep=";")
    
    xlsx_path = CSV_PATH.with_suffix(".xlsx")
    df.to_excel(xlsx_path, index=False, engine="openpyxl")
    
    print(f"✅ Собрано {len(all_rows)} записей с {len(set(r['Остановка_ID'] for r in all_rows))} остановок.")
    print(f"Файл сохранён: {xlsx_path.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())