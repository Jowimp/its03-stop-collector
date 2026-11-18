import asyncio
import aiohttp
import json
from pathlib import Path
from collections import deque

# ================= НАСТРОЙКИ =================
# Стартовая остановка (например, "Площадь Советов" в Улан-Удэ)
START_STOP_ID = "1543346528" 
# Файл, куда сохраним результат
OUTPUT_FILE = Path("all_stops_ids.txt")
# Задержка между запросами (секунды), чтобы не злить Яндекс
DELAY = 1.5 
# =============================================

API_URL = "https://yandex.ru/maps/api/masstransit/getStopInfo"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://yandex.ru/maps/",
    "Accept": "application/json",
}

async def fetch_stop(session, stop_id):
    """Запрашивает данные по одной остановке."""
    params = {"id": stop_id, "lang": "ru_RU"}
    try:
        async with session.get(API_URL, params=params, headers=HEADERS, timeout=10) as response:
            if response.status == 200:
                return await response.json()
    except Exception as e:
        print(f"[!] Ошибка при запросе {stop_id}: {e}")
    return None

def extract_stop_ids(data):
    """Извлекает все ID остановок (EssentialStops) из ответа API."""
    found_stops = set()
    if not data or "data" not in data:
        return found_stops
    
    transports = data["data"].get("transports", [])
    for transport in transports:
        for thread in transport.get("threads", []):
            for stop in thread.get("EssentialStops", []):
                stop_id = stop.get("id")
                if stop_id:
                    found_stops.add(str(stop_id))
    return found_stops

async def main():
    print(f"Запуск паука со стартовой остановки: {START_STOP_ID}")
    
    # Очередь на посещение и множество уже посещенных остановок
    queue = deque([START_STOP_ID])
    visited = {START_STOP_ID}
    all_collected = {START_STOP_ID} # Сюда собираем уникальные ID

    async with aiohttp.ClientSession() as session:
        while queue:
            current_id = queue.popleft()
            print(f"[{len(visited)}] Опрос остановки: {current_id}...")
            
            data = await fetch_stop(session, current_id)
            if not data:
                continue

            # Извлекаем новые ID остановок
            new_ids = extract_stop_ids(data)
            
            # Добавляем в очередь те, которые еще не посещали
            for nid in new_ids:
                if nid not in visited:
                    visited.add(nid)
                    queue.append(nid)
                    all_collected.add(nid)

            # Сохраняем прогресс на диск после каждой итерации
            with OUTPUT_FILE.open("w", encoding="utf-8") as f:
                for sid in sorted(all_collected):
                    f.write(f"{sid}\n")
            
            # Пауза, чтобы не превышать лимиты Яндекса
            await asyncio.sleep(DELAY)

    print(f"\n✅ Готово! Собрано {len(all_collected)} уникальных остановок.")
    print(f"Список сохранен в файл: {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())