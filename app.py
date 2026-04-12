from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from dotenv import load_dotenv
import requests
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'verdetech-secret-key-2025')

OPENROUTER_API_KEY = os.environ.get('OPENROUTER_API_KEY', '')
MARKETER_PASSWORD = os.environ.get('MARKETER_PASSWORD', 'verde2025')

VERDETECH_CONTEXT = """
Ты — AI-маркетолог компании VerdeTech (verdetech.ru). Твоя задача — помогать маркетологу.

О компании VerdeTech:
- Производит комплексные пищевые добавки, специи, пряности и сушёные овощи
- Рынок B2B: клиенты — производители пищевой продукции, HoReCa сети, оптовые компании, дистрибьюторы
- Ключевые преимущества: собственное производство → честная цена, отгрузка за 5 дней, гибкие условия без жёстких контрактов
- Сильная позиция в импортозамещении — разрабатывают натуральные аналоги импортных продуктов
- Сотрудничают с университетами, научный подход к разработке

Tone of voice: профессиональный, экспертный, партнёрский. Без излишней рекламности. Деловой стиль.

Целевая аудитория в письмах: технологи производств, директора по закупкам, владельцы пищевых предприятий.

Всегда отвечай на русском языке.
"""

TOOLS = {
    'email_writer': {
        'name': 'Написать письмо',
        'icon': '✉️',
        'placeholder': 'Например: письмо для новых клиентов о нашем ассортименте специй, или: реактивация клиентов которые давно не покупали',
        'prompt': lambda inp: f"""Напиши письмо для email-рассылки VerdeTech.

Задача: {inp}

Выдай результат строго в таком формате:

**Тема письма:** (до 60 символов, цепляющая, без спам-слов)

**Прехедер:** (до 90 символов, дополняет тему)

**Текст письма:**
(профессиональное письмо с приветствием, основным посылом, конкретной пользой для клиента и призывом к действию)

**Призыв к действию:** (одна чёткая кнопка или ссылка)
"""
    },
    'campaign_planner': {
        'name': 'План кампании',
        'icon': '📅',
        'placeholder': 'Например: план на май для прогрева новых лидов, или: серия писем для запуска нового продукта',
        'prompt': lambda inp: f"""Составь план email-кампании для VerdeTech.

Задача: {inp}

Включи в план:
1. Цель кампании
2. Сегмент аудитории
3. Таблицу писем: № | Дата | Тема письма | Цель письма | Призыв к действию
4. Ключевые метрики для отслеживания (open rate, CTR, конверсии)
5. Краткие рекомендации по каждому письму
"""
    },
    'subject_lines': {
        'name': 'Темы писем',
        'icon': '💡',
        'placeholder': 'Например: письмо о скидках на специи для HoReCa, или: напоминание о неоплаченном заказе',
        'prompt': lambda inp: f"""Сгенерируй 10 вариантов темы письма для рассылки VerdeTech.

Контекст письма: {inp}

Требования:
- Профессиональный B2B стиль
- Без спам-слов (бесплатно, срочно, только сегодня и т.п.)
- До 60 символов каждая
- Разные форматы: вопрос, факт, выгода, интрига, кейс

Формат: пронумерованный список с коротким пояснением почему эта тема работает.
"""
    },
    'segment_strategy': {
        'name': 'Сегментация базы',
        'icon': '🎯',
        'placeholder': 'Например: у нас 500 контактов — производители, HoReCa и оптовики, как сегментировать?',
        'prompt': lambda inp: f"""Разработай стратегию сегментации email-базы для VerdeTech.

Запрос: {inp}

Опиши:
1. Рекомендуемые сегменты с критериями
2. Что отправлять каждому сегменту (темы, частота, контент)
3. Как собирать данные для сегментации через Unisender
4. Приоритет сегментов по потенциалу выручки
"""
    },
    'metrics_advisor': {
        'name': 'Анализ метрик',
        'icon': '📊',
        'placeholder': 'Вставьте показатели рассылки: open rate X%, CTR Y%, отписки Z%, и я объясню что делать',
        'prompt': lambda inp: f"""Проанализируй метрики email-рассылки VerdeTech и дай рекомендации.

Данные: {inp}

Предоставь:
1. Оценку каждого показателя (хорошо/норма/плохо) с бенчмарками для B2B
2. Главные проблемы если есть
3. Конкретные шаги для улучшения каждого показателя
4. Приоритет действий (что сделать первым)
"""
    },
    'welcome_series': {
        'name': 'Welcome-серия',
        'icon': '👋',
        'placeholder': 'Например: приветственная серия для нового клиента который оставил заявку на сайте',
        'prompt': lambda inp: f"""Разработай welcome-серию писем для VerdeTech.

Контекст: {inp}

Создай серию из 4 писем:
Для каждого письма укажи:
- Письмо №X: [название]
- Когда отправить: (сразу / через N дней)
- Тема письма
- Цель письма
- Краткое содержание (3-5 предложений что написать)
- Призыв к действию
"""
    },
}


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated


@app.route('/')
def index():
    if session.get('logged_in'):
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('password') == MARKETER_PASSWORD:
            session['logged_in'] = True
            return redirect(url_for('dashboard'))
        error = 'Неверный пароль. Попробуйте ещё раз.'
    return render_template('login.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/dashboard')
@login_required
def dashboard():
    tools_ui = {k: {'name': v['name'], 'icon': v['icon'], 'placeholder': v['placeholder']} for k, v in TOOLS.items()}
    return render_template('dashboard.html', tools=TOOLS, tools_ui=tools_ui)


@app.route('/api/generate', methods=['POST'])
@login_required
def generate():
    data = request.get_json()
    tool_id = data.get('tool')
    user_input = data.get('input', '').strip()

    if not user_input:
        return jsonify({'error': 'Введите задачу'}), 400

    tool = TOOLS.get(tool_id)
    if not tool:
        return jsonify({'error': 'Инструмент не найден'}), 400

    prompt = tool['prompt'](user_input)

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
                'HTTP-Referer': 'https://verdetech.ru',
                'X-Title': 'VerdeTech Marketing Assistant',
            },
            json={
                'model': 'anthropic/claude-sonnet-4-5',
                'messages': [
                    {'role': 'system', 'content': VERDETECH_CONTEXT},
                    {'role': 'user', 'content': prompt},
                ],
                'max_tokens': 2000,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        content = result['choices'][0]['message']['content']
        return jsonify({'result': content})
    except requests.exceptions.Timeout:
        return jsonify({'error': 'Превышено время ожидания. Попробуйте ещё раз.'}), 504
    except Exception as e:
        return jsonify({'error': f'Ошибка: {str(e)}'}), 500


TEAM_SYSTEM_PROMPT = """Ты — AI-помощник команды Verde Tech (verdetech.ru), производителя пищевых ингредиентов и добавок в СПб.

Ты знаешь всю стратегию SEO и Яндекс.Директ для компании:

КЛЮЧЕВЫЕ ФАКТЫ:
- Verde Tech — производитель комплексных пищевых добавок, специй, маринадов, рассолов для шприцевания, сушёных овощей
- Сайт на WordPress, 120 страниц, 14 категорий каталога
- Сейчас НЕ в топ-10 Яндекса ни по одному запросу
- Главные конкуренты: edaprof.ru, yurealfood.ru, emkolbaski.ru, ssnab.ru

КРИТИЧЕСКИЕ SEO-ОШИБКИ:
1. Страница каталога: title "Архивы Каталог" (WordPress default), нет H1, нет meta description
2. Нет страниц под ключевые запросы: "рассолы для шприцевания", "комплексные пищевые добавки"
3. Нет Schema.org разметки

СЕМАНТИКА (Wordstat):
- комплексная пищевая добавка: 3639 показов
- шприцевание мяса: 1326 показов
- рассол для шприцевания: 1069 показов
- добавки для пищевого производства: 1146 показов

ДИРЕКТ: 6 групп объявлений, 18 вариантов, бюджет от 3500 руб./неделю на тест.

Отвечай по-русски, кратко и конкретно. Если спрашивают как исправить что-то в WordPress — давай пошаговую инструкцию."""

TEAM_TASKS = [
    {"id": 1, "cat": "SEO — Критические", "title": "Исправить title страницы каталога", "desc": 'Сейчас: "Архивы Каталог - Verde Tech". Нужно: "Каталог пищевых ингредиентов и добавок оптом — Verde Tech"', "steps": ["WordPress → Записи → Рубрики → Каталог → Изменить", "В блоке Yoast/RankMath внизу:", "SEO Title: Каталог пищевых ингредиентов и добавок оптом — Verde Tech", "Meta Description: Комплексные пищевые добавки, специи, маринады, рассолы для мясной, молочной, кондитерской промышленности.", "Сохранить"], "pri": "critical", "time": "10 мин"},
    {"id": 2, "cat": "SEO — Критические", "title": "Добавить H1 и описание к каталогу", "desc": "Нет H1 и текста — только список ссылок. Нужен текст 200-300 слов.", "steps": ["WordPress → Рубрики → Каталог → Изменить", "В поле Описание: текст про ассортимент, 14 категорий", "Ключевые слова: пищевые добавки оптом, от производителя, СПб", "Сохранить"], "pri": "critical", "time": "20 мин"},
    {"id": 3, "cat": "SEO — Критические", "title": "Улучшить meta description главной", "desc": 'Сейчас: "У нас вы можете купить..." → Нужно: конкретика + УТП', "steps": ["WordPress → Страницы → Главная → Изменить", "Meta Description: Производитель комплексных пищевых добавок, специй и ингредиентов в СПб. Оптом от 1 кг. 300+ клиентов. Доставка по РФ.", "Title: Производитель пищевых ингредиентов и добавок в СПб — Verde Tech", "Сохранить"], "pri": "high", "time": "5 мин"},
    {"id": 4, "cat": "SEO — Новые страницы", "title": "Создать страницу «Рассолы для шприцевания»", "desc": "1069 показов/мес. В топе emkolbaski.ru и yurealfood.ru. Verde Tech отсутствует.", "steps": ["WordPress → Записи → Добавить", "URL: /rassoly-dlya-shpricevaniya/", "H1: Рассолы для шприцевания мяса оптом", "Контент: 1500-2000 слов — виды, дозировки, для мяса/птицы/рыбы", "Таблица дозировок, FAQ 3-5 вопросов", "CTA: Запросить образцы", "Ссылки на каталог мясопереработки"], "pri": "critical", "time": "2-3 ч"},
    {"id": 5, "cat": "SEO — Новые страницы", "title": "Создать страницу «Комплексные пищевые добавки»", "desc": "3639 показов/мес — самый объёмный запрос.", "steps": ["URL: /kompleksnye-pishchevye-dobavki/", "H1: Комплексные пищевые добавки от производителя", "Контент: виды КПД, состав, применение по отраслям", "Таблица: тип → отрасль → функция", "FAQ: что такое КПД, ГОСТ, как выбрать", "CTA: Запросить каталог КПД"], "pri": "critical", "time": "2-3 ч"},
    {"id": 6, "cat": "SEO — Техническое", "title": "Добавить Schema.org разметку", "desc": "Конкуренты используют Schema.org — расширенные сниппеты в выдаче.", "steps": ["Установить плагин Schema Pro или использовать Yoast", "Organization schema: название, адрес, телефон, лого", "BreadcrumbList на все категории", "Проверить через Rich Results Test"], "pri": "high", "time": "30 мин"},
    {"id": 7, "cat": "SEO — Перелинковка", "title": "Добавить перелинковку между категориями", "desc": "Категории не ссылаются друг на друга. Блог не ведёт на каталог.", "steps": ["На категориях добавить «Смотрите также»", "Мясопереработка → Специи, Маринады", "В статьях блога — ссылки на категории", "На категориях — «Читайте в блоге: ...»"], "pri": "medium", "time": "1-2 ч"},
    {"id": 8, "cat": "Директ — Запуск", "title": "Создать аккаунт Яндекс.Директ", "desc": "Зарегистрироваться на direct.yandex.ru и пополнить баланс.", "steps": ["Перейти на direct.yandex.ru", "Войти под аккаунтом Яндекса", "Страна: Россия, валюта: рубли", "Пополнить: минимум 3500 руб."], "pri": "high", "time": "10 мин"},
    {"id": 9, "cat": "Директ — Запуск", "title": "Кампания: Рассолы для шприцевания", "desc": "Приоритетная группа — 1069 показов, горячий B2B интент.", "steps": ["Создать кампанию → Текстово-графические объявления", "Регион: Вся Россия, Пн-Пт 8:00-19:00", "Бюджет: 500 руб./день", "Фразы: рассол для шприцевания, рассол для шприцевания мяса, маринад для шприцевания мяса", "3 объявления из файла verdetech_ads_v2.md", "Минус-слова из файла", "Запустить"], "pri": "high", "time": "30 мин"},
    {"id": 10, "cat": "Директ — Запуск", "title": "Кампания: Комплексные пищевые добавки", "desc": "3639 показов — самый объёмный запрос.", "steps": ["Фразы: комплексная пищевая добавка, КПД купить, производство КПД", "3 объявления из файла", "Бюджет: 500 руб./день", "Минус-слова", "Запустить"], "pri": "high", "time": "20 мин"},
    {"id": 11, "cat": "Директ — Запуск", "title": "Создать остальные 4 кампании", "desc": "Пищевые добавки оптом, Специи оптом, Мясопереработка, Сушёные овощи.", "steps": ["По аналогии с предыдущими", "Фразы и объявления из verdetech_ads_v2.md", "Бюджет 300-500 руб./день на группу"], "pri": "medium", "time": "1 ч"},
    {"id": 12, "cat": "Контент", "title": "Статья: Рассол для шприцевания мяса", "desc": "Пилотная статья. Запрос: 1069 показов/мес.", "steps": ["Структура: Что такое → Виды → Составы → Дозировки → FAQ", "1500-2500 слов, таблица дозировок", "CTA: Запросить образцы", "Ссылки на каталог мясопереработки"], "pri": "high", "time": "3-4 ч"},
    {"id": 13, "cat": "Аналитика", "title": "Подключить Метрику + цели", "desc": "Цели: заявка, клик на телефон, скачивание прайса.", "steps": ["Проверить подключение Метрики", "Создать цели: форма, телефон, email, мессенджер", "Привязать Метрику к Директу"], "pri": "high", "time": "30 мин"},
    {"id": 14, "cat": "Контент", "title": "Лид-магнит: Справочник технолога", "desc": "PDF дозировок. Обмен на email + компания + должность.", "steps": ["Собрать таблицы дозировок КПД", "Оформить PDF 15-20 стр.", "Форма захвата на сайте", "Баннер в блоге и каталоге"], "pri": "medium", "time": "1-2 дня"},
]


@app.route('/team', methods=['GET', 'POST'])
def team_dashboard():
    if request.method == 'POST':
        if request.form.get('password') == MARKETER_PASSWORD:
            session['team_logged_in'] = True
            return redirect(url_for('team_dashboard'))
        return render_template('team_login.html', error='Неверный пароль')
    if not session.get('team_logged_in'):
        return render_template('team_login.html', error=None)
    return render_template('team.html', tasks=TEAM_TASKS)


@app.route('/api/team-chat', methods=['POST'])
def team_chat():
    data = request.get_json()
    user_message = data.get('message', '').strip()

    if not user_message:
        return jsonify({'error': 'Введите вопрос'}), 400

    try:
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'anthropic/claude-sonnet-4',
                'messages': [
                    {'role': 'system', 'content': TEAM_SYSTEM_PROMPT},
                    {'role': 'user', 'content': user_message},
                ],
                'max_tokens': 2000,
            },
            timeout=60,
        )
        response.raise_for_status()
        result = response.json()
        reply = result['choices'][0]['message']['content']
        return jsonify({'reply': reply})
    except Exception as e:
        return jsonify({'reply': f'Ошибка: {str(e)}'}), 500


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
