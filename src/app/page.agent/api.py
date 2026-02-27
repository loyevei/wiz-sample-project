import json
import season.lib.exception

struct = wiz.model("struct")

def agent_tools():
    """등록된 Tool 목록 반환"""
    agent = struct.agent()
    tools = agent.get_tools()
    wiz.response.status(200, tools)

def agent_chat():
    """SSE 스트리밍 Agent 채팅"""
    flask = wiz.response._flask

    # Request Context 내에서 파라미터 추출 (generator 바깥)
    message = wiz.request.query("message", "")
    history_str = wiz.request.query("history", "[]")

    if not message.strip():
        wiz.response.status(400, message="message is required")

    # History 복원
    try:
        history = json.loads(history_str) if isinstance(history_str, str) else history_str
    except Exception:
        history = []

    # Agent 인스턴스 생성
    agent = struct.agent()

    # SSE Generator
    def generate():
        try:
            for event in agent.run(message, history=history):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            # 루프 종료 후 최종 히스토리 전달
            final_history = agent.get_history()
            yield f"data: {json.dumps({'type': 'history', 'messages': final_history}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)
