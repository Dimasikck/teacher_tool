import json
import re
from config import Config

try:
    import openai
except Exception:
    openai = None


class AIAnalyzer:
    def __init__(self):
        self.api_key = Config.OPENAI_API_KEY
        self.client = None
        if openai and self.api_key:
            try:
                openai.api_key = self.api_key
                # openai>=1.x
                self.client = openai.OpenAI(api_key=self.api_key)
            except Exception:
                self.client = None

    def analyze_text_assignment(self, text, requirements):
        prompt = f"""
        Проанализируй студенческую работу по следующим критериям:
        {requirements}

        Текст работы:
        {text}

        Оцени работу от 0 до 100 и дай краткое обоснование.
        Формат ответа: JSON с полями score, feedback, suggestions
        """

        if not self.client:
            # Fallback heuristic if no API key
            score = max(0, min(100, 60 + (len(text.split()) // 50)))
            return {"score": score, "feedback": "Локальная эвристическая оценка без ИИ", "suggestions": []}
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "system", "content": "Ты опытный преподаватель"},
                          {"role": "user", "content": prompt}],
                temperature=0.3
            )
            result = response.choices[0].message.content
            return json.loads(result)
        except Exception as e:
            return {"score": 0, "feedback": f"Ошибка анализа: {str(e)}", "suggestions": []}

    def check_plagiarism(self, text):
        words = len(text.split())
        unique_words = len(set(text.lower().split()))
        uniqueness = (unique_words / words * 100) if words > 0 else 0

        return {
            "uniqueness_score": round(uniqueness, 2),
            "is_original": uniqueness > 70
        }

    def analyze_code(self, code, language='python'):
        prompt = f"""
        Проверь код на {language}:
        1. Синтаксис
        2. Логика
        3. Оптимизация
        4. Стиль кода

        Код:
        {code}

        Дай оценку 0-100 и рекомендации.
        """

        if not self.client:
            return {"score": 70, "feedback": "Локальная проверка кода недоступна без ИИ", "suggestions": []}
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка анализа кода: {str(e)}"

    def suggest_schedule_slot(self, existing_schedule, duration_minutes=90):
        prompt = f"""
        На основе существующего расписания предложи оптимальное время для нового занятия.
        Длительность: {duration_minutes} минут

        Существующее расписание:
        {json.dumps(existing_schedule, ensure_ascii=False)}

        Учти:
        - Рабочее время 8:00-20:00
        - Перерывы между занятиями минимум 10 минут
        - Избегай пересечений

        Верни JSON: {{"day": "день_недели", "time": "HH:MM", "reason": "обоснование"}}
        """

        if not self.client:
            # Simple local suggestion: next weekday at 10:00
            return {"day": "Monday", "time": "10:00", "reason": "Локальная эвристика без ИИ"}
        try:
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            return {"error": str(e)}