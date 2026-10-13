import config

def get_llm(level: str):
    level=level.lower()
    
    if level == "low":
        from langchain_openrouter import ChatOpenRouter

        return ChatOpenRouter(model="nvidia/nemotron-3-ultra-550b-a55b:free", temperature=0, api_key=config.OPENROUTER_API_KEY)
    elif level == "medium":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4o", temperature=0)
    elif level == "high":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-sonnet-4-20250514", temperature=0)
    else:
        raise ValueError(f"Invalid LLM level: {level}")