def get_llm(level: str):
    level=level.lower()
    
    if level == "low":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(model="gpt-4", temperature=0)
    elif level == "medium":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model="claude-v1", temperature=0)
    elif level == "high":
        from langchain_google_vertexai import ChatVertexAI

        return ChatVertexAI(model_name="chat-bison", temperature=0)
    else:
        raise ValueError(f"Invalid LLM level: {level}")