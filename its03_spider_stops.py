import asyncio
import aiohttp
import json
from pathlib import Path

# ================= НАСТРОЙКИ =================
# Базовый URL API (как в ваших запросах к its03)
API_URL = "http://its03.ru/php/apiRequest.php/getStationForecasts.php"
# Если для listLines/stopList используется другой эндпоинт, укажите его здесь
LINES_API_URL = "http://its03.ru/php/apiRequest.php/getLines.php" 
STOPS_API_URL = "http://its03.ru/php/apiRequest.php/getStops.php"

OUTPUT_FILE = Path("its03_all_stops.json")
DELAY = 1.0  # Задержка между запросами (сек)
# =============================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "text/plain;charset=UTF-8",
    "Origin": "http://its03.ru",
    "Referer": "http://its03.ru/"
}

async def fetch_lines(session):
    """Получает список всех маршрутов города."""
    # В реальном API its03 структура запроса может отличаться,
    # но по аналогии с getStationForecasts это POST с JSON-payload.
    payload = {
        "t": "11111111-50b3-4fec-b922-8a50a1d38366",
        "ct": 26,
        "cd": "getLines.php",
        "data": {"wuid": 804427263646, "sid": 3},
        "w": -1
    }
    try:
        async with session.post(LINES_API_URL, data=json.dumps(payload), headers=HEADERS, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                # Предполагаем, что маршруты лежат в ключе "data" или "lines"
                lines = data.get("data") or data.get("lines") or []
                return lines
            else:
                print(f"[!] Ошибка получения маршрутов: HTTP {response.status}")
                return []
    except Exception as e:
        print(f"[!] Ошибка запроса маршрутов: {e}")
        return []

async def fetch_stops_for_line(session, line_num):
    """Получает список остановок для конкретного маршрута."""
    payload = {
        "t": "11111111-50b3-4fec-b922-8a50a1d38366",
        "ct": 26,
        "cd": "getStops.php",
        "data": {"line_num": line_num, "wuid": 804427263646, "sid": 3},
        "w": -1
    }
    try:
        async with session.post(STOPS_API_URL, data=json.dumps(payload), headers=HEADERS, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                stops = data.get("data", {}).get("stops") or data.get("stops") or []
                return stops
            else:
                return []
    except Exception:
        return []

async def main():
    print("Запуск сбора всех остановок через маршруты...")
    all_stops = {}  # Словарь для хранения уникальных остановок: {id: {"name": ..., "lat": ..., "lon": ...}}

    async with aiohttp.ClientSession() as session:
        lines = await fetch_lines(session)
        if not lines:
            print("Не удалось получить список маршрутов. Проверьте эндпоинт LINES_API_URL.")
            return

        print(f"Найдено маршрутов: {len(lines)}")

        for i, line in enumerate(lines, 1):
            line_num = line.get("number") or line.get("name")
            if not line_num:
                continue

            print(f"[{i}/{len(lines)}] Опрос маршрута {line_num}...")
            stops = await fetch_stops_for_line(session, line_num)

            for stop in stops:
                stop_id = stop.get("id")
                if stop_id and stop_id not in all_stops:
                    all_stops[stop_id] = {
                        "id": stop_id,
                        "name": stop.get("name", "Без названия"),
                        "lat": stop.get("lat"),
                        "lon": stop.get("lon"),
                        "stop_type": stop.get("stop_type")
                    }

            await asyncio.sleep(DELAY)  # Пауза, чтобы не нагружать сервер

    # Сохраняем результат
    result_list = list(all_stops.values())
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово! Собрано уникальных остановок: {len(result_list)}")
    print(f"Файл сохранен: {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())