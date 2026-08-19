def analyze(data: str) -> str:
    headers = {"Content-Type": "application/json"}
    prompt = f"""
Ты — профессиональный спортивный аналитик линии. Проанализируй данные матча:
{data}

Оцени форму, H2H, покрытие, физическую готовность и маркеты (форы/тоталы/исход).
Выдай строгий разбор и сводную таблицу:
| Турнир | Матч | Выбор | Риск |
"""
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    try:
        # Получаем полный список актуальных моделей аккаунта
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={GEMINI_KEY}"
        list_res = httpx.get(list_url, timeout=15.0).json()
        
        if "error" in list_res:
            return f"Ошибка API ключа: {list_res['error'].get('message')}"
            
        models = [
            m["name"] for m in list_res.get("models", [])
            if "generateContent" in m.get("supportedGenerationMethods", [])
        ]
        
        # Сортируем: сначала самые свежие (flash / pro)
        models.sort(key=lambda x: ("flash" in x, "2.0" in x, "pro" in x), reverse=True)

        last_error = ""
        for model_name in models:
            gen_url = f"https://generativelanguage.googleapis.com/v1beta/{model_name}:generateContent?key={GEMINI_KEY}"
            try:
                res = httpx.post(gen_url, headers=headers, json=payload, timeout=40.0)
                res_json = res.json()
                if "candidates" in res_json:
                    return res_json["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    last_error = res_json.get("error", {}).get("message", "Нет ответа")
            except Exception as e:
                last_error = str(e)
                continue

        return f"Не удалось получить ответ ни от одной модели. Последняя ошибка: {last_error}"

    except Exception as e:
        return f"Ошибка соединения: {str(e)}"
