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
- Ключевые преимущества: собственное производство → честная цена, быстрая реакция, гибкие условия без жёстких контрактов
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') != 'production'
    app.run(debug=debug, host='0.0.0.0', port=port)
