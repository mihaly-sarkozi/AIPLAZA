class SimpleResponder:
    """Egy egyszerű tesztválasz generátor, ami az OpenAI klienssel azonos struktúrát ad vissza."""

    async def chat(self, question: str) -> str:
        return f"(Tesztválasz) A kérdésed: {question}"