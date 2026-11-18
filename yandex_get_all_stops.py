import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright

# ================= НАСТРОЙКИ =================
OUTPUT_FILE = Path("yandex_all_stops.json")
# Ссылка на карту Улан-Удэ с включенным слоем транспорта (пример)
# Можно заменить на любой другой город
MAP_URL = "https://yandex.ru/maps/198/ulan-ude/transport/"
# =============================================

async def main():
    print("Запуск сбора всех остановок с Яндекс.Карт...")
    print("Открывается Chrome...")

    async with async_playwright() as p:
        # Запускаем видимый Chrome (чтобы Яндекс не блокировал)
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./chrome-profile-stops",
            headless=False,
            channel="chrome",
        )
        page = await context.new_page()

        # Сюда будем складывать перехваченные данные
        captured_payloads = []

        async def handle_response(response):
            # Ловим запросы, связанные с транспортом/остановками
            url = response.url
            if "masstransit" in url or "getStops" in url or "transport" in url:
                try:
                    body = await response.json()
                    if body:
                        captured_payloads.append(body)
                        print(f"[network] Перехвачен ответ: {url[:80]}...")
                except Exception:
                    pass

        context.on("response", handle_response)

        # Открываем карту с транспортом
        await page.goto(MAP_URL)

        print("=" * 60)
        print("1. Дождитесь загрузки карты и слоя с остановками.")
        print("2. Если нужно, немного подвигайте карту (или измените масштаб),")
        print("   чтобы Яндекс подгрузил все остановки в видимой области.")
        print("3. Скрипт автоматически сохранит все перехваченные ID.")
        print("4. Когда закончите, нажмите Enter в этом терминале.")
        print("=" * 60)

        # Ждем, пока пользователь не нажмет Enter
        await asyncio.get_event_loop().run_in_executor(None, input, "")

        await context.close()

    # --- Обработка собранных данных ---
    all_stops = {}  # Словарь: id -> name

    # Рекурсивная функция для поиска остановок в любом месте JSON
    def find_stops(obj):
        if isinstance(obj, dict):
            # Признаки остановки: есть id и name (или title)
            if "id" in obj and ("name" in obj or "title" in obj):
                stop_id = obj.get("id")
                stop_name = obj.get("name") or obj.get("title")
                # Фильтруем по типу, если есть
                if stop_id and stop_name:
                    all_stops[str(stop_id)] = str(stop_name)
            for v in obj.values():
                find_stops(v)
        elif isinstance(obj, list):
            for item in obj:
                find_stops(item)

    for payload in captured_payloads:
        find_stops(payload)

    if not all_stops:
        print("\n❌ Не удалось найти остановки. Попробуйте подвигать карту и запустить снова.")
        return

    # Сохраняем результат
    result_list = [{"id": sid, "name": name} for sid, name in all_stops.items()]
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result_list, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Готово! Собрано уникальных остановок: {len(result_list)}")
    print(f"Файл сохранен: {OUTPUT_FILE.resolve()}")
    print("Вы можете использовать эти ID в скрипте сбора расписания.")

if __name__ == "__main__":
    asyncio.run(main())