# =============================================================================
# Local LLM — transformers 기반 로컬 모델 래퍼 (OpenAI client 호환 인터페이스)
# =============================================================================
# OpenAI client.chat.completions.create() 와 동일한 인터페이스를 제공하여
# 기존 코드 변경을 최소화한다. API 서버 없이 모델을 직접 메모리에 로딩.
# =============================================================================

import gc
import json
import os
import sys
import time
import uuid
import threading

# HuggingFace 캐시 디렉토리 (모델 다운로드 위치)
_HF_CACHE_DIR = "/opt/app/data/models"
_DEFAULT_MODEL_ID = "google/gemma-4-26B-A4B-it"
_MAX_CONTEXT = 32768  # 안전한 최대 컨텍스트 (Gemma 4는 128K 지원, VRAM 절약을 위해 32K 사용)
_VERSION = 15  # 변경 시 기존 모델을 자동 해제 후 재로딩
_GPU_MEMORY = "22GiB"
_INT4_GROUP_SIZE = 128

_model = None
_tokenizer = None
_lock = threading.Lock()
_loaded = False


def _patch_rocm_moe():
    """ROCm에서 grouped_mm이 지원되지 않으므로 fallback 강제."""
    try:
        import transformers.integrations.moe as _moe
        _moe._can_use_grouped_mm = lambda *a, **k: False
    except Exception:
        pass


def _patch_bnb_params():
    """bitsandbytes 0.49.x + transformers 5.x 호환 패치.
    transformers가 _is_hf_initialized kwarg를 전달하지만 bnb가 모름."""
    try:
        import bitsandbytes as bnb
        for cls_name in ('Params4bit', 'Int8Params'):
            cls = getattr(bnb.nn, cls_name, None)
            if cls is None:
                continue
            orig_new = cls.__new__
            if getattr(orig_new, '_patched', False):
                continue
            def _make_patched(orig):
                def patched_new(cls_, *args, **kwargs):
                    kwargs.pop('_is_hf_initialized', None)
                    return orig(cls_, *args, **kwargs)
                patched_new._patched = True
                return patched_new
            cls.__new__ = _make_patched(orig_new)
    except Exception:
        pass


def _cleanup():
    """기존 모델 메모리 해제 (GPU + CPU). accelerate hooks까지 제거."""
    global _model, _tokenizer, _loaded, _client_instance
    import torch
    if _model is not None:
        # accelerate dispatch hooks 제거 (참조 유지 방지)
        try:
            from accelerate.hooks import remove_hook_from_submodules
            remove_hook_from_submodules(_model)
        except Exception:
            pass
        # tied weights 해제
        try:
            _model.tie_weights = lambda: None
        except Exception:
            pass
        del _model
    _model = None
    if _tokenizer is not None:
        del _tokenizer
    _tokenizer = None
    _loaded = False
    _client_instance = None
    # 여러 번 GC 수행 (순환 참조 해제)
    for _ in range(5):
        gc.collect()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
        torch.cuda.empty_cache()


# =========================================================================
# MoE Expert int4 수동 양자화 (Gemma4TextExperts 3D 텐서 대상)
# quanto는 nn.Linear만 양자화하므로, 3D Parameter로 저장된 MoE expert 가중치는
# 수동으로 int4 패킹/언패킹을 구현한다.
# =========================================================================
def _pack_int4(tensor_2d, group_size=_INT4_GROUP_SIZE):
    """2D bf16 텐서를 symmetric int4로 양자화, uint8로 패킹."""
    import torch
    rows, cols = tensor_2d.shape
    pad_cols = (cols + group_size - 1) // group_size * group_size
    if pad_cols != cols:
        tensor_2d = torch.nn.functional.pad(tensor_2d, (0, pad_cols - cols))
    num_groups = pad_cols // group_size
    grouped = tensor_2d.reshape(rows, num_groups, group_size)
    scales = grouped.abs().amax(dim=-1, keepdim=True).clamp(min=1e-8) / 7.0
    quantized = (grouped / scales).round().clamp(-8, 7).to(torch.int8).reshape(rows, pad_cols)
    even = (quantized[:, 0::2] + 8).to(torch.uint8)
    odd = (quantized[:, 1::2] + 8).to(torch.uint8)
    packed = (odd << 4) | even
    return packed, scales.squeeze(-1).to(torch.bfloat16)


def _unpack_int4(packed, scales, orig_cols, group_size=_INT4_GROUP_SIZE):
    """int4 패킹된 텐서를 bf16으로 복원 (단일 expert 2D 슬라이스용)."""
    import torch
    rows, half_cols = packed.shape
    pad_cols = half_cols * 2
    lo = (packed & 0x0F).to(torch.int8) - 8
    hi = (packed >> 4).to(torch.int8) - 8
    unpacked = torch.stack([lo, hi], dim=-1).reshape(rows, pad_cols)
    num_groups = pad_cols // group_size
    grouped = unpacked.reshape(rows, num_groups, group_size).float()
    result = (grouped * scales.unsqueeze(-1).float()).reshape(rows, pad_cols)
    return result[:, :orig_cols].to(torch.bfloat16)


def _quantize_experts(model):
    """Gemma4TextExperts의 3D Parameter를 int4 buffer로 교체."""
    import torch
    try:
        from transformers.models.gemma4.modeling_gemma4 import Gemma4TextExperts
    except ImportError:
        return

    for name, module in model.named_modules():
        if not isinstance(module, Gemma4TextExperts):
            continue

        # gate_up_proj [num_experts, 2*intermediate, hidden]
        gu = module.gate_up_proj.data
        p_list, s_list = [], []
        for i in range(module.num_experts):
            p, s = _pack_int4(gu[i])
            p_list.append(p)
            s_list.append(s)
        module.register_buffer('_gu_packed', torch.stack(p_list))
        module.register_buffer('_gu_scales', torch.stack(s_list))
        module._gu_orig_cols = gu.shape[2]
        del p_list, s_list, gu
        if 'gate_up_proj' in module._parameters:
            del module._parameters['gate_up_proj']
        gc.collect()

        # down_proj [num_experts, hidden, intermediate]
        dp = module.down_proj.data
        p_list, s_list = [], []
        for i in range(module.num_experts):
            p, s = _pack_int4(dp[i])
            p_list.append(p)
            s_list.append(s)
        module.register_buffer('_dp_packed', torch.stack(p_list))
        module.register_buffer('_dp_scales', torch.stack(s_list))
        module._dp_orig_cols = dp.shape[2]
        del p_list, s_list, dp
        if 'down_proj' in module._parameters:
            del module._parameters['down_proj']
        gc.collect()

    # Forward 패치 (int4 dequantize 사용)
    Gemma4TextExperts.forward = _patched_experts_forward


def _patched_experts_forward(self, hidden_states, top_k_index, top_k_weights):
    """int4 양자화된 expert 가중치를 사용하는 forward (활성 expert만 dequantize)."""
    import torch
    final_hidden_states = torch.zeros_like(hidden_states)
    with torch.no_grad():
        expert_mask = torch.nn.functional.one_hot(top_k_index, num_classes=self.num_experts)
        expert_mask = expert_mask.permute(2, 1, 0)
        expert_hit = torch.greater(expert_mask.sum(dim=(-1, -2)), 0).nonzero()

    for expert_idx in expert_hit:
        expert_idx = expert_idx[0]
        if expert_idx == self.num_experts:
            continue
        top_k_pos, token_idx = torch.where(expert_mask[expert_idx])
        current_state = hidden_states[token_idx]

        gu_w = _unpack_int4(self._gu_packed[expert_idx], self._gu_scales[expert_idx], self._gu_orig_cols)
        gate, up = torch.nn.functional.linear(current_state, gu_w).chunk(2, dim=-1)
        del gu_w
        current_hidden_states = self.act_fn(gate) * up

        dp_w = _unpack_int4(self._dp_packed[expert_idx], self._dp_scales[expert_idx], self._dp_orig_cols)
        current_hidden_states = torch.nn.functional.linear(current_hidden_states, dp_w)
        del dp_w
        current_hidden_states = current_hidden_states * top_k_weights[token_idx, top_k_pos, None]
        final_hidden_states.index_add_(0, token_idx, current_hidden_states.to(final_hidden_states.dtype))

    return final_hidden_states


def _load_model(model_path):
    global _model, _tokenizer, _loaded
    if _loaded:
        return
    with _lock:
        if _loaded:
            return
        import torch
        from transformers import AutoTokenizer, AutoModelForCausalLM

        _patch_rocm_moe()

        # 이전 실패한 로딩에서 남은 VRAM 정리
        for attr in ('last_traceback', 'last_value', 'last_type'):
            if hasattr(sys, attr):
                try:
                    setattr(sys, attr, None)
                except Exception:
                    pass
        for _ in range(5):
            gc.collect()
        if torch.cuda.is_available():
            torch.cuda.synchronize()
            torch.cuda.empty_cache()

        # 1단계: CPU에 bf16 모델 로드
        _tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        _model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.bfloat16,
            device_map="cpu",
            low_cpu_mem_usage=True,
            trust_remote_code=True,
        )

        # 2단계: MoE expert 3D 가중치를 int4로 수동 양자화 (~47GB → ~12.5GB)
        _quantize_experts(_model)

        # 3단계: CPU 메모리 정리 후 GPU 이동
        # Expert int4 packed (~12.5GB) + 나머지 bf16 (~4.4GB) ≈ 17GB → GPU 24GB에 충분
        for _ in range(3):
            gc.collect()
        _model = _model.to("cuda:0")
        _model.eval()
        _loaded = True


# =========================================================================
# OpenAI-compatible response objects (dot-access)
# =========================================================================
class _DotDict:
    def __init__(self, d):
        for k, v in d.items():
            if isinstance(v, dict):
                setattr(self, k, _DotDict(v))
            elif isinstance(v, list):
                setattr(self, k, [_DotDict(i) if isinstance(i, dict) else i for i in v])
            else:
                setattr(self, k, v)

    def __getattr__(self, name):
        return None

    def get(self, key, default=None):
        return getattr(self, key, default)


class _ToolCall:
    def __init__(self, d):
        self.id = d.get("id", "")
        self.type = d.get("type", "function")
        fn = d.get("function", {})
        self.function = _DotDict({
            "name": fn.get("name", ""),
            "arguments": fn.get("arguments", "{}"),
        })


class _Message:
    def __init__(self, role="assistant", content="", tool_calls=None):
        self.role = role
        self.content = content
        self.tool_calls = tool_calls  # list[_ToolCall] or None


class _Choice:
    def __init__(self, message, finish_reason="stop"):
        self.index = 0
        self.message = message
        self.finish_reason = finish_reason
        # streaming delta
        self.delta = message


class _Usage:
    def __init__(self, prompt_tokens=0, completion_tokens=0):
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = prompt_tokens + completion_tokens


class _ChatCompletion:
    def __init__(self, choices, usage, model="local"):
        self.id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        self.object = "chat.completion"
        self.created = int(time.time())
        self.model = model
        self.choices = choices
        self.usage = usage


# =========================================================================
# Core generation
# =========================================================================
def _build_chat(messages, tools=None):
    """messages와 tools를 chat 템플릿 형식으로 변환."""
    chat = []
    for m in messages:
        role = m.get("role", "user") if isinstance(m, dict) else getattr(m, "role", "user")
        content = m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
        chat.append({"role": role, "content": content or ""})

    # tools가 있으면 system prompt에 tool 설명 추가
    if tools and chat and chat[0].get("role") == "system":
        tool_desc = "\n\nYou have access to the following tools. To use a tool, output a JSON block like:\n<tool_call>\n{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}\n</tool_call>\n\nAvailable tools:\n"
        for t in tools:
            fn = t.get("function", {}) if isinstance(t, dict) else {}
            tool_desc += f"- {fn.get('name', '')}: {fn.get('description', '')}\n"
        chat[0]["content"] = (chat[0]["content"] or "") + tool_desc

    return chat


def _get_input_device():
    """모델이 위치한 디바이스 반환."""
    if hasattr(_model, "hf_device_map"):
        devices = list(_model.hf_device_map.values())
        if devices:
            dev = devices[0]
            if isinstance(dev, int):
                import torch
                return torch.device(f"cuda:{dev}")
            elif dev == "cpu":
                import torch
                return torch.device("cpu")
            return dev
    # 단일 디바이스 (int4 양자화 후 전체 GPU)
    try:
        return next(_model.parameters()).device
    except StopIteration:
        # quanto 양자화 후 parameters가 비어있을 수 있음 → buffers에서 확인
        for buf in _model.buffers():
            return buf.device
    return _model.device


def _generate_text(messages, max_tokens=2048, temperature=0.7, top_p=0.9, tools=None):
    """transformers 기반 텍스트 생성."""
    import torch

    chat = _build_chat(messages, tools)

    prompt = _tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
    input_device = _get_input_device()
    inputs = _tokenizer(prompt, return_tensors="pt").to(input_device)
    prompt_len = inputs["input_ids"].shape[-1]

    available = _MAX_CONTEXT - prompt_len
    if available < 64:
        # 프롬프트가 너무 길면 잘라서 재시도
        inputs["input_ids"] = inputs["input_ids"][:, -(_MAX_CONTEXT - max_tokens):]
        if "attention_mask" in inputs:
            inputs["attention_mask"] = inputs["attention_mask"][:, -(_MAX_CONTEXT - max_tokens):]
        prompt_len = inputs["input_ids"].shape[-1]
        available = _MAX_CONTEXT - prompt_len

    gen_kwargs = {
        "max_new_tokens": min(max_tokens, max(available, 64)),
        "do_sample": temperature > 0,
        "top_p": top_p,
    }
    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    with torch.no_grad():
        output_ids = _model.generate(**inputs, **gen_kwargs)

    new_ids = output_ids[0][prompt_len:]
    text = _tokenizer.decode(new_ids, skip_special_tokens=True)
    return text, prompt_len, len(new_ids)


def _stream_generate_text(messages, max_tokens=2048, temperature=0.7, top_p=0.9, tools=None):
    """토큰 단위 스트리밍 생성기."""
    import torch
    from transformers import TextIteratorStreamer

    chat = _build_chat(messages, tools)

    prompt = _tokenizer.apply_chat_template(chat, tokenize=False, add_generation_prompt=True)
    input_device = _get_input_device()
    inputs = _tokenizer(prompt, return_tensors="pt").to(input_device)
    prompt_len = inputs["input_ids"].shape[-1]

    available = _MAX_CONTEXT - prompt_len
    if available < 64:
        inputs["input_ids"] = inputs["input_ids"][:, -(_MAX_CONTEXT - max_tokens):]
        if "attention_mask" in inputs:
            inputs["attention_mask"] = inputs["attention_mask"][:, -(_MAX_CONTEXT - max_tokens):]
        prompt_len = inputs["input_ids"].shape[-1]
        available = _MAX_CONTEXT - prompt_len

    streamer = TextIteratorStreamer(_tokenizer, skip_prompt=True, skip_special_tokens=True)

    gen_kwargs = {
        **inputs,
        "max_new_tokens": min(max_tokens, max(available, 64)),
        "do_sample": temperature > 0,
        "top_p": top_p,
        "streamer": streamer,
    }
    if temperature > 0:
        gen_kwargs["temperature"] = temperature

    def _run_generate():
        try:
            with torch.no_grad():
                _model.generate(**gen_kwargs)
        except Exception:
            pass

    thread = threading.Thread(target=_run_generate)
    thread.start()

    for text_chunk in streamer:
        yield text_chunk

    thread.join()


# =========================================================================
# Tool call 파싱 (모델이 JSON으로 tool call을 출력한 경우)
# =========================================================================
def _parse_tool_calls(text, tools_schema):
    """모델 출력에서 tool_call JSON을 파싱 시도."""
    if not tools_schema or not text:
        return None, text

    # 모델이 <tool_call> 또는 ```json 형태로 tool call을 출력하는 패턴
    import re
    patterns = [
        r'<tool_call>\s*(\{.*?\})\s*</tool_call>',
        r'```json\s*(\{.*?\})\s*```',
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(1))
                if "name" in data and "arguments" in data:
                    tc = _ToolCall({
                        "id": f"call_{uuid.uuid4().hex[:8]}",
                        "type": "function",
                        "function": {
                            "name": data["name"],
                            "arguments": json.dumps(data["arguments"]) if isinstance(data["arguments"], dict) else str(data["arguments"]),
                        },
                    })
                    remaining = text[:match.start()] + text[match.end():]
                    return [tc], remaining.strip()
            except (json.JSONDecodeError, KeyError):
                pass
    return None, text


# =========================================================================
# OpenAI-compatible Client class
# =========================================================================
class _Completions:
    def __init__(self, model_name):
        self.model_name = model_name

    def create(self, model=None, messages=None, max_tokens=2048,
               temperature=0.7, top_p=0.9, stream=False,
               tools=None, tool_choice=None, **kwargs):
        messages = messages or []
        model = model or self.model_name

        if stream:
            return self._stream(messages, max_tokens, temperature, top_p, tools=tools)

        text, prompt_tokens, completion_tokens = _generate_text(
            messages, max_tokens, temperature, top_p, tools=tools
        )

        # tool call 파싱 시도
        tool_calls, content = _parse_tool_calls(text, tools)

        msg = _Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls,
        )

        return _ChatCompletion(
            choices=[_Choice(msg)],
            usage=_Usage(prompt_tokens, completion_tokens),
            model=model,
        )

    def _stream(self, messages, max_tokens, temperature, top_p, tools=None):
        """스트리밍 제너레이터 — OpenAI SSE chunk 호환."""
        request_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
        created = int(time.time())

        for chunk_text in _stream_generate_text(messages, max_tokens, temperature, top_p, tools=tools):
            yield _ChatCompletion(
                choices=[_Choice(_Message(content=chunk_text), finish_reason=None)],
                usage=_Usage(),
                model=self.model_name,
            )

        # final chunk
        yield _ChatCompletion(
            choices=[_Choice(_Message(content=""), finish_reason="stop")],
            usage=_Usage(),
            model=self.model_name,
        )


class _Chat:
    def __init__(self, model_name):
        self.completions = _Completions(model_name)


class LocalLLMClient:
    """OpenAI client 드롭인 대체. client.chat.completions.create() 호환."""

    def __init__(self, model_path, model_name="google/gemma-4-26B-A4B-it"):
        self.model_path = model_path
        self.model_name = model_name
        self.chat = _Chat(model_name)
        # 모델 로딩 (최초 1회)
        _load_model(model_path)


# =========================================================================
# Singleton factory
# =========================================================================
_client_instance = None
_client_lock = threading.Lock()


def _resolve_model_path(config_path):
    """config에서 받은 경로가 유효하면 사용, 아니면 HF 캐시에서 자동 검색."""
    if config_path and os.path.isdir(config_path):
        return config_path
    # HF cache 구조: models--{org}--{name}/snapshots/{hash}/
    safe_id = _DEFAULT_MODEL_ID.replace("/", "--")
    snapshots_dir = os.path.join(_HF_CACHE_DIR, f"models--{safe_id}", "snapshots")
    if os.path.isdir(snapshots_dir):
        snaps = sorted(os.listdir(snapshots_dir))
        if snaps:
            return os.path.join(snapshots_dir, snaps[-1])
    return ""


def get_client(config=None):
    """config에서 모델 경로를 읽어 싱글톤 LocalLLMClient 반환."""
    global _client_instance
    if _client_instance is not None:
        return _client_instance

    with _client_lock:
        if _client_instance is not None:
            return _client_instance

        config_path = getattr(config, "local_model_path", "") if config else ""
        model_name = getattr(config, "local_model_name", _DEFAULT_MODEL_ID) if config else _DEFAULT_MODEL_ID

        model_path = _resolve_model_path(config_path)
        if not model_path:
            raise ValueError("config/season.py에 local_model_path를 설정하세요.")

        _client_instance = LocalLLMClient(model_path, model_name)
        return _client_instance


Model = None  # WIZ model 규칙: 이 파일은 get_client() 팩토리로 사용
