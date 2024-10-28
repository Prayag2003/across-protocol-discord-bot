def get_role_specific_template(role):
    """Define a role-specific system message with strict KB adherence and minimal external assumptions."""
    if role == "developer":
        return """You are a highly skilled developer assistant with expertise in Across protocol. Follow these guidelines:
        - Use the knowledge base strictly as the primary source of truth.
        - Avoid assuming knowledge outside of the KB.
        - Provide production-ready code adhering to best practices, with inline comments and structured documentation.
        - Use KB content to address context cues and avoid adding creative assumptions outside the KB."""
    
    elif role == "admin":
        return """You are an administrative assistant specializing in Across protocol operations and configurations. Your approach should focus on:
        - Ensuring all responses derive strictly from KB content.
        - Providing configuration details, protocol rules, and policy insights only from verified KB information.
        - Minimizing external explanations, focusing on KB-specific instructions and guidelines only."""
    
    else:  # Default to general user
        return """You are a knowledgeable Across protocol assistant. Respond to user queries as follows:
        - Use the KB as your sole source of truth for information.
        - Break down technical concepts into digestible explanations without adding creative assumptions.
        - Refer only to KB content, ensuring accuracy and adherence to the source material."""

def detect_query_type(query):
    """Identify if the query requires a code-based response."""
    code_indicators = [
        'code', 'function', 'implement', 'write', 'program',
        'syntax', 'debug', 'error', 'example', 'script',
        'development', 'api', 'integration'
    ]
    return any(indicator in query.lower() for indicator in code_indicators)

def generate_prompt_template(context, query, role="user", detail_level="standard"):
    """Generate a prompt template with strict KB adherence, adaptable for role, query type, and response depth."""
    
    is_code_query = detect_query_type(query)
    system_message = get_role_specific_template(role)
    
    # Define the output detail instruction based on the detail level requested.
    output_instruction = {
        "brief": "Provide a concise response strictly using KB content.",
        "standard": "Provide a clear, context-specific response based strictly on KB content.",
        "detailed": "Provide an in-depth response strictly within the KB context, with comprehensive details and clarifications."
    }.get(detail_level, "Provide a clear, context-specific response strictly based on KB content.")

    # Define user-specific instructions for code or explanation responses.
    role_instruction = {
        "developer": "Craft a precise code solution or explanation based only on KB content, including inline comments and documentation references." if is_code_query else "Offer a technical explanation rooted in KB specifics, avoiding external examples.",
        "admin": "Provide KB-based configuration guidance or protocol references strictly within the KB scope." if not is_code_query else "Offer a KB-referenced code solution adhering to administrative standards.",
        "user": "Explain concepts or provide relevant context strictly using KB content, limiting the response to KB-verified information." if not is_code_query else "Provide a straightforward code solution derived solely from KB content."
    }.get(role, "Provide a clear, KB-based response without external references.")

    user_message = f"""Context from Knowledge Base:
    {context}

    User Query:
    {query}
    
    {role_instruction}

    {output_instruction}
    """
    
    # For debugging or review purposes, this can be printed.
    print(user_message)
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
