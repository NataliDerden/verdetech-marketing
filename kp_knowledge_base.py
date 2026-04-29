"""
База знаний КП-генератора Verde Tech.

Объединяет четыре источника информации о продуктах:
1. PRICE_MAP — позиции из актуального прайса (01.05.2026) с ценами по фасовкам
2. _ALL_SPECS_RAW — спецификации (что делает продукт, дозировка, применение)
3. ALL_PRODUCTS — курированный каталог самых продаваемых продуктов
4. COLORANTS_ARCHIVE — архивный реестр красителей (прайс 14.10.2024, 53 позиции),
   нет в актуальном прайсе 2026, но используется когда клиент спрашивает про
   красители, цвета, окрашивание. Помечается флагом is_archive=True.

Кросс-референсирует их по имени и предоставляет find_relevant_for_context()
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

try:
    from products_colorants_archive import (
        find_colorants_for_context as _find_colorants_archive,
        COLORANTS_ARCHIVE as _COLORANTS_ARCHIVE,
        ARCHIVE_DATE as _COLORANTS_ARCHIVE_DATE,
    )
except ImportError:
    _find_colorants_archive = None
    _COLORANTS_ARCHIVE = []
    _COLORANTS_ARCHIVE_DATE = ""


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


def _colorant_context_signal(combined_text):
    """True если в тексте есть сигнал к красителям/цветам — чтобы подмешать архив 2024."""
    if not combined_text:
        return False
    triggers = CATEGORY_TRIGGERS['colors'] + [
        'цвет', 'окрас', 'оттенок', 'колер', 'розов', 'красн', 'жёлт', 'желт',
        'оранж', 'зелен', 'син', 'голуб', 'фиолет', 'коричн', 'белый', 'чёрн', 'черн',
        'свекол', 'аннато', 'паприк', 'е120', 'е124', 'е129', 'е131', 'е133',
        'е104', 'е110', 'е122', 'е132', 'е171', 'е150', 'е160', 'е100', 'е141',
        'халяль', 'натуральн краситель', 'clean label',
    ]
    blob = combined_text.lower()
    return any(t in blob for t in triggers)


def find_relevant_for_context(situation_text, hints_text, deal_products_text='',
                               site_text='', industry='', max_items=60):
    """
    Главная функция БЗ для КП-генератора.
    Возвращает список обогащённых продуктов (имя+категория+цена+спецификация),
    отсортированный по релевантности к контексту клиента.

    context = ситуация клиента + подсказки менеджера + продукты в сделке + анализ сайта.

    Если в контексте есть сигналы к красителям/цветам, дополнительно подмешивает
    архивные красители 2024 года (с пометкой is_archive=True).
    """
    combined = ' '.join(filter(None, [situation_text, hints_text, deal_products_text, site_text, industry])).lower()

    detected = detect_categories_in_text(combined)
    needs_colorants = 'colors' in detected or _colorant_context_signal(combined)

    # Если категории не обнаружены, нет деталей и нет сигнала к красителям — пусто
    if not detected and not deal_products_text and not site_text and not needs_colorants:
        return []

    # Скорим ВСЕ позиции актуального прайса
    all_scored = []
    for entry in PRICE_MAP.values():
        enriched = _enrich_price_entry(entry)
        score = _score_product_against_context(enriched, combined)
        if score > 0:
            all_scored.append((score, enriched))

    all_scored.sort(key=lambda x: x[0], reverse=True)
    main_items = [item for _, item in all_scored[:max_items]]

    # Дополнительно: подмешиваем архивные красители если есть сигнал
    if needs_colorants and _find_colorants_archive is not None:
        archive_items = _find_colorants_archive(
            combined, industry=industry, max_items=12
        )
        # Кладём архивные после основных, но не превышая общий лимит
        # Избегаем дубликатов по имени
        existing_names = {it.get('name', '').lower() for it in main_items}
        for arch in archive_items:
            if arch.get('name', '').lower() not in existing_names:
                main_items.append(arch)

    return main_items


def get_knowledge_base_summary():
    """Сервисная: краткая сводка о том, что есть в БЗ."""
    return {
        'price_entries': len(PRICE_MAP),
        'specs_entries': len(_ALL_SPECS_RAW) if _ALL_SPECS_RAW else 0,
        'curated_products': len(ALL_PRODUCTS) if ALL_PRODUCTS else 0,
        'colorants_archive': len(_COLORANTS_ARCHIVE),
        'colorants_archive_date': _COLORANTS_ARCHIVE_DATE,
        'categories_supported': list(CATEGORY_TRIGGERS.keys()),
    }
