"""
Прайс-лист Verde Tech — загрузка и поиск цен по названию продукта.
Источник: products/VerdeTech-прайс 2026_04_.csv (cp866)
Две ценовые колонки: тарное место (мешок 20-25 кг) и меньше тарного.
"""
import csv
import os
import re

PRICE_VALID_UNTIL = "01.05.2026"
_CSV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         'products', 'VerdeTech-прайс 2026_04_.csv')

# { normalized_name: {'name': str, 'cat': str,
#                      'bulk_no_vat': float, 'bulk_vat': float,
#                      'small_no_vat': float, 'small_vat': float} }
PRICE_MAP: dict = {}


def _norm(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r'\s+', ' ', s)
    # убираем суффиксы сорта чтобы не мешали матчингу
    return s


def _parse_price(s: str) -> float | None:
    s = s.strip().replace('\xa0', '').replace(' ', '').replace(',', '.')
    try:
        return float(s)
    except ValueError:
        return None


def _load() -> dict:
    result = {}
    if not os.path.exists(_CSV_PATH):
        print(f'[prices] Файл прайса не найден: {_CSV_PATH}')
        return result

    with open(_CSV_PATH, encoding='cp866', errors='replace', newline='') as f:
        reader = csv.reader(f, delimiter=';')
        rows = list(reader)

    # Данные начинаются со строки 8 (индекс 8)
    for row in rows[8:]:
        if len(row) < 14:
            continue
        name = row[3].strip().strip('"')
        cat  = row[1].strip()
        if not name or not cat:
            continue

        bulk_no_vat  = _parse_price(row[10])
        bulk_vat     = _parse_price(row[11])
        small_no_vat = _parse_price(row[12])
        small_vat    = _parse_price(row[13])

        if bulk_no_vat is None and small_no_vat is None:
            continue

        key = _norm(name)
        result[key] = {
            'name':         name,
            'cat':          cat,
            'bulk_no_vat':  bulk_no_vat,
            'bulk_vat':     bulk_vat,
            'small_no_vat': small_no_vat,
            'small_vat':    small_vat,
        }

    print(f'[prices] Загружено {len(result)} позиций из прайса')
    return result


def lookup_price(product_name: str) -> dict | None:
    """
    Ищет цену по названию продукта.
    Возвращает dict с ценами или None если не найдено.
    Стратегия: точное совпадение → по первым N словам → по любому слову.
    """
    if not PRICE_MAP:
        return None

    key = _norm(product_name)

    # 1. Точное совпадение
    if key in PRICE_MAP:
        return PRICE_MAP[key]

    # 2. Совпадение по первым 3 словам
    words = key.split()
    if len(words) >= 3:
        prefix3 = ' '.join(words[:3])
        for k, v in PRICE_MAP.items():
            if k.startswith(prefix3):
                return v

    # 3. Совпадение по первым 2 словам (если слова длинные — не однобуквенные)
    if len(words) >= 2 and all(len(w) > 2 for w in words[:2]):
        prefix2 = ' '.join(words[:2])
        for k, v in PRICE_MAP.items():
            if k.startswith(prefix2):
                return v

    # 4. Ключевое слово (первое длинное слово) содержится в ключе прайса
    meaningful = [w for w in words if len(w) > 4]
    if meaningful:
        first = meaningful[0]
        for k, v in PRICE_MAP.items():
            if first in k:
                return v

    return None


def format_price(price_entry: dict) -> dict:
    """
    Форматирует цены для подстановки в шаблон КП.
    Возвращает словарь с человекочитаемыми строками.
    """
    def fmt(val: float | None) -> str:
        if val is None:
            return ''
        return f'{val:,.2f}'.replace(',', ' ').rstrip('0').rstrip('.')

    bulk_str  = fmt(price_entry.get('bulk_no_vat'))
    small_str = fmt(price_entry.get('small_no_vat'))
    bulk_v    = fmt(price_entry.get('bulk_vat'))
    small_v   = fmt(price_entry.get('small_vat'))

    return {
        'bulk_no_vat':  bulk_str,
        'bulk_vat':     bulk_v,
        'small_no_vat': small_str,
        'small_vat':    small_v,
        'display':      _make_display(bulk_str, small_str),
    }


def _make_display(bulk: str, small: str) -> str:
    """Одна цена — за мешок без НДС (bulk), fallback на small если bulk пуст."""
    price = bulk or small
    return f'{price} ₽/кг' if price else ''


def get_category_pricelist(category: str = '') -> list:
    """
    Возвращает отформатированный список позиций из прайса для слайда-прайслиста.
    Если category задана — фильтрует по ней, иначе возвращает все позиции.
    """
    items = sorted(PRICE_MAP.values(), key=lambda x: (x['cat'], x['name']))
    if category:
        items = [i for i in items if i['cat'] == category]
    result = []
    for it in items:
        fmt = format_price(it)
        result.append({
            'name': it['name'],
            'cat':  it['cat'],
            'bulk':  fmt.get('bulk_no_vat', ''),
            'small': fmt.get('small_no_vat', ''),
        })
    return result


# Загружаем при импорте
PRICE_MAP = _load()
