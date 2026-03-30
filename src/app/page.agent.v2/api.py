import json
import season.lib.exception


def _load_agent_class():
    """Hot-load Agent class from the latest built source to avoid runtime cache issues."""
    hotload = wiz.model("hotload")
    return hotload.load_symbol("model/struct/agent.py", "Agent", name_prefix="wiz_hot_agent")


def agent_chat():
    """SSE 스트리밍 Agent 채팅 (v2)"""
    flask = wiz.response._flask

    message = wiz.request.query("message", "")
    history_str = wiz.request.query("history", "[]")
    collection = wiz.request.query("collection", "")

    if not message.strip():
        wiz.response.status(400, message="message is required")

    try:
        history = json.loads(history_str) if isinstance(history_str, str) else history_str
    except Exception:
        history = []

    struct = wiz.model("struct")
    AgentClass = _load_agent_class()
    agent = AgentClass(struct, collection=collection)

    def generate():
        try:
            for event in agent.run(message, history=history):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
            final_history = agent.get_history()
            yield f"data: {json.dumps({'type': 'history', 'messages': final_history}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)
