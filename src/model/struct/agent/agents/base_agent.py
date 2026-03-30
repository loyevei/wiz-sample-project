# =============================================================================
# BaseAgent — 모든 서브 에이전트의 공통 인터페이스
# =============================================================================

class BaseAgent:
    """모든 서브 에이전트가 상속하는 기본 클래스.

    Attributes:
        name: 에이전트 식별자 (예: "keyword", "router")
        description: 에이전트 역할 설명
        ctx: 공유 컨텍스트 dict (wiz, config, struct, collection, tools 등)
    """

    name = ""
    description = ""

    def __init__(self, ctx):
        self.ctx = ctx

    def run(self, **kwargs):
        """서브 에이전트 실행. 반환값은 dict.
        
        각 서브 에이전트는 이 메서드를 오버라이드하여 고유 로직을 구현한다.
        """
        raise NotImplementedError

    def _llm_call(self, messages, max_tokens=1200, tools=None, tool_choice=None):
        """공통 OpenAI LLM 호출 래퍼."""
        client = self.ctx.get("client")
        model = self.ctx.get("model", "gpt-4o")
        if not client:
            return None

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice or "auto"

        try:
            response = client.chat.completions.create(**kwargs)
            return response.choices[0].message
        except Exception:
            return None

    def _extract_json(self, text):
        """텍스트에서 JSON 객체 추출."""
        import json
        if not text:
            return None
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            return json.loads(text[start:end + 1])
        except Exception:
            return None
