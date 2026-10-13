"""`translator.py`（v4 刮削线 S4）单测。

**零外网**：所有 HTTP 都由 `FakeOpener` 顶掉（`urllib.request.urlopen` 也被换成会炸的桩，
任何漏网的真实调用都会立刻失败）。API key 一律用假值，绝不出现真 key。

覆盖点（对齐任务硬性验收）：提示词四条铁律 + glossary 注入、代码块剥离、Key 归一比对、
三道校验器正反例、降级链（批量失败 → 单条 → 备用模型 → untranslated）、`content` 判空重试、
`max_tokens` 默认 ≥2000、缓存命中、缺配置 `selfcheck` 返回 `ok=False`、
5xx/429 退避重试、超时、机翻兜底开关、分批上限、`llm_conf` 覆盖与降级。
"""

import hashlib
import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest

PLUGIN_DIR = Path(__file__).resolve().parents[3] / "plugins.v3" / "avhelper"
_PKG = "avhelper_under_test"


def _load_translator():
    if _PKG not in sys.modules:
        import types

        pkg = types.ModuleType(_PKG)
        pkg.__path__ = [str(PLUGIN_DIR)]
        sys.modules[_PKG] = pkg
    key = f"{_PKG}.translator"
    if key in sys.modules:
        return sys.modules[key]
    spec = importlib.util.spec_from_file_location(key, PLUGIN_DIR / "translator.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[key] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def tr():
    return _load_translator()


# ---------------------------------------------------------------- 假 HTTP 工装

class FakeResp:
    """最小响应对象：`urlopen` 的 context manager + `.read()` + `.status`。"""

    def __init__(self, body, status=200):
        self._body = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.status = status

    def read(self, *a):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def reply(content, *, model="hy3", reasoning=None, finish="stop", usage=None):
    """构造一个 OpenAI 兼容的成功响应体。"""
    return {
        "id": "gen-test",
        "object": "chat.completion",
        "model": model,
        "choices": [{
            "index": 0,
            "finish_reason": finish,
            "message": {"role": "assistant", "content": content,
                        **({"reasoning_content": reasoning} if reasoning is not None else {})},
        }],
        "usage": usage if usage is not None else {
            "prompt_tokens": 120, "completion_tokens": 60, "total_tokens": 180},
    }


class FakeOpener:
    """按模型名分派的假 opener；每次调用记录 (model, max_tokens, messages)。"""

    def __init__(self):
        self.calls = []
        self.handlers = {}
        self.default_error = urllib.error.HTTPError(
            "http://gw/v1/chat/completions", 404, "Not Found", {},
            __import__("io").BytesIO(b'{"error":{"code":"model_not_found","message":"no"}}'))

    def on(self, model, fn):
        """`fn(n, body) -> dict | FakeResp | Exception`；`n` 是该模型的第几次调用（从 1 起）。"""
        self.handlers[model] = fn
        return self

    def on_json(self, model, payload_or_fn):
        def _fn(n, body):
            if callable(payload_or_fn):
                return reply(payload_or_fn(n, body), model=model)
            return reply(json.dumps(payload_or_fn, ensure_ascii=False) if isinstance(payload_or_fn, (dict, list))
                         else payload_or_fn, model=model)
        return self.on(model, _fn)

    def __call__(self, req, timeout):
        body = json.loads(req.data.decode("utf-8"))
        self.calls.append({
            "model": body.get("model"),
            "max_tokens": body.get("max_tokens"),
            "temperature": body.get("temperature"),
            "messages": body.get("messages"),
            "request": body,
            "timeout": timeout,
            "url": req.full_url,
            "auth": req.headers.get("Authorization") or req.headers.get("authorization"),
        })
        n = sum(1 for c in self.calls if c["model"] == body.get("model"))
        fn = self.handlers.get(body.get("model"))
        if fn is None:
            return self._raise(self.default_error)
        out = fn(n, body)
        if isinstance(out, Exception):
            return self._raise(out)
        if isinstance(out, FakeResp):
            return out
        return FakeResp(out)

    @staticmethod
    def _raise(exc):
        raise exc


@pytest.fixture()
def no_sleep(tr, monkeypatch):
    """退避睡眠改成 no-op，测试不许真等。"""
    slept = []
    monkeypatch.setattr(tr, "_sleep", lambda s: slept.append(s))
    return slept


@pytest.fixture(autouse=True)
def no_throttle(tr, monkeypatch):
    """调用间隔闸门也关掉（真跑会每条睡 1 s）。"""
    monkeypatch.setattr(tr, "_throttle", lambda: None)


@pytest.fixture()
def no_net(monkeypatch):
    """兜底闸门：真去联网就直接炸。"""
    def _boom(*a, **k):
        raise AssertionError("单测不允许真实网络调用")

    monkeypatch.setattr("urllib.request.urlopen", _boom)
    return _boom


FAKE_CONF = {"base_url": "http://gw.local:3065/v1", "api_key": "sk-fake-key",
             "model": "hy3", "fallback": "fb-model", "reasoning": "off",
             "temperature": "0"}

JP_TITLE = "【FANZA限定】地味OLが中年キ上司にバレた隠れエロボディ 雛形みくる"
JP_PLOT = ("VR専用の3D映像作品。至近距離で見つめ合い、耳元で囁かれながら濃厚なキスと愛撫を繰り返す。"
           "臨場感を追求した長回しの濡れ場が延々と続き、最後は顔面射精で幕を閉じる。")
ZH_PLOT_OK = "以超近距离对视、耳边低语中反复进行浓密的亲吻与爱抚，追求临场感的长镜头缠绵不断持续。"


def item(number, title=JP_TITLE, plot=None, glossary=None):
    return {"number": number, "title_jp": title, "plot_jp": plot, "glossary": glossary or {}}


# ================================================================ 常量与配置

class TestConstants:
    def test_contract_model_names(self, tr):
        assert tr.DEFAULT_MODEL == "hy3"
        assert tr.DEFAULT_FALLBACK == "deepseek-v4.1-flash"

    def test_max_tokens_default_at_least_2000(self, tr):
        """D20：hy3 会把 token 烧在 reasoning 上，默认值必须 ≥2000。"""
        assert tr.MAX_TOKENS_DEFAULT >= 2000
        assert tr._resolve_max_tokens(0) == tr.MAX_TOKENS_DEFAULT
        assert tr._resolve_max_tokens(-1) == tr.MAX_TOKENS_DEFAULT
        assert tr._resolve_max_tokens(None) == tr.MAX_TOKENS_DEFAULT
        assert tr._resolve_max_tokens(512) == 2000      # 夹到下限
        assert tr._resolve_max_tokens(4096) == 4096
        assert tr._resolve_max_tokens(10 ** 9) == tr.MAX_TOKENS_MAX

    def test_batch_limits(self, tr):
        assert (tr.BATCH_TITLE, tr.BATCH_PLOT) == (6, 3)

    def test_prompt_version_pinned_in_cache_key(self, tr):
        assert tr.PROMPT_VER  # 非空：提示词一改必须递增，缓存才失效

    def test_import_does_not_touch_host_or_network(self, tr):
        """模块 import 期不许联网/读配置：conf 里的 key 此刻应为空（本机无宿主配置）。"""
        assert isinstance(tr.llm_conf(), dict)


class TestLLMConf:
    def test_defaults_when_nothing_configured(self, tr, monkeypatch):
        monkeypatch.setattr(tr, "_host_setting", lambda *a, **k: tr._UNSET)
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_MODEL", raising=False)
        conf = tr.llm_conf()
        assert conf["model"] == "hy3"
        assert conf["fallback"] == "deepseek-v4.1-flash"
        assert conf["base_url"] == tr.DEFAULT_BASE_URL
        assert conf["api_key"] == ""

    def test_override_wins(self, tr, monkeypatch):
        monkeypatch.setattr(tr, "_host_setting", lambda *a, **k: tr._UNSET)
        conf = tr.llm_conf({"api_key": "sk-ovr", "base_url": "http://ovr:1/v1/",
                            "model": "m1", "fallback": "m2"})
        assert conf["base_url"] == "http://ovr:1/v1"
        assert conf["api_key"] == "sk-ovr"
        assert conf["model"] == "m1"
        assert conf["fallback"] == "m2"
        assert conf["reasoning"] == tr.DEFAULT_REASONING

    def test_reasoning_default_off_with_effort_none(self, tr):
        """REPORT-5 §9.2：默认关思考，请求体必须带 `reasoning_effort:"none"`。"""
        conf = dict(FAKE_CONF)
        assert tr.DEFAULT_REASONING == tr.REASONING_OFF
        assert tr.reasoning_effort(conf) == "none"
        opener = FakeOpener().on_json("hy3", '{"A":1}')
        tr.chat([{"role": "user", "content": "x"}], model="hy3", conf=conf, opener=opener)
        assert opener.calls[0]["request"]["reasoning_effort"] == "none"

    def test_reasoning_auto_omits_param(self, tr):
        conf = dict(FAKE_CONF, reasoning=tr.REASONING_AUTO)
        assert tr.reasoning_effort(conf) == ""
        opener = FakeOpener().on_json("hy3", '{"A":1}')
        tr.chat([{"role": "user", "content": "x"}], model="hy3", conf=conf, opener=opener)
        assert "reasoning_effort" not in opener.calls[0]["request"]

    def test_partial_conf_still_gets_defaults(self, tr, monkeypatch):
        """★ 回归：调用方手工拼的 conf 缺键时，必须补上默认值（含 reasoning）。

        踩过的真坑：直接 `c = conf or llm_conf()` → `reasoning` 静默变空 → 思考没关掉、
        耗时回到 30~50 s，而**没有任何异常或日志**。所以入口统一走 `resolve_conf()`。
        """
        monkeypatch.setattr(tr, "_host_setting", lambda *a, **k: tr._UNSET)
        monkeypatch.delenv("LLM_TRANSLATE_REASONING", raising=False)
        partial = {"base_url": "http://gw:1/v1", "api_key": "k", "model": "hy3",
                   "fallback": "fb-model"}
        resolved = tr.resolve_conf(partial)
        assert resolved["reasoning"] == tr.DEFAULT_REASONING
        assert resolved["temperature"] == "0.0"

        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "中文", "plot_zh": None}})
        tr.translate_batch([item("SNOS-380")], conf=partial, opener=opener)
        assert opener.calls[0]["request"]["reasoning_effort"] == "none"

    def test_resolve_conf_none_uses_module_conf(self, tr):
        assert "reasoning" in tr.resolve_conf(None)

    def test_reasoning_bad_value_falls_back_to_default(self, tr):
        conf = tr.llm_conf({"reasoning": "banana", "api_key": "k"})
        assert conf["reasoning"] == tr.DEFAULT_REASONING

    @pytest.mark.parametrize("raw,expected", [
        (None, 0.0), ("", 0.0), ("0", 0.0), ("0.3", 0.3), (2, 2.0),
        (-1, 0.0), (2.6, 2.0), (100, 2.0), ("abc", 0.0), (float("nan"), 0.0),
    ])
    def test_temperature_clamped_to_0_2(self, tr, raw, expected):
        """网关不校验也不夹取（实测 -1/100 都 200），必须自己夹到 [0,2]。"""
        assert tr._resolve_temperature(raw, FAKE_CONF) == expected

    def test_default_temperature_is_zero(self, tr):
        assert tr.CHAT_TEMPERATURE == 0.0
        opener = FakeOpener().on_json("hy3", '{"A":1}')
        tr.chat([{"role": "user", "content": "x"}], model="hy3", conf=dict(FAKE_CONF),
                opener=opener)
        assert opener.calls[0]["temperature"] == 0.0

    def test_env_wins_over_host(self, tr, monkeypatch):
        monkeypatch.setattr(tr, "_host_setting", lambda key, default=None: "host-value")
        monkeypatch.setenv("LLM_API_KEY", "sk-env")
        assert tr.llm_conf()["api_key"] == "sk-env"

    def test_host_setting_used_when_no_env(self, tr, monkeypatch):
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.setattr(tr, "_host_setting",
                            lambda key, default=None: {"LLM_API_KEY": "sk-host"}.get(key, default))
        assert tr.llm_conf()["api_key"] == "sk-host"

    def test_host_import_failure_is_swallowed(self, tr, monkeypatch):
        """宿主没有 `app.runtime.settings` 时必须静默降级，不许抛。"""
        monkeypatch.setitem(sys.modules, "app.runtime.settings", None)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        assert tr._host_setting("LLM_API_KEY", "") == ""
        assert tr.llm_conf()["api_key"] == ""

    def test_is_configured(self, tr):
        assert tr.is_configured(FAKE_CONF) is True
        assert tr.is_configured({**FAKE_CONF, "api_key": ""}) is False
        assert tr.is_configured({**FAKE_CONF, "base_url": ""}) is False
        assert tr.is_configured({**FAKE_CONF, "model": ""}) is False


# ================================================================ 解析

class TestParse:
    @pytest.mark.parametrize("text,expected", [
        ('{"A":1}', {"A": 1}),
        ('```json\n{"A":1}\n```', {"A": 1}),
        ('```\n{"A":1}\n```', {"A": 1}),
        ('好的，结果如下：\n```json\n{"A":1}\n```\n以上就是译文。', {"A": 1}),
        ('这是结果：{"A":1} 请查收', {"A": 1}),
        ('{"A":1}\n```', {"A": 1}),
        ('  {"A":1}  ', {"A": 1}),
    ])
    def test_strips_fence_and_prose(self, tr, text, expected):
        assert tr.parse_model_json(text) == expected

    @pytest.mark.parametrize("text", ["", "   ", None, "抱歉我做不到", "[1,2,3]", "``````"])
    def test_unparseable(self, tr, text):
        assert tr.parse_model_json(text) is None

    def test_strip_code_fence_direct(self, tr):
        assert tr.strip_code_fence("```json\n{}\n```") == "{}"
        assert tr.strip_code_fence("{}") == "{}"

    def test_normalize_key(self, tr):
        assert tr.normalize_key("SNOS-380") == "SNOS380"
        assert tr.normalize_key("snos-380") == "SNOS380"
        assert tr.normalize_key("SNOS_380") == "SNOS380"
        assert tr.normalize_key(" snos 380 ") == "SNOS380"
        assert tr.normalize_key(None) == ""

    def test_key_lookup_is_normalized(self, tr):
        obj = {"snos_380": {"title_zh": "中文"}}
        assert tr._entry_from_obj(obj, "SNOS-380")["title_zh"] == "中文"
        assert tr._entry_from_obj(obj, "CAWD-989") is None
        assert tr._entry_from_obj({"SNOS-380": "not-a-dict"}, "SNOS-380") is None
        assert tr._entry_from_obj(None, "SNOS-380") is None


# ================================================================ 提示词

class TestPrompt:
    def test_four_iron_rules_present(self, tr):
        sys_p = tr.system_prompt({})
        assert "严格合法的 JSON" in sys_p
        assert "顶层 Key 必须与输入的番号字符串完全一致" in sys_p
        assert "严禁自行音译" in sys_p
        assert "plot_zh 必须为 null" in sys_p
        assert "严禁输出任何解释、安全声明或道德说教" in sys_p

    def test_glossary_injected_into_system_prompt(self, tr):
        sys_p = tr.system_prompt({"橋本ありな": "新有菜"})
        assert "橋本ありな → 新有菜" in sys_p
        assert "必须严格替换" in sys_p

    def test_glossary_empty_is_explicit(self, tr):
        assert "本次没有需要强制的译名词条" in tr.system_prompt({})

    def test_glossary_injected_into_user_payload(self, tr):
        msgs = tr.build_messages([item("SNOS-380", glossary={"橋本ありな": "新有菜"})])
        assert [m["role"] for m in msgs] == ["system", "user"]
        payload = json.loads(msgs[1]["content"])
        assert payload["SNOS-380"]["actor_glossary"] == {"橋本ありな": "新有菜"}
        assert payload["SNOS-380"]["title_jp"] == JP_TITLE
        assert payload["SNOS-380"]["plot_jp"] is None

    def test_payload_key_is_display_number_not_index(self, tr):
        msgs = tr.build_messages([item("SNOS-380"), item("CAWD-989")])
        payload = json.loads(msgs[1]["content"])
        assert sorted(payload) == ["CAWD-989", "SNOS-380"]
        assert "0" not in payload and "1" not in payload

    def test_glossary_merged_across_batch(self, tr):
        msgs = tr.build_messages([
            item("A-1", glossary={"橋本ありな": "新有菜"}),
            item("A-2", glossary={"みながわ千遥": "皆川千遥"}),
        ])
        sys_p = msgs[0]["content"]
        assert "橋本ありな → 新有菜" in sys_p and "みながわ千遥 → 皆川千遥" in sys_p

    def test_blank_values_dropped(self, tr):
        payload = json.loads(tr.build_user_payload([
            {"number": "A-1", "title_jp": "x", "plot_jp": "   ", "glossary": {"": "中", "日": ""}},
            {"number": "", "title_jp": "y"},
        ]))
        assert list(payload) == ["A-1"]
        assert payload["A-1"]["plot_jp"] is None
        assert "actor_glossary" not in payload["A-1"]

    def test_literal_null_string_normalized(self, tr):
        payload = json.loads(tr.build_user_payload(
            [{"number": "A-1", "title_jp": "x", "plot_jp": "null"}]))
        assert payload["A-1"]["plot_jp"] is None


# ================================================================ 校验器

class TestValidatorRefuse:
    @pytest.mark.parametrize("word", [
        "抱歉", "无法翻译", "无法提供", "色情", "露骨", "成人", "违规",
        "Inappropriate", "rejected for security", "cannot fulfill", "I cannot",
        "敏感内容", "系统检测",
    ])
    def test_refuse_words_each(self, tr, word):
        text = "标题前缀 " + word + " 标题后缀"
        ok, why = tr.validate_entry({"title_zh": text, "plot_zh": None},
                                    {"number": "A-1", "plot_jp": None})
        assert ok is False and "拒译词" in why

    def test_gateway_refusal_text_hits_blacklist(self, tr):
        """网关审查的原话必须被黑名单兜住（REPORT-5 §3 的真实拦截文本）。"""
        gateway_text = "抱歉，系统检测到您当前输入的信息存在敏感内容，我无法响应您的请求，请检查后重新输入。"
        hits = tr.refuse_hits(gateway_text)
        assert "抱歉" in hits and "系统检测" in hits and "敏感内容" in hits

    def test_transport_block_message_hits_blacklist(self, tr):
        """备用模型被截断时拼进 JSON 的那句话也要能兜住。"""
        assert tr.refuse_hits('{"CAWD-989": {"Inappropriate input/output rejected for security reasons')

    def test_refuse_case_insensitive(self, tr):
        assert tr.check_refuse_words("I CANNOT do that")[0] is False
        assert tr.refuse_hits("inappropriate content") == ["Inappropriate"]

    def test_refuse_in_plot_also_caught(self, tr):
        ok, why = tr.validate_entry(
            {"title_zh": "正常标题", "plot_zh": "抱歉，我无法提供这段翻译"},
            {"number": "A-1", "plot_jp": JP_PLOT})
        assert ok is False and "拒译词" in why

    def test_clean_text_passes(self, tr):
        assert tr.check_refuse_words("正常的中文标题") == (True, "ok")


class TestTransportValidator:
    """第 0 道校验器（REPORT-5 §9.4）—— 专拦「HTTP 200 的假成功」。"""

    SRC = {"number": "SNOS-380", "title_jp": JP_TITLE, "plot_jp": None}

    def test_ok_requires_content_and_parsed(self, tr):
        res = {"ok": True, "content": '{"SNOS-380":{}}', "usage": {}, "finish_reason": "stop"}
        assert tr.transport_status(res, parsed={"SNOS-380": {}}, found_keys=["SNOS380"],
                                   expected_keys=["SNOS380"]) == "ok"

    def test_content_without_parsed_is_bad_json(self, tr):
        res = {"ok": True, "content": "半个 JSON", "usage": {}, "finish_reason": "stop"}
        assert tr.transport_status(res, parsed=None) == tr.TR_BAD_JSON

    def test_key_mismatch(self, tr):
        res = {"ok": True, "content": "{}", "usage": {}, "finish_reason": "stop"}
        assert tr.transport_status(res, parsed={"A": {}}, found_keys=["A"],
                                   expected_keys=["SNOS380"]) == tr.TR_KEY_MISMATCH

    def test_content_filter(self, tr):
        res = {"ok": False, "content": None, "usage": None,
               "finish_reason": "content_filter", "error": ""}
        assert tr.transport_status(res) == tr.TR_CONTENT_FILTER

    def test_gateway_block_usage_null(self, tr):
        """审查拦截：HTTP 200 + usage 整个为 null + 一句拒绝话术。"""
        res = {"ok": False, "content": None, "usage": None, "finish_reason": "stop",
               "error": ""}
        assert tr.transport_status(res) == tr.TR_GATEWAY_BLOCK

    def test_token_exhausted(self, tr):
        res = {"ok": False, "content": "", "usage": {"completion_tokens": 4096},
               "finish_reason": "length", "error": "空正文"}
        assert tr.transport_status(res) == tr.TR_TOKEN_EXHAUSTED

    def test_empty_content(self, tr):
        res = {"ok": False, "content": "", "usage": {}, "finish_reason": "stop",
               "error": ""}
        assert tr.transport_status(res) == tr.TR_EMPTY_CONTENT

    @pytest.mark.parametrize("err,expected", [
        ("model_not_found: 模型不存在: nope", "model_not_found"),
        ("invalid_api_key: Unauthorized", "invalid_api_key"),
    ])
    def test_model_level_errors(self, tr, err, expected):
        res = {"ok": False, "content": None, "usage": None, "finish_reason": None, "error": err}
        assert tr.transport_status(res) == expected

    def test_validate_entry_uses_transport(self, tr):
        entry = {"title_zh": "正常中文标题", "plot_zh": None,
                 "_transport": {"status": tr.TR_CONTENT_FILTER}}
        ok, why = tr.validate_entry(entry, self.SRC)
        assert ok is False and "审查拦截" in why

    def test_validate_entry_accepts_ok_and_partial(self, tr):
        for status in ("ok", "partial"):
            entry = {"title_zh": "正常中文标题", "plot_zh": None, "_transport": {"status": status}}
            assert tr.validate_entry(entry, self.SRC) == (True, "ok")

    def test_entries_without_transport_pass(self, tr):
        """缓存条目 / 机翻条目没有 `_transport`，不能被第 0 道误杀。"""
        assert tr.validate_entry({"title_zh": "正常中文标题", "plot_zh": None}, self.SRC)[0] is True

    def test_reason_text_is_chinese(self, tr):
        for status in (tr.TR_GATEWAY_BLOCK, tr.TR_CONTENT_FILTER, tr.TR_TOKEN_EXHAUSTED,
                       tr.TR_EMPTY_CONTENT, tr.TR_BAD_JSON, tr.TR_KEY_MISMATCH):
            assert tr.transport_reason(status) != status


class TestActorsPassthrough:
    """S3 覆盖率的补丁：返回里要告诉上层「本片哪些演员有中文名」。"""

    def test_normalize_actors(self, tr):
        out = tr.normalize_actors([{"name": "橋本ありな"}, {"name": "茉城まみ"}],
                                  {"橋本ありな": "新有菜"})
        assert out == [{"jp": "橋本ありな", "zh": "新有菜"}, {"jp": "茉城まみ", "zh": ""}]

    def test_normalize_actors_accepts_strings(self, tr):
        assert tr.normalize_actors(["橋本ありな"], {"橋本ありな": "新有菜"}) == \
            [{"jp": "橋本ありな", "zh": "新有菜"}]

    def test_no_glossary_means_all_japanese(self, tr):
        """查不到就保留日文 —— 绝不猜译（乱音译的名字用户搜不到）。"""
        out = tr.normalize_actors([{"name": "茉城まみ"}], {})
        assert out == [{"jp": "茉城まみ", "zh": ""}]

    def test_actors_ride_along_in_result(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "中文标题", "plot_zh": None}})
        it = item("SNOS-380", glossary={"橋本ありな": "新有菜"})
        it["actors"] = [{"name": "橋本ありな"}, {"name": "茉城まみ"}]
        out = tr.translate_batch([it], conf=FAKE_CONF, opener=opener)
        assert out["SNOS-380"]["actors"] == [{"jp": "橋本ありな", "zh": "新有菜"},
                                             {"jp": "茉城まみ", "zh": ""}]

    def test_actors_present_even_when_untranslated(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        it = item("SNOS-380", glossary={"橋本ありな": "新有菜"})
        it["actors"] = [{"name": "橋本ありな"}]
        out = tr.translate_batch([it], conf=FAKE_CONF, opener=opener)
        assert out["SNOS-380"]["status"] == "untranslated"
        assert out["SNOS-380"]["actors"] == [{"jp": "橋本ありな", "zh": "新有菜"}]

    def test_prompt_forbids_guessing_names(self, tr):
        """第 3 条铁律：表外人名一律保留日文。"""
        sys_p = tr.system_prompt({"橋本ありな": "新有菜"})
        assert "只有出现在【演员译名对照表】里的人名才允许译成中文" in sys_p
        assert "不在表里的人名一律原样保留日文写法" in sys_p
        assert "严禁音译、严禁自创中文名" in sys_p

    def test_prompt_states_empty_glossary_rule(self, tr):
        assert "表为空时所有人名都保留日文" in tr.system_prompt({})


class TestValidatorKana:
    def test_kana_residue_rejected(self, tr):
        ok, why = tr.check_kana_residue("これはテストでございます")
        assert ok is False and "假名残留" in why

    def test_short_kana_not_rejected(self, tr):
        # 假名 3 个 < 4：即使占比 100% 也放行（阈值口径是「≥4 且 >30%」）
        assert tr.check_kana_residue("テスト")[0] is True
        assert tr.count_kana("テスト") == 3

    def test_four_kana_over_30pct_rejected(self, tr):
        text = "テストあ"          # 4 假名 / 5 字符 = 80%
        assert tr.count_kana(text) == 4
        assert tr.check_kana_residue(text)[0] is False

    def test_four_kana_under_30pct_passes(self, tr):
        text = "テスト" + "中" * 20   # 3 假名 → 占比远低于 30%
        assert tr.check_kana_residue(text)[0] is True
        text2 = "あいうえ" + "中" * 20  # 4 假名 / 24 字符 ≈ 17%
        assert tr.count_kana(text2) == 4
        assert tr.check_kana_residue(text2)[0] is True

    def test_kana_ratio_helper(self, tr):
        assert tr.kana_ratio("") == 0.0
        assert tr.kana_ratio("ああ") == 1.0
        assert round(tr.kana_ratio("ああ中中"), 3) == 0.5

    def test_katakana_and_hiragana_both_counted(self, tr):
        assert tr.count_kana("あア漢") == 2


class TestValidatorLength:
    def test_title_too_short(self, tr):
        ok, why = tr.check_length("短", None, None)
        assert ok is False and "标题过短" in why
        assert tr.check_length("中文", None, None)[0] is True

    def test_plot_too_short(self, tr):
        ok, why = tr.check_length("正常标题", "太短", "あ" * 100)
        assert ok is False and "过短" in why

    def test_plot_too_long(self, tr):
        ok, why = tr.check_length("正常标题", "中" * 300, "あ" * 100)
        assert ok is False and "过长" in why

    def test_plot_reasonable_passes(self, tr):
        src = "あ" * 100
        assert tr.check_length("正常标题", "中" * 50, src)[0] is True
        assert tr.check_length("正常标题", "中" * 15, src)[0] is True    # 恰好 0.15
        assert tr.check_length("正常标题", "中" * 250, src)[0] is True   # 恰好 2.5

    def test_plot_boundary_edges_fail(self, tr):
        src = "あ" * 100
        assert tr.check_length("正常标题", "中" * 14, src)[0] is False
        assert tr.check_length("正常标题", "中" * 251, src)[0] is False

    def test_empty_plot_when_source_has_plot_rejected(self, tr):
        ok, why = tr.check_length("正常标题", None, "あ" * 50)
        assert ok is False and "plot_zh 为空" in why

    def test_fabricated_plot_rejected(self, tr):
        """提示词铁律 3：源没有简介却编出一段 —— 必须判失败。"""
        ok, why = tr.check_length("正常标题", "凭空编造的简介", None)
        assert ok is False and "源无简介" in why
        assert tr.check_length("正常标题", None, None)[0] is True


class TestValidateEntryCombined:
    def test_all_pass_without_plot(self, tr):
        ok, why = tr.validate_entry(
            {"title_zh": "地味OL被中年恶心上司发现隐藏色气身材 雏形美玖留", "plot_zh": None},
            {"number": "SNOS-380", "title_jp": JP_TITLE, "plot_jp": None})
        assert (ok, why) == (True, "ok")

    def test_all_pass_with_plot(self, tr):
        ok, why = tr.validate_entry(
            {"title_zh": "VR沉浸体验 与女友共度浓密时光", "plot_zh": ZH_PLOT_OK},
            {"number": "MIDV-946", "title_jp": "VR作品", "plot_jp": JP_PLOT})
        assert (ok, why) == (True, "ok")

    def test_empty_title_rejected(self, tr):
        ok, why = tr.validate_entry({"title_zh": "   ", "plot_zh": None},
                                    {"number": "A-1", "plot_jp": None})
        assert ok is False and "标题为空" in why

    def test_entry_not_dict_rejected(self, tr):
        assert tr.validate_entry(None, {"number": "A-1"})[0] is False
        assert tr.validate_entry("文本", {"number": "A-1"})[0] is False

    def test_reason_carries_number(self, tr):
        ok, why = tr.validate_entry({"title_zh": "抱歉", "plot_zh": None},
                                    {"number": "SNOS-380"})
        assert ok is False and "SNOS-380" in why


# ================================================================ 缓存键

class TestCacheKey:
    def test_formula(self, tr):
        raw = "|".join(("ソース", "zh-CN", "title", tr.PROMPT_VER, tr.glossary_hash({})))
        assert tr.cache_key("ソース", field_type="title") == \
            hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def test_field_type_separates(self, tr):
        assert tr.cache_key("x", field_type="title") != tr.cache_key("x", field_type="plot")

    def test_glossary_changes_key(self, tr):
        a = tr.cache_key("橋本ありな 引退", field_type="title", glossary={})
        b = tr.cache_key("橋本ありな 引退", field_type="title", glossary={"橋本ありな": "新有菜"})
        c = tr.cache_key("橋本ありな 引退", field_type="title", glossary={"橋本ありな": "桥本有菜"})
        assert len({a, b, c}) == 3

    def test_prompt_ver_changes_key(self, tr):
        assert tr.cache_key("x", prompt_ver="v1") != tr.cache_key("x", prompt_ver="v2")

    def test_target_lang_changes_key(self, tr):
        assert tr.cache_key("x", target_lang="zh-CN") != tr.cache_key("x", target_lang="zh-TW")

    def test_glossary_hash_is_order_independent(self, tr):
        assert tr.glossary_hash({"a": "1", "b": "2"}) == tr.glossary_hash({"b": "2", "a": "1"})
        assert tr.glossary_hash({}) == "none"
        assert tr.glossary_hash(None) == "none"


# ================================================================ 假 Store

class FakeStore:
    """`store.translate_get/translate_put` 的内存替身（签名与契约 §3.2 一致）。"""

    def __init__(self):
        self.data = {}
        self.puts = []

    def translate_get(self, cache_key):
        return self.data.get(cache_key)

    def translate_put(self, cache_key, source_text, translated_text,
                      model_name="", quality_tier="llm"):
        self.data[cache_key] = translated_text
        self.puts.append({"key": cache_key, "src": source_text, "dst": translated_text,
                          "model": model_name, "tier": quality_tier})

    def seed(self, tr, src, dst, field_type="title", glossary=None):
        self.data[tr.cache_key(src, field_type=field_type, glossary=glossary)] = dst
        return self


# ================================================================ chat / selfcheck

class TestChat:
    def test_success_returns_text_and_empty_err(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "中文", "plot_zh": None}})
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener)
        assert err == "" and "SNOS-380" in text
        assert opener.calls[0]["max_tokens"] >= 2000
        assert opener.calls[0]["auth"] == "Bearer sk-fake-key"
        assert opener.calls[0]["url"].endswith("/v1/chat/completions")

    def test_empty_content_with_reasoning_retries_then_fails(self, tr, no_net, no_sleep):
        """D20 核心：content 空而 reasoning 非空 → 重试一次，绝不把 reasoning 当译文。"""
        opener = FakeOpener().on("hy3", lambda n, b: reply("", reasoning="推理" * 400,
                                                           finish="length"))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            max_tokens=2000, conf=FAKE_CONF, opener=opener)
        assert text == ""
        assert "空正文" in err and "reasoning" in err
        assert len([c for c in opener.calls if c["model"] == "hy3"]) == 1 + tr.EMPTY_CONTENT_RETRY
        assert no_sleep  # 重试前退避过

    def test_empty_content_retry_can_succeed(self, tr, no_net, no_sleep):
        # 推理输错了：先回了一个完全不合 JSON 的正文 → 应该只是「解析失败」，不触发空正文重试
        opener = FakeOpener().on("hy3", lambda n, b: (
            reply("", reasoning="推理中", finish="length") if n == 1
            else reply('{"A-1":{"title_zh":"第二次成功","plot_zh":null}}')))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener)
        assert err == "" and "第二次成功" in text
        assert len(opener.calls) == 2

    def test_content_and_reasoning_both_present_uses_content(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: reply('{"A":1}', reasoning="我思考了很久"))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener)
        assert json.loads(text) == {"A": 1} and err == ""

    def test_http_500_retries_with_backoff(self, tr, no_net, no_sleep):
        def boom(n, b):
            if n <= 2:
                return urllib.error.HTTPError("u", 500, "err", {},
                                              __import__("io").BytesIO(b'{"error":{}}'))
            return reply('{"A":1}')

        opener = FakeOpener().on("hy3", boom)
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener, retry_limit=tr.RETRY_MAX)
        assert err == "" and json.loads(text) == {"A": 1}
        assert len(opener.calls) == 3
        assert no_sleep == [tr.RETRY_BASE_SLEEP, tr.RETRY_BASE_SLEEP * 2]   # 指数退避

    def test_http_429_retry_capped(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError(
            "u", 429, "slow", {}, __import__("io").BytesIO(b'{"error":{}}')))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener, retry_limit=tr.RETRY_MAX)
        assert text == "" and "429" in err
        assert len(opener.calls) == 1 + tr.RETRY_MAX

    def test_http_404_not_retried(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("nope", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="nope",
                            conf=FAKE_CONF, opener=opener)
        assert text == "" and "404" in err
        assert len(opener.calls) == 1

    def test_model_not_found_not_retried(self, tr, no_net, no_sleep):
        """REPORT-5 §6.1：`404` + `model_not_found` 是降级信号，不该在同一个模型上耗往返。"""
        body = {"error": {"code": "model_not_found", "message": "模型不存在: nope"}}
        opener = FakeOpener().on("nope", lambda n, b: FakeResp(body, status=404))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="nope",
                            conf=FAKE_CONF, opener=opener, retry_limit=tr.RETRY_MAX_SINGLE)
        assert text == "" and "model_not_found" in err
        assert len(opener.calls) == 1

    def test_error_envelope_reported(self, tr, no_net, no_sleep):
        body = {"error": {"code": "model_not_found", "message": "模型不存在: nope"}}
        opener = FakeOpener().on("nope", lambda n, b: FakeResp(body, status=404))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="nope",
                            conf=FAKE_CONF, opener=opener)
        assert text == "" and "model_not_found" in err and "模型不存在" in err

    def test_timeout_is_swallowed(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: TimeoutError("timed out"))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener, retry_limit=tr.RETRY_MAX_BATCH)
        assert text == "" and "TimeoutError" in err
        assert len(opener.calls) == 1 + tr.RETRY_MAX_BATCH   # 超时按可重试处理

    def test_non_json_body(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: FakeResp(b"<html>502</html>", status=200))
        text, err = tr.chat([{"role": "user", "content": "x"}], model="hy3",
                            conf=FAKE_CONF, opener=opener)
        assert text == "" and "非 JSON" in err

    def test_default_timeout_at_least_120(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", '{"A":1}')
        tr.chat([{"role": "user", "content": "x"}], model="hy3", conf=FAKE_CONF, opener=opener)
        assert tr.CHAT_TIMEOUT >= 120
        assert opener.calls[0]["timeout"] == tr.CHAT_TIMEOUT

    def test_max_tokens_override_respected(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", '{"A":1}')
        tr.chat([{"role": "user", "content": "x"}], model="hy3", max_tokens=6000,
                conf=FAKE_CONF, opener=opener)
        assert opener.calls[0]["max_tokens"] == 6000


class TestSelfcheck:
    def test_missing_key_returns_not_ok_without_raising(self, tr, no_net, monkeypatch):
        monkeypatch.setattr(tr, "llm_conf", lambda override=None: {
            "base_url": "http://gw/v1", "api_key": "", "model": "hy3",
            "fallback": "fb"})
        out = tr.selfcheck("hy3")
        assert out["ok"] is False
        assert out["model"] == "hy3"
        assert out["latency_ms"] == 0
        assert "LLM_API_KEY" in out["error"]

    def test_no_host_module_no_raise(self, tr, no_net, monkeypatch):
        monkeypatch.setitem(sys.modules, "app.runtime.settings", None)
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("LLM_BASE_URL", raising=False)
        out = tr.selfcheck("")
        assert out["ok"] is False and out["model"] == "hy3"

    def test_ok_path(self, tr, no_net, no_sleep, monkeypatch):
        monkeypatch.setattr(tr, "llm_conf", lambda override=None: dict(FAKE_CONF))
        opener = FakeOpener().on_json("hy3", "正常")
        monkeypatch.setattr(tr, "_open_url", opener)
        out = tr.selfcheck("hy3")
        assert out["ok"] is True and out["reply"] == "正常"
        assert out["latency_ms"] >= 0

    def test_failure_path_returns_error(self, tr, no_net, no_sleep, monkeypatch):
        monkeypatch.setattr(tr, "llm_conf", lambda override=None: dict(FAKE_CONF))
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 401, "bad key", {}, None))
        monkeypatch.setattr(tr, "_open_url", opener)
        out = tr.selfcheck("hy3")
        assert out["ok"] is False and "401" in out["error"]

    def test_uses_min_token_budget(self, tr, no_net, no_sleep, monkeypatch):
        monkeypatch.setattr(tr, "llm_conf", lambda override=None: dict(FAKE_CONF))
        opener = FakeOpener().on_json("hy3", "正常")
        monkeypatch.setattr(tr, "_open_url", opener)
        tr.selfcheck("hy3")
        assert opener.calls[0]["max_tokens"] >= tr.MAX_TOKENS_MIN >= 2000


# ================================================================ 降级链

class TestDegradeChain:
    def test_batch_success_no_single_retry(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: reply(json.dumps(
            {k: {"title_zh": "中文" + k, "plot_zh": None}
             for k in json.loads(b["messages"][1]["content"])}, ensure_ascii=False)))
        out = tr.translate_batch([item("SNOS-380"), item("CAWD-989")],
                                 conf=FAKE_CONF, opener=opener)
        assert {k: v["status"] for k, v in out.items()} == {"SNOS-380": "done", "CAWD-989": "done"}
        assert {v["model"] for v in out.values()} == {"hy3"}
        assert len(opener.calls) == 1   # 批量一次搞定

    def test_missing_key_falls_to_single_retry(self, tr, no_net, no_sleep):
        def hy3(n, b):
            req = json.loads(b["messages"][1]["content"])
            if len(req) > 1:
                first = list(req)[0]
                return reply(json.dumps({first: {"title_zh": "批量只给一个", "plot_zh": None}},
                                        ensure_ascii=False))
            k = list(req)[0]
            return reply(json.dumps({k: {"title_zh": "单条补译" + k, "plot_zh": None}},
                                    ensure_ascii=False))

        opener = FakeOpener().on("hy3", hy3)
        out = tr.translate_batch([item("SNOS-380"), item("CAWD-989")],
                                 conf=FAKE_CONF, opener=opener)
        assert out["CAWD-989"]["title_zh"] == "单条补译CAWD-989"
        assert out["CAWD-989"]["status"] == "done"
        # 部分成功（只缺一个 Key）不重打整批：1 次批量 + 1 次单条补
        assert [len(json.loads(c["messages"][1]["content"])) for c in opener.calls] == [2, 1]

    def test_batch_fail_then_single_then_fallback(self, tr, no_net, no_sleep):
        """批量失败 → 单条 hy3 → 单条备用模型：三级都走一遍，最终由备用模型救回。"""
        def hy3(n, b):
            raise urllib.error.HTTPError("u", 404, "nf", {}, None)

        opener = FakeOpener().on("hy3", hy3).on_json("fb-model", {
            "SNOS-380": {"title_zh": "备用模型译文", "plot_zh": None}})
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener)
        row = out["SNOS-380"]
        assert row["status"] == "done" and row["title_zh"] == "备用模型译文"
        assert row["model"] == "fb-model"
        assert [c["model"] for c in opener.calls] == ["hy3", "hy3", "fb-model"]

    def test_validator_failure_triggers_single_retry(self, tr, no_net, no_sleep):
        """批量里出现拒译语 → 该条转单条重试（单条模型给出干净译文）。"""
        def hy3(n, b):
            req = json.loads(b["messages"][1]["content"])
            if len(req) > 1:
                return reply(json.dumps(
                    {k: {"title_zh": "抱歉，我无法翻译这段内容", "plot_zh": None} for k in req},
                    ensure_ascii=False))
            k = list(req)[0]
            return reply(json.dumps({k: {"title_zh": "单条干净译文", "plot_zh": None}},
                                    ensure_ascii=False))

        opener = FakeOpener().on("hy3", hy3)
        out = tr.translate_batch([item("SNOS-380"), item("CAWD-989")], conf=FAKE_CONF, opener=opener)
        assert {v["title_zh"] for v in out.values()} == {"单条干净译文"}
        assert {v["status"] for v in out.values()} == {"done"}
        # 1 次批量（两条都拒译）+ 2 次单条
        assert [len(json.loads(c["messages"][1]["content"])) for c in opener.calls] == [2, 1, 1]

    def test_all_fail_marks_untranslated_keeps_jp(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None)) \
                            .on("fb-model", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener)
        row = out["SNOS-380"]
        assert row["status"] == "untranslated"
        assert row["title_zh"] == JP_TITLE          # 保留日文原名
        assert row["plot_zh"] is None
        assert row["error"]
        # 404 不是可重试错误：批量一次 + 单条一次 + 备用一次，各只调一遍
        assert [c["model"] for c in opener.calls] == ["hy3", "hy3", "fb-model"]

    def test_server_error_is_retried_before_fallback(self, tr, no_net, no_sleep):
        """5xx/429 才是可重试的：网关抽风时先退避重试，别急着降级到备用模型。"""
        def boom(n, b):
            # 按「同一次请求的第几次尝试」计：第 2 次（也就是重试的那次）就成功
            if n % 2 == 1:
                return urllib.error.HTTPError("u", 503, "unavailable", {},
                                              __import__("io").BytesIO(b'{}'))
            return reply('{"SNOS-380":{"title_zh":"重试后成功","plot_zh":null}}')

        opener = FakeOpener().on("hy3", boom)
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener)
        assert out["SNOS-380"]["status"] == "done"
        assert out["SNOS-380"]["title_zh"] == "重试后成功"
        # 第一次尝试 503 → chat_detail 内部退避重试一次即成功；**没有**降级到备用模型
        assert [c["model"] for c in opener.calls] == ["hy3", "hy3"]
        assert no_sleep == [tr.RETRY_BASE_SLEEP]

    def test_rejected_status_is_reported(self, tr, no_net, no_sleep):
        """校验器反复不过 → 单条链走完仍拿不到合法译文 → untranslated（error 里带原因）。"""
        opener = FakeOpener().on("hy3", lambda n, b: reply(
            '{"SNOS-380":{"title_zh":"抱歉，我无法翻译","plot_zh":null}}'))
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener)
        row = out["SNOS-380"]
        assert row["status"] == "untranslated"
        assert "拒译词" in row["error"]
        assert row["status"] in tr.STATUSES

    def test_machine_fallback_off_by_default(self, tr, no_net, no_sleep):
        left = []
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener,
                                 machine_fn=lambda src: left.append(src) or "机翻结果")
        assert out["SNOS-380"]["status"] == "untranslated"
        assert left == []            # 默认关：机翻函数一次都不许被调

    def test_machine_fallback_when_allowed(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener,
                                 allow_machine=True,
                                 machine_fn=lambda src: "机翻译文标题")
        row = out["SNOS-380"]
        assert row["status"] == "machine_fallback"
        assert row["title_zh"] == "机翻译文标题"
        assert row["model"] == "machine"

    def test_machine_fallback_rejected_by_validator(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 404, "nf", {}, None))
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener,
                                 allow_machine=True, machine_fn=lambda src: "抱歉")
        assert out["SNOS-380"]["status"] == "untranslated"

    def test_all_entries_present_even_on_hard_failure(self, tr, no_net, no_sleep):
        """任何失败路径都必须给齐条目，KeyError 会直接打挂 UI。"""
        opener = FakeOpener().on("hy3", lambda n, b: urllib.error.HTTPError("u", 500, "e", {}, None))
        out = tr.translate_batch([item("SNOS-380"), item("CAWD-989", plot=JP_PLOT)],
                                 conf=FAKE_CONF, opener=opener)
        assert set(out) == {"SNOS-380", "CAWD-989"}
        for row in out.values():
            assert set(row) >= {"number", "title_zh", "plot_zh", "status", "error"}

    def test_no_base_url_short_circuits(self, tr, no_net, no_sleep):
        opener = FakeOpener()
        out = tr.translate_batch([item("SNOS-380")],
                                 conf={"base_url": "", "api_key": "k", "model": "hy3",
                                       "fallback": "fb"}, opener=opener)
        assert out["SNOS-380"]["status"] == "untranslated"
        assert "LLM_BASE_URL" in out["SNOS-380"]["error"]
        assert opener.calls == []

    def test_blank_number_skipped(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "中文", "plot_zh": None}})
        out = tr.translate_batch([item("SNOS-380"), {"number": "", "title_jp": "x"}],
                                 conf=FAKE_CONF, opener=opener)
        assert set(out) == {"SNOS-380"}

    def test_empty_items(self, tr, no_net, no_sleep):
        assert tr.translate_batch([], conf=FAKE_CONF, opener=FakeOpener()) == {}
        assert tr.translate_batch(None, conf=FAKE_CONF, opener=FakeOpener()) == {}


class TestBatching:
    def test_title_only_batches_of_six(self, tr, no_net, no_sleep):
        sizes = []

        def hy3(n, b):
            req = json.loads(b["messages"][1]["content"])
            sizes.append(len(req))
            return reply(json.dumps({k: {"title_zh": "中文" + k, "plot_zh": None} for k in req},
                                    ensure_ascii=False))

        opener = FakeOpener().on("hy3", hy3)
        items = [item("N-%02d" % i) for i in range(1, 14)]
        out = tr.translate_batch(items, conf=FAKE_CONF, opener=opener)
        assert sizes == [6, 6, 1]
        assert len(out) == 13 and all(v["status"] == "done" for v in out.values())

    def test_plot_batches_of_three(self, tr, no_net, no_sleep):
        sizes = []

        def hy3(n, b):
            req = json.loads(b["messages"][1]["content"])
            sizes.append(len(req))
            return reply(json.dumps(
                {k: {"title_zh": "中文" + k, "plot_zh": "中" * 30} for k in req},
                ensure_ascii=False))

        opener = FakeOpener().on("hy3", hy3)
        src_plot = "あ" * 100
        items = [item("N-%02d" % i, plot=src_plot) for i in range(1, 8)]
        out = tr.translate_batch(items, conf=FAKE_CONF, opener=opener)
        assert sizes == [1, 1, 1, 1, 1, 1, 1]      # 每条都有简介 → 绝不互相合批
        assert len(opener.calls) == 7
        assert all(v["plot_zh"] == "中" * 30 for v in out.values())

    def test_plot_request_gets_same_full_budget(self, tr, no_net, no_sleep):
        """REPORT-5：统一 8192（不再分标题/简介档），别给 1024 —— 会被思维链吃光。"""
        def hy3(n, b):
            req = json.loads(b["messages"][1]["content"])
            out = {}
            for k, v in req.items():
                has_plot = bool(v.get("plot_jp"))
                out[k] = {"title_zh": "中文标题", "plot_zh": ("中" * 30) if has_plot else None}
            return reply(json.dumps(out, ensure_ascii=False))

        opener = FakeOpener().on("hy3", hy3)
        a = tr.translate_batch([item("A-1")], conf=FAKE_CONF, opener=opener)
        b = tr.translate_batch([item("A-2", plot="あ" * 100)], conf=FAKE_CONF, opener=opener)
        assert a["A-1"]["status"] == "done" and a["A-1"]["plot_zh"] is None
        assert b["A-2"]["status"] == "done" and b["A-2"]["plot_zh"] == "中" * 30
        budgets = [c["max_tokens"] for c in opener.calls]
        assert budgets == [8192, 8192]
        assert tr.MAX_TOKENS_DEFAULT == 8192

    def test_chunk_items_mixed(self, tr):
        items = [item("A"), item("B", plot="あ" * 50), item("C"),
                 item("D"), item("E"), item("F"), item("G")]
        chunks = tr._chunk_items(items)
        assert [len(c) for c in chunks] == [2, 5]
        assert [i["number"] for c in chunks for i in c] == ["A", "B", "C", "D", "E", "F", "G"]
        assert all(len(c) <= tr.BATCH_TITLE for c in chunks)
        for c in chunks:
            if any(i.get("plot_jp") for i in c):
                assert len(c) <= tr.BATCH_PLOT

    def test_chunk_items_plot_never_mixes_with_full_title_batch(self, tr):
        """批内一旦出现简介条目，该批上限降到 3，后面的纯标题条目不许把它撑回 6。"""
        items = [item("A"), item("B"), item("C"), item("D"),
                 item("E", plot="あ" * 50), item("F"), item("G")]
        chunks = tr._chunk_items(items)
        assert [i["number"] for c in chunks for i in c] == \
            ["A", "B", "C", "D", "E", "F", "G"]
        assert [len(c) for c in chunks] == [4, 1, 2]
        for c in chunks:
            if any(i.get("plot_jp") for i in c):
                assert len(c) <= tr.BATCH_PLOT   # 含简介的批绝不超过 3

    def test_chunk_items_never_exceeds_plot_limit(self, tr):
        items = [item("A", plot="あ" * 50)] + [item("N-%d" % i) for i in range(8)]
        chunks = tr._chunk_items(items)
        for c in chunks:
            if any(i.get("plot_jp") for i in c):
                assert len(c) <= tr.BATCH_PLOT
        assert all(len(c) <= tr.BATCH_TITLE for c in chunks)
        assert [i["number"] for c in chunks for i in c] == [i["number"] for i in items]

    def test_chunk_items_every_item_keeps_plot_limit(self, tr):
        chunks = tr._chunk_items([item("N-%d" % i, plot="あ" * 50) for i in range(5)])
        assert [len(c) for c in chunks] == [1, 1, 1, 1, 1]

    def test_chunk_items_title_only_batches_full(self, tr):
        chunks = tr._chunk_items([item("N-%d" % i) for i in range(13)])
        assert [len(c) for c in chunks] == [6, 6, 1]


# ================================================================ 缓存

class TestCache:
    def test_cache_hit_skips_http(self, tr, no_net, no_sleep):
        store = FakeStore().seed(tr, JP_TITLE, "缓存里的中文标题")
        opener = FakeOpener()
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener, store=store)
        row = out["SNOS-380"]
        assert row["status"] == "done" and row["title_zh"] == "缓存里的中文标题"
        assert row["from_cache"] is True
        assert opener.calls == []          # 一次 HTTP 都没有

    def test_cache_hit_with_plot_requires_both(self, tr, no_net, no_sleep):
        store = FakeStore().seed(tr, JP_TITLE, "缓存标题")
        opener = FakeOpener().on("hy3", lambda n, b: reply(json.dumps(
            {k: {"title_zh": "新标题", "plot_zh": "中" * 30}
             for k in json.loads(b["messages"][1]["content"])}, ensure_ascii=False)))
        out = tr.translate_batch([item("SNOS-380", plot="あ" * 100)], conf=FAKE_CONF,
                                 opener=opener, store=store)
        assert out["SNOS-380"]["from_cache"] is False   # 简介没缓存 → 走调用
        assert len(opener.calls) == 1

    def test_full_cache_hit_including_plot(self, tr, no_net, no_sleep):
        store = FakeStore()
        store.seed(tr, JP_TITLE, "缓存标题", field_type="title")
        store.seed(tr, "あ" * 100, "中" * 40, field_type="plot")
        opener = FakeOpener()
        out = tr.translate_batch([item("SNOS-380", plot="あ" * 100)], conf=FAKE_CONF,
                                 opener=opener, store=store)
        row = out["SNOS-380"]
        assert row["from_cache"] is True and row["title_zh"] == "缓存标题"
        assert row["plot_zh"] == "中" * 40
        assert opener.calls == []

    def test_cache_written_after_success(self, tr, no_net, no_sleep):
        store = FakeStore()
        opener = FakeOpener().on("hy3", lambda n, b: reply(json.dumps(
            {k: {"title_zh": "新中文标题", "plot_zh": None}
             for k in json.loads(b["messages"][1]["content"])}, ensure_ascii=False)))
        tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener, store=store)
        assert store.data[tr.cache_key(JP_TITLE, field_type="title")] == "新中文标题"
        assert store.puts[0]["tier"] == "llm" and store.puts[0]["src"] == JP_TITLE

    def test_glossary_change_misses_cache(self, tr, no_net, no_sleep):
        store = FakeStore().seed(tr, JP_TITLE, "旧词表译文")
        opener = FakeOpener().on("hy3", lambda n, b: reply(
            '{"SNOS-380":{"title_zh":"新词表译文","plot_zh":null}}'))
        out = tr.translate_batch([item("SNOS-380", glossary={"橋本ありな": "新有菜"})],
                                 conf=FAKE_CONF, opener=opener, store=store)
        assert out["SNOS-380"]["from_cache"] is False
        assert out["SNOS-380"]["title_zh"] == "新词表译文"
        assert len(opener.calls) == 1

    def test_corrupt_cache_does_not_break(self, tr, no_net, no_sleep):
        class BadStore:
            def translate_get(self, key):
                raise RuntimeError("db locked")

            def translate_put(self, *a, **k):
                raise RuntimeError("db locked")

        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "正常译文", "plot_zh": None}})
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener,
                                 store=BadStore())
        assert out["SNOS-380"]["status"] == "done"
        assert out["SNOS-380"]["title_zh"] == "正常译文"

    def test_invalid_cached_entry_is_not_trusted(self, tr, no_net, no_sleep):
        store = FakeStore().seed(tr, JP_TITLE, "抱歉，我无法翻译")
        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "重译的好标题", "plot_zh": None}})
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener, store=store)
        assert out["SNOS-380"]["from_cache"] is False
        assert out["SNOS-380"]["title_zh"] == "重译的好标题"

    def test_store_none_is_fine(self, tr, no_net, no_sleep):
        opener = FakeOpener().on_json("hy3", {"SNOS-380": {"title_zh": "无缓存译文", "plot_zh": None}})
        out = tr.translate_batch([item("SNOS-380")], conf=FAKE_CONF, opener=opener, store=None)
        assert out["SNOS-380"]["status"] == "done"


class TestUsage:
    def test_usage_accumulated(self, tr, no_net, no_sleep):
        opener = FakeOpener().on("hy3", lambda n, b: reply(json.dumps(
            {k: {"title_zh": "中文", "plot_zh": None}
             for k in json.loads(b["messages"][1]["content"])}, ensure_ascii=False),
            usage={"prompt_tokens": 100, "completion_tokens": 50, "reasoning_tokens": 20}))
        out = tr.translate_batch([item("A-1"), item("A-2")], conf=FAKE_CONF, opener=opener)
        assert out["A-1"]["usage"]["prompt_tokens"] == 100
        assert out["A-1"]["usage"]["completion_tokens"] == 50
        assert out["A-1"]["usage"]["reasoning_tokens"] == 20
