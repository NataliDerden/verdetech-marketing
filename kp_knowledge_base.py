"""
База знаний КП-генератора Verde Tech.

Объединяет три источника информации о продуктах:
1. PRICE_MAP (1882 позиции из прайса 01.05.2026 с ценами по тарным/мелким фасовкам)
2. _ALL_SPECS_RAW (~800 спецификаций — что делает продукт, дозировка, применение)
3. ALL_PRODUCTS (курированный каталог самых продаваемых продуктов)

Кросс-референсирует их по имени и предоставляет одну функцию find_relevant_for_context()
которая ранжирует продукты по релевантности к ситуации клиента.
"""
import re
from products_prices import PRICE_MAP

try:
    from products_specs_all import ALL_SPECS as _ALL_SPECS_RAW
except ImportError:
    _ALL_SPECS_RAW = {}

try:
    from products_catalog import UNIFIED_PRODUCTS as ALL_PRODUCTS
except ImportError:
    ALL_PRODUCTS = []


# Триггеры категорий — слова, которые указывают на интерес клиента к данной категории
CATEGORY_TRIGGERS = {
    'spices': [
        'специ', 'пряност', 'перец', 'паприк', 'розмарин', 'чеснок', 'базилик',
        'орегано', 'тимьян', 'тимиан', 'кориандр', 'тмин', 'кардамон', 'имбир',
        'куркум', 'гвоздик', 'мускат', 'корица', 'лавр', 'фенхель', 'укроп',
        'петрушк', 'майоран', 'шалфей', 'сушён', 'сушен', 'смесь приправ',
        'смесь специй', 'приправ', 'анис',
    ],
    'marinades': [
        'маринад', 'ткемали', 'грузинск', 'чесночн', 'универсал', 'французск',
        'для шашлык', 'для курицы', 'для мяс', 'фруктово-специев',
    ],
    'brines': [
        'рассол', 'инъект', 'шприцев', 'бесфосфатн', 'фосфат', 'засолк', 'ветчин',
    ],
    'stabilizers': [
        'стабилизатор', 'эмультек', 'фреш', 'белков', 'термостаб', 'эмульгатор',
        'связующ',
    ],
    'functional': [
        'витамин', 'smart plus', 'инулин', 'пребиотик', 'минерал', 'кальций',
        'магний', 'функциональн', 'clean label', 'обогащ',
    ],
    'colors': [
        'краситель', 'пигмент', 'кармин', 'аннато', 'окраск',
    ],
    'sauces': [
        'соус', 'кетчуп', 'майонез', 'дрессинг',
    ],
    'extracts': [
        'экстракт', 'эфирн', 'олеосмол',
    ],
    'dried_vegetables': [
        'сушёный лук', 'сушеный лук', 'сушёная морковь', 'сушеная морковь',
        'дегидратир', 'хлопья', 'чипсы',
    ],
}


def _norm(s):
    s = (s or '').lower().strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def detect_categories_in_text(text):
    """Возвращает множество категорий, ключевые слова которых встречаются в тексте."""
    if not text:
        return set()
    blob = text.lower()
    found = set()
    for cat, keywords in CATEGORY_TRIGGERS.items():
        if any(kw in blob for kw in keywords):
            found.add(cat)
    return found


def _find_spec_for_name(product_name):
    """Найти спецификацию по имени продукта (точное → префикс → ключевое слово)."""
    if not _ALL_SPECS_RAW:
        return None
    key = _norm(product_name)
    if not key:
        return None

    # 1. Точное совпадение
    for spec_name, meta in _ALL_SPECS_RAW.items():
        if _norm(spec_name) == key:
            return meta

    # 2. По первым 3 словам
    words = key.split()
    if len(words) >= 3:
        prefix3 = ' '.join(words[:3])
        for spec_name, meta in _ALL_SPECS_RAW.items():
            sn = _norm(spec_name)
            if sn.startswith(prefix3) or prefix3.startswith(sn[:len(prefix3)]):
                return meta

    # 3. По первым 2 значимым словам
    meaningful = [w for w in words if len(w) > 3]
    if len(meaningful) >= 2:
        first_two = ' '.join(meaningful[:2])
        for spec_name, meta in _ALL_SPECS_RAW.items():
            if first_two in _norm(spec_name):
                return meta

    return None


def _enrich_price_entry(price_entry):
    """Обогащает позицию из прайса данными из спецификации (что делает, как применять)."""
    spec = _find_spec_for_name(price_entry['name'])
    spec_text = ''
    spec_path = ''
    if spec:
        spec_text = (spec.get('text') or '').strip()
        # Берём первые 300 символов содержательного текста (без шапки документа)
        if spec_text:
            spec_text = re.sub(r'\s+', ' ', spec_text)[:300]
        spec_path = spec.get('path', '')

    return {
        'name': price_entry['name'],
        'category': price_entry.get('cat', ''),
        'price_bulk_no_vat': price_entry.get('bulk_no_vat'),
        'price_bulk_vat': price_entry.get('bulk_vat'),
        'price_small_no_vat': price_entry.get('small_no_vat'),
        'spec_purpose': spec_text,
        'spec_path': spec_path,
        'has_spec': bool(spec),
    }


def _score_product_against_context(enriched, context_text):
    """Считает релевантность продукта контексту. Чем выше скор, тем выше в списке."""
    score = 0
    ctx = context_text.lower()
    name_lc = enriched['name'].lower()
    cat_lc = enriched['category'].lower()
    spec_lc = (enriched.get('spec_purpose', '') or '').lower()

    # Прямое упоминание в контексте слов из имени продукта (значимых)
    for word in re.findall(r'[а-яёa-z]+', name_lc):
        if len(word) > 4 and word in ctx:
            score += 5
    # Слова из категории
    for word in re.findall(r'[а-яёa-z]+', cat_lc):
        if len(word) > 4 and word in ctx:
            score += 3
    # Совпадение по триггерам категорий
    for cat_name, keywords in CATEGORY_TRIGGERS.items():
        if any(kw in ctx for kw in keywords):
            if any(kw in name_lc or kw in cat_lc for kw in keywords):
                score += 2
            if any(kw in spec_lc for kw in keywords):
                score += 1
    return score


def find_relevant_for_context(situation_text, hints_text, deal_products_text='',
                               site_text='', industry='', max_items=60):
    """
    Главная функция БЗ для КП-генератора.
    Возвращает список обогащённых продуктов (имя+категория+цена+спецификация),
    отсортированный по релевантности к контексту клиента.

    context = ситуация клиента + подсказки менеджера + продукты в сделке + анализ сайта.
    """
    combined = ' '.join(filter(None, [situation_text, hints_text, deal_products_text, site_text, industry])).lower()

    detected = detect_categories_in_text(combined)

    # Если категории не обнаружены и нет других сигналов — отдадим топ ходовых из курированного
    if not detected and not deal_products_text and not site_text:
        # Возвращаем небольшой набор по индустрии — пусть Claude сам выберет из каталога
        return []

    # Скорим ВСЕ позиции прайса
    all_scored = []
    for entry in PRICE_MAP.values():
        enriched = _enrich_price_entry(entry)
        score = _score_product_against_context(enriched, combined)
        if score > 0:
            all_scored.append((score, enriched))

    # Сортируем по релевантности
    all_scored.sort(key=lambda x: x[0], reverse=True)

    return [item for _, item in all_scored[:max_items]]


def get_knowledge_base_summary():
    """Сервисная: краткая сводка о том, что есть в БЗ."""
    return {
        'price_entries': len(PRICE_MAP),
        'specs_entries': len(_ALL_SPECS_RAW) if _ALL_SPECS_RAW else 0,
        'curated_products': len(ALL_PRODUCTS) if ALL_PRODUCTS else 0,
        'categories_supported': list(CATEGORY_TRIGGERS.keys()),
    }
