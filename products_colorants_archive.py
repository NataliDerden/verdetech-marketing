"""
Архив прайсов красителей Verde Tech (октябрь 2024).

ВАЖНО: эти позиции НЕ входят в актуальный прайс 2026_04 (там красителей нет).
Используются как ориентировочный реестр продуктов и цен 2024 года, чтобы
КП-генератор мог корректно подбирать колор-решения по запросу клиента.

При использовании в КП обязательна пометка: "цена ориентировочная по прайсу
14.10.2024 — точную стоимость уточняем менеджером перед заказом".

Источники:
- products/colorants-archive-2024/КП_№_14_1_Красители ... мясники и рыбники
- products/colorants-archive-2024/КП_№_14_2_Красители ... кондитер (водо- и жирорастворимые)
- products/colorants-archive-2024/КП_№_14_4_Красители натуральные
- products/colorants-archive-2024/Красители (новые)/ — спецификации в .docx

Итого: 53 позиции из 4 групп (meat_fish, confectionery_water, confectionery_lake, natural).
"""
import json
import os
import re
from typing import List, Dict, Optional

ARCHIVE_DATE = "14.10.2024"
ARCHIVE_NOTE = "Цена ориентировочная по прайсу 14.10.2024, актуализирует менеджер"

_JSON_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'products', 'colorants_archive_2024.json'
)

# Карта: tag → читаемая категория для отчётов
TAG_LABELS = {
    "meat_fish": "Красители для мясо- и рыбопереработки",
    "confectionery_water": "Красители кондитерские (водорастворимые)",
    "confectionery_lake": "Красители кондитерские (жирорастворимые / лак)",
    "natural": "Натуральные красители (clean label)",
}

# Цвет/тон → ключевые слова в имени или примечании
COLOR_HINTS = {
    "красный": ["красный", "красн", "паприк", "кармин", "свеколь", "малинов", "вишн"],
    "розовый": ["розов", "малинов", "паприк"],
    "оранжевый": ["оранжев", "паприк", "аннато", "лосос"],
    "жёлтый": ["жёлт", "желт", "куркум", "хинолин", "карамель"],
    "зелёный": ["зелён", "зелен", "хлорофилл", "яблок", "спирулин"],
    "синий": ["син", "голуб", "индиго"],
    "фиолетовый": ["фиолет", "лаванд", "виноград", "ежевик"],
    "коричневый": ["коричн", "шоколад", "кофе", "карамель", "колер", "е150"],
    "чёрный": ["чёрн", "черн", "уголь", "е153"],
    "белый": ["белый", "е171", "диоксид"],
}


def _load_records() -> List[Dict]:
    if not os.path.exists(_JSON_PATH):
        # Логируем громко: на Railway/в логах будет видно, что архив не загрузился
        print(f"[colorants-archive] WARN: JSON не найден по пути {_JSON_PATH} — "
              f"архив красителей будет пуст, КП по запросам про цвет получит только актуальный прайс",
              flush=True)
        return []
    try:
        with open(_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        print(f"[colorants-archive] WARN: ошибка чтения {_JSON_PATH}: {e} — архив будет пуст",
              flush=True)
        return []
    if not data:
        print(f"[colorants-archive] WARN: JSON пустой, архив красителей не загружен",
              flush=True)
        return []
    print(f"[colorants-archive] Загружено {len(data)} позиций красителей из архива {ARCHIVE_DATE}",
          flush=True)
    return data


COLORANTS_ARCHIVE: List[Dict] = _load_records()


def _norm(s: Optional[str]) -> str:
    return re.sub(r'\s+', ' ', (s or '').lower()).strip()


def get_colorants_by_industry(industry: str) -> List[Dict]:
    """Вернуть все архивные красители, релевантные данной отрасли."""
    if not industry:
        return []
    ind_lc = industry.lower()
    out = []
    for rec in COLORANTS_ARCHIVE:
        targets = rec.get("industry_targets") or []
        if any(t in ind_lc or ind_lc in t for t in targets):
            out.append(rec)
    return out


def get_colorants_by_color(color_or_tone: str) -> List[Dict]:
    """Подобрать архивные красители по цвету/тону (например 'красный', 'свекольный')."""
    if not color_or_tone:
        return []
    q = _norm(color_or_tone)
    # Развернём запрос в множество подсказок
    hint_words = set([q])
    for color, hints in COLOR_HINTS.items():
        if color in q or any(h in q for h in hints):
            hint_words.update(hints)
    out = []
    for rec in COLORANTS_ARCHIVE:
        blob = " ".join([
            _norm(rec.get("name")),
            _norm(rec.get("note")),
            _norm(rec.get("composition")),
            _norm(rec.get("category_label")),
        ])
        if any(h in blob for h in hint_words):
            out.append(rec)
    return out


def find_colorants_for_context(context_text: str, industry: str = "",
                                max_items: int = 12) -> List[Dict]:
    """
    Главная функция: подбирает архивные красители под контекст КП.
    Возвращает обогащённые записи с архивной пометкой.
    """
    if not COLORANTS_ARCHIVE:
        return []
    blob = (context_text or "").lower()
    industry_lc = (industry or "").lower()

    scored = []
    for rec in COLORANTS_ARCHIVE:
        score = 0
        name_lc = _norm(rec.get("name"))
        note_lc = _norm(rec.get("note"))
        comp_lc = _norm(rec.get("composition"))
        targets = rec.get("industry_targets") or []
        full = " ".join([name_lc, note_lc, comp_lc, _norm(rec.get("category_label"))])

        # Отрасль
        if industry_lc:
            if any(t in industry_lc or industry_lc in t for t in targets):
                score += 4

        # Цветовые подсказки в контексте
        for color, hints in COLOR_HINTS.items():
            if color in blob or any(h in blob for h in hints):
                if any(h in full for h in hints):
                    score += 3

        # Прямые упоминания
        for word in re.findall(r'[а-яёa-z]{4,}', name_lc):
            if word in blob:
                score += 2
        for word in re.findall(r'[а-яёa-z]{4,}', note_lc):
            if word in blob:
                score += 1

        # Триггеры самого слова "краситель"/"цвет"/"окрас"
        if any(kw in blob for kw in ["краситель", "пигмент", "окрас", "цвет ",
                                      "розов", "красн", "жёлт", "желт",
                                      "оранж", "зелен", "син", "фиолет",
                                      "корич", "чёрн", "черн", "карамель",
                                      "паприк", "кармин", "свекол", "аннато"]):
            score += 1

        if score > 0:
            scored.append((score, rec))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [_to_enriched(r) for _, r in scored[:max_items]]


def _to_enriched(rec: Dict) -> Dict:
    """Преобразовать архивную запись в формат, совместимый с _enrich_price_entry."""
    return {
        "name": rec.get("name", ""),
        "category": rec.get("category_label", ""),
        "tag": rec.get("tag", ""),
        "price_archive_2024_vat": rec.get("price_2024_vat"),
        "price_bulk_no_vat": None,
        "price_bulk_vat": None,
        "price_small_no_vat": None,
        "spec_purpose": (rec.get("composition") or "")[:300],
        "spec_path": "",
        "has_spec": True,
        "is_archive": True,
        "archive_date": ARCHIVE_DATE,
        "archive_note": ARCHIVE_NOTE,
        "dosage": rec.get("dosage", ""),
        "packing": rec.get("packing", ""),
        "note": rec.get("note", ""),
        "industry_targets": rec.get("industry_targets", []),
    }


def get_archive_summary() -> Dict:
    """Сервисная: сводка по архиву красителей."""
    by_tag: Dict[str, int] = {}
    for r in COLORANTS_ARCHIVE:
        by_tag[r.get("tag", "?")] = by_tag.get(r.get("tag", "?"), 0) + 1
    return {
        "total": len(COLORANTS_ARCHIVE),
        "by_tag": by_tag,
        "archive_date": ARCHIVE_DATE,
    }


if __name__ == "__main__":
    import sys
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    s = get_archive_summary()
    print(f"[colorants-archive] Загружено {s['total']} позиций ({s['archive_date']})")
    for tag, n in s["by_tag"].items():
        print(f"  {tag}: {n}")
    # Пример: подбор под мясокомбинат с розовым тоном
    sample = find_colorants_for_context(
        "нужен розовый оттенок для варёных колбас",
        industry="meat_processing",
        max_items=5,
    )
    print(f"\nПример подбора (мясокомбинат, розовый): {len(sample)} позиций")
    for it in sample:
        print(f"  - {it['name']} [{it.get('note','')}] — {it['price_archive_2024_vat']} руб (архив 2024)")
