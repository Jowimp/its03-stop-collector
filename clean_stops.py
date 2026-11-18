import json
import re
from pathlib import Path

INPUT_FILE = Path("yandex_all_stops.json")
OUTPUT_FILE = Path("clean_stops_ids.json")

def is_valid_stop_id(stop_id):
    # ID должен быть либо числом, либо строкой, начинающейся с "stop__" и цифр
    if str(stop_id).isdigit():
        return True
    if re.match(r"^stop__\d+$", str(stop_id)):
        return True
    return False

def main():
    if not INPUT_FILE.exists():
        print("Файл yandex_all_stops.json не найден.")
        return

    with INPUT_FILE.open("r", encoding="utf-8") as f:
        data = json.load(f)

    clean_stops = {}
    
    for item in data:
        stop_id = item.get("id")
        stop_name = item.get("name")
        
        # Проверяем ID на валидность
        if stop_id and stop_name and is_valid_stop_id(stop_id):
            # Если ID еще нет в словаре, добавляем
            if str(stop_id) not in clean_stops:
                clean_stops[str(stop_id)] = stop_name

    # Сохраняем очищенный список
    result = [{"id": k, "name": v} for k, v in clean_stops.items()]
    
    with OUTPUT_FILE.open("w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ Очистка завершена!")
    print(f"Было записей: {len(data)}")
    print(f"Осталось уникальных остановок: {len(result)}")
    print(f"Сохранено в: {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    main()