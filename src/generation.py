def llm_generation(query, context, llm_client):
    prompt = f"""
    You are a helpful assistant.

    Use the context below to answer the question.

    Context:
    {context}

    Question:
    {query}

    Answer:
    """

    response = llm_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "user", "content": prompt}
        ]
    )

    return response.choices[0].message.content