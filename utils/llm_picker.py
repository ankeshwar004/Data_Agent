from langchain.chat_models import ChatOpenAI, ChatAnthropic, ChatVertexAI


def get_llm(level: str):
    
    level=level.lower()
    
    if level == "low":
        return ChatOpenAI(model_name="gpt-4", temperature=0)
    elif level == "medium":
        return ChatAnthropic(model_name="claude-v1", temperature=0)
    elif level == "high":
        return ChatVertexAI(model_name="chat-bison", temperature=0)
    else:
        raise ValueError(f"Invalid LLM level: {level}")