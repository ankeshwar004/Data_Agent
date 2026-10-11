def get_llm(level: str):
    level=level.lower()
    
    if level == "low":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o-mini", temperature=0)
    elif level == "medium":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o", temperature=0)
    elif level == "high":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    else:
        raise ValueError(f"Invalid LLM level: {level}")