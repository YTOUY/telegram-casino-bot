"""
Скрипт для проверки валидности TGS файла
"""
import gzip
import json
import os
import sys
import io

def validate_tgs_file(file_path):
    """Проверить валидность TGS файла"""
    if sys.platform == 'win32':
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    
    print(f"🔍 Проверка TGS файла: {file_path}")
    print("=" * 50)
    
    if not os.path.exists(file_path):
        print(f"❌ Файл не найден: {file_path}")
        return False
    
    file_size = os.path.getsize(file_path)
    print(f"📊 Размер файла: {file_size / 1024:.2f} KB")
    
    try:
        # Читаем файл
        with open(file_path, 'rb') as f:
            tgs_data = f.read()
        
        print(f"📦 Прочитано байт: {len(tgs_data)}")
        
        # Пробуем распаковать как gzip
        try:
            decompressed = gzip.decompress(tgs_data)
            print(f"✅ Файл успешно распакован из gzip")
            print(f"📊 Размер после распаковки: {len(decompressed) / 1024:.2f} KB")
        except Exception as e:
            print(f"❌ Ошибка распаковки gzip: {e}")
            return False
        
        # Пробуем распарсить как JSON
        try:
            lottie_json = json.loads(decompressed.decode('utf-8'))
            print(f"✅ JSON успешно распарсен")
            
            # Проверяем структуру Lottie
            if 'v' in lottie_json:
                print(f"📋 Версия Lottie: {lottie_json['v']}")
            if 'fr' in lottie_json:
                print(f"📋 FPS: {lottie_json['fr']}")
            if 'w' in lottie_json and 'h' in lottie_json:
                print(f"📋 Размеры: {lottie_json['w']}x{lottie_json['h']}")
            if 'layers' in lottie_json:
                print(f"📋 Слоев: {len(lottie_json['layers'])}")
            if 'assets' in lottie_json:
                print(f"📋 Ассетов: {len(lottie_json['assets'])}")
            
            print(f"✅ TGS файл валиден и содержит корректную Lottie анимацию")
            return True
            
        except json.JSONDecodeError as e:
            print(f"❌ Ошибка парсинга JSON: {e}")
            print(f"📋 Первые 200 символов распакованных данных:")
            print(decompressed.decode('utf-8', errors='ignore')[:200])
            return False
            
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")
        return False


if __name__ == "__main__":
    file_path = os.path.join("mini_app", "stickers", "slots", "base.tgs")
    validate_tgs_file(file_path)
    
    print()
    file_path_new = os.path.join("mini_app", "stickers", "slots", "base_new.tgs")
    if os.path.exists(file_path_new):
        print("=" * 50)
        validate_tgs_file(file_path_new)







