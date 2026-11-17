from utils.ai_service import ask_deepseek

result = ask_deepseek(
    "Ты — астролог. Ответь кратко.",
    "Какая сегодня энергия дня?",
    max_tokens=100,
    temperature=0.8
)
print("Result:", result)