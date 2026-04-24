import json
import os
import time
import season.lib.exception

def _load_agent_class():
    """Hot-load Agent class from the latest built source to avoid runtime cache issues.

    This enables applying Python changes via build without server restart.
    """
    hotload = wiz.model("hotload")
    return hotload.load_symbol("model/struct/agent.py", "Agent", name_prefix="wiz_hot_agent")


def _parse_history(history_str):
    try:
        return json.loads(history_str) if isinstance(history_str, str) else history_str
    except Exception:
        return []


def _safe_int(value, default, min_value=1, max_value=10):
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(min_value, min(max_value, parsed))


def _safe_float(value, default):
    try:
        return float(value)
    except Exception:
        return default


def _run_benchmark_trial(AgentClass, struct, provider, model_name, message, history, collection,
                         api_key="", temperature=None, top_p=None, max_tokens=None):
    started = time.time()
    agent = AgentClass(
        struct,
        collection=collection,
        provider=provider,
        model_name=model_name,
        api_key=api_key,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )

    final_text = ""
    first_text_ms = None
    first_event_ms = None
    tool_use_count = 0
    tool_result_count = 0
    error_message = ""
    completed = False
    events = []

    for event in agent.run(message, history=history):
        now = time.time()
        event_type = event.get("type", "") if isinstance(event, dict) else ""
        if first_event_ms is None:
            first_event_ms = round((now - started) * 1000, 2)
        events.append(event_type)

        if event_type == "text":
            if first_text_ms is None:
                first_text_ms = round((now - started) * 1000, 2)
            final_text = event.get("content", "") or final_text
        elif event_type == "tool_use":
            tool_use_count += 1
        elif event_type == "tool_result":
            tool_result_count += 1
        elif event_type == "error":
            error_message = event.get("message", "")
        elif event_type == "done":
            completed = True

    total_ms = round((time.time() - started) * 1000, 2)
    return {
        "provider": provider,
        "model": model_name,
        "completed": completed,
        "error": error_message,
        "total_ms": total_ms,
        "first_event_ms": first_event_ms,
        "first_text_ms": first_text_ms,
        "tool_use_count": tool_use_count,
        "tool_result_count": tool_result_count,
        "answer_chars": len(final_text or ""),
        "answer_preview": (final_text or "")[:400],
        "event_sequence": events,
    }


def _summarize_trials(provider, model_name, trials):
    success = [t for t in trials if t.get("completed") and not t.get("error")]

    def _avg(key):
        rows = [t.get(key) for t in success if t.get(key) is not None]
        if not rows:
            return None
        return round(sum(rows) / len(rows), 2)

    unique_answers = []
    seen = set()
    for trial in success:
        preview = (trial.get("answer_preview") or "").strip()
        if preview and preview not in seen:
            seen.add(preview)
            unique_answers.append(preview)

    return {
        "provider": provider,
        "model": model_name,
        "trials": len(trials),
        "success_count": len(success),
        "failure_count": len(trials) - len(success),
        "avg_total_ms": _avg("total_ms"),
        "avg_first_event_ms": _avg("first_event_ms"),
        "avg_first_text_ms": _avg("first_text_ms"),
        "avg_tool_use_count": _avg("tool_use_count"),
        "avg_tool_result_count": _avg("tool_result_count"),
        "avg_answer_chars": _avg("answer_chars"),
        "unique_answer_count": len(unique_answers),
        "sample_answers": unique_answers[:3],
        "last_error": next((t.get("error") for t in reversed(trials) if t.get("error")), ""),
    }

def agent_tools():
    """등록된 Tool 목록 반환"""
    struct = wiz.model("struct")
    AgentClass = _load_agent_class()
    agent = AgentClass(struct)
    tools = agent.get_tools()
    wiz.response.status(200, tools)

def agent_chat():
    """SSE 스트리밍 Agent 채팅"""
    if wiz.request.query("mode", "") == "benchmark_compare":
        return benchmark_compare()

    flask = wiz.response._flask

    # Request Context 내에서 파라미터 추출 (generator 바깥)
    message = wiz.request.query("message", "")
    history_str = wiz.request.query("history", "[]")
    collection = wiz.request.query("collection", "")

    if not message.strip():
        wiz.response.status(400, message="message is required")

    # History 복원
    try:
        history = json.loads(history_str) if isinstance(history_str, str) else history_str
    except Exception:
        history = []

    # Agent 인스턴스 생성 (collection 전달) — hot-loaded to reflect latest build without restart
    struct = wiz.model("struct")
    AgentClass = _load_agent_class()
    agent = AgentClass(struct, collection=collection)

    # SSE Generator
    def generate():
        done_sent = False
        try:
            for event in agent.run(message, history=history):
                if not isinstance(event, dict):
                    continue
                if event.get("_type"):
                    continue  # 내부 제어 이벤트 무시
                if event.get("type") == "done":
                    done_sent = True
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)}, ensure_ascii=False)}\n\n"
        finally:
            try:
                final_history = agent.get_history()
            except Exception:
                final_history = history
            yield f"data: {json.dumps({'type': 'history', 'messages': final_history}, ensure_ascii=False)}\n\n"
            if not done_sent:
                yield f"data: {json.dumps({'type': 'done', 'content': ''}, ensure_ascii=False)}\n\n"

    resp = flask.Response(generate(), mimetype="text/event-stream")
    resp.headers["Cache-Control"] = "no-cache"
    resp.headers["X-Accel-Buffering"] = "no"
    wiz.response.response(resp)


def benchmark_compare():
    """Local Gemma vs GPT-4.1 A/B 벤치마크."""
    message = wiz.request.query("message", "안녕하세요. 간단히 자기소개 해주세요.")
    history = _parse_history(wiz.request.query("history", "[]"))
    collection = wiz.request.query("collection", "")
    trials = _safe_int(wiz.request.query("trials", 5), 5, min_value=1, max_value=5)
    temperature = _safe_float(wiz.request.query("temperature", 0.2), 0.2)
    top_p = _safe_float(wiz.request.query("top_p", 0.9), 0.9)
    max_tokens = _safe_int(wiz.request.query("max_tokens", 2400), 2400, min_value=64, max_value=4000)

    config = wiz.config("season")
    local_model = wiz.request.query("local_model", getattr(config, "local_model_name", "google/gemma-4-26B-A4B-it"))
    openai_model = wiz.request.query("openai_model", getattr(config, "openai_model", "gpt-4.1"))
    openai_api_key = (
        wiz.request.query("openai_api_key", "")
        or getattr(config, "openai_api_key", "")
        or os.environ.get("OPENAI_API_KEY", "")
    )

    struct = wiz.model("struct")
    AgentClass = _load_agent_class()

    local_trials = []
    for _ in range(trials):
        local_trials.append(_run_benchmark_trial(
            AgentClass,
            struct,
            provider="local",
            model_name=local_model,
            message=message,
            history=history,
            collection=collection,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        ))

    local_summary = _summarize_trials("local", local_model, local_trials)

    openai_trials = []
    openai_summary = {
        "provider": "openai",
        "model": openai_model,
        "trials": trials,
        "success_count": 0,
        "failure_count": trials,
        "avg_total_ms": None,
        "avg_first_event_ms": None,
        "avg_first_text_ms": None,
        "avg_tool_use_count": None,
        "avg_tool_result_count": None,
        "avg_answer_chars": None,
        "unique_answer_count": 0,
        "sample_answers": [],
        "last_error": "OpenAI API key가 없어 GPT 벤치마크를 건너뛰었습니다.",
        "skipped": True,
    }

    if openai_api_key:
        for _ in range(trials):
            openai_trials.append(_run_benchmark_trial(
                AgentClass,
                struct,
                provider="openai",
                model_name=openai_model,
                message=message,
                history=history,
                collection=collection,
                api_key=openai_api_key,
                temperature=temperature,
                top_p=top_p,
                max_tokens=max_tokens,
            ))
        openai_summary = _summarize_trials("openai", openai_model, openai_trials)
        openai_summary["skipped"] = False

    comparison = {
        "message": message,
        "collection": collection,
        "trials": trials,
        "temperature": temperature,
        "top_p": top_p,
        "max_tokens": max_tokens,
        "local": {
            "summary": local_summary,
            "trials": local_trials,
        },
        "openai": {
            "summary": openai_summary,
            "trials": openai_trials,
        },
    }
    wiz.response.status(200, comparison)
