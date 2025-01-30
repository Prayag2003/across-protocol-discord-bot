def generate_announce_prompt_template(context, query, detail_level="detailed"):
    output_instruction = {
        "brief": "Summarize the most relevant announcement concisely.",
        "standard": "Provide a clear response based on the most relevant and recent announcements.",
        "detailed": "Provide a detailed explanation, elaborating on relevant announcements and their context."
    }.get(detail_level, "Provide a clear response based on the most relevant and recent announcements.")

    user_prompt = (
        f"Context from Announcements:\n{context}\n\n"
        f"User Query:\n{query}\n\n"
        f"Based on these announcements, please provide a relevant response to the user's query. "
        f"Important notes:\n"
        f"1. Recent announcements carry more weight and may override older information.\n"
        f"2. If conflicting statements exist, prioritize the most recent one.\n"
        f"3. Provide specific details and timestamps when possible to offer clear context.\n"
        f"4. If the announcements lack relevant details, explicitly mention this.\n"
        f"\n{output_instruction}"
    )

    system_prompt = """You are a helpful discord bot assistant that provides information about announcements. 
            Your task is to:
            1. Always prefer latest announcements as per time stamp to give accurate results. Take this very seriously.
            2. The results must not be ambiguous.
            3. Answer questions about announcements, events, updates, and news.
            4. Always prioritize the most recent information, as it represents the current state.
            5. When discussing status updates or changes, explicitly mention the latest known state.
            6. Include relevant timestamps to provide context about when information was announced.
            7. If there are conflicting announcements, explain the timeline and current status.
            8. If no announcements match the query, clearly state that.
            
            Always maintain a helpful and informative tone while ensuring users understand the current state of affairs."""

    return [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
