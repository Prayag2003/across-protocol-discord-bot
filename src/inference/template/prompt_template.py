def get_coding_template():
    """Enhanced coding template"""
    return """You are an expert developer focusing on the Across protocol implementation.
    Please provide practical, production-ready code solutions with:
    - Clear documentation and comments
    - Error handling and edge cases
    - Best practices and optimizations
    - Example usage where appropriate
    - References to specific documentation when available
    
    Focus on writing clean, maintainable code that follows industry standards."""

def get_explanation_template():
    """Enhanced explanation template"""
    return """You are a knowledgeable assistant specializing in the Across protocol and its related technologies.
    Please provide clear, informative responses that:
    - Break down complex concepts into understandable parts
    - Use analogies and examples where helpful
    - Focus on practical understanding
    - Address the core of the user's question
    - Cite specific sources when available
    - Synthesize information from multiple sources when relevant
    
    Aim to educate and clarify rather than just provide information."""

def detect_query_type(query):
    """Enhanced query type detection"""
    code_indicators = [
        'code', 'function', 'implement', 'write', 'program',
        'syntax', 'debug', 'error', 'example', 'script',
        'development', 'api', 'integration'
    ]
    
    query_lower = query.lower()
    return any(indicator in query_lower for indicator in code_indicators)

def generate_prompt_template(context, query):
    """Generate enhanced prompt template"""
    is_code_query = detect_query_type(query)
    
    system_message = get_coding_template() if is_code_query else get_explanation_template()
    
    user_message = f"""Context:
    {context}

    User Query:
    {query}
    
    {'Please provide a code solution with explanations and documentation references.' if is_code_query else 'Please explain this clearly and comprehensively using the provided context. Cite sources where possible.'}"""
    
    return [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]
