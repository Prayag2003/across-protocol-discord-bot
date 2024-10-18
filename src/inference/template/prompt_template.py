def get_prompt_template(context, query):
    return f"""
    You are a knowledgeable assistant specializing in the Across protocol and its related technologies.

    Based on the relevant documentation provided below, please answer the user's query concisely and accurately.

    Context:
    {context}

    User Query:
    {query}

    Your response should be clear, informative, and directly address the user's question, leveraging the context.
    """
