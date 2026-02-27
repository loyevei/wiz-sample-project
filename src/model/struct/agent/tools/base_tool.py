# =============================================================================
# BaseTool — Agent Tool 추상 클래스
# =============================================================================

class BaseTool:
    name = ""
    description = ""
    input_schema = {}

    def __init__(self, agent_context):
        self.ctx = agent_context

    def execute(self, **kwargs):
        raise NotImplementedError

    def to_openai_tool(self):
        """OpenAI Function Calling 형식의 Tool 스키마 반환"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            }
        }
