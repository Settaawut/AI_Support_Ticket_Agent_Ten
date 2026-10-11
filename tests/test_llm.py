import openai
import pytest
from openai.types.chat import ChatCompletion

from triage.config import Settings
from triage.llm import FakeLLM, LLMError, LLMResponse
from triage.llm.openai_client import OpenAIClient, is_transient
from triage.llm.retry import with_retry


# Built without __init__ so the tests don't depend on the SDK's HTTP library internals,
# which differ between openai 1.x (httpx) and newer majors.
def _timeout() -> Exception:
    return openai.APITimeoutError.__new__(openai.APITimeoutError)


def _bad_request() -> Exception:
    return openai.BadRequestError.__new__(openai.BadRequestError)


# --- with_retry -----------------------------------------------------------------------


def _flaky(failures: list[Exception], result: str = "ok"):
    calls = {"n": 0}

    def fn():
        calls["n"] += 1
        if failures:
            raise failures.pop(0)
        return result

    return fn, calls


def test_retry_recovers_from_transient_errors_with_exponential_backoff():
    fn, calls = _flaky([_timeout(), _timeout()])
    sleeps: list[float] = []
    result = with_retry(
        fn,
        retries=3,
        base_delay_s=1.0,
        is_transient=is_transient,
        sleep=sleeps.append,
        jitter=lambda d: d,
    )
    assert result == "ok" and calls["n"] == 3
    assert sleeps == [1.0, 2.0]


def test_retry_does_not_retry_permanent_errors():
    fn, calls = _flaky([_bad_request()])
    with pytest.raises(openai.BadRequestError):
        with_retry(fn, retries=3, base_delay_s=0, is_transient=is_transient, sleep=lambda _: None)
    assert calls["n"] == 1


def test_retry_gives_up_after_budget():
    fn, calls = _flaky([_timeout() for _ in range(5)])
    with pytest.raises(openai.APITimeoutError):
        with_retry(fn, retries=2, base_delay_s=0, is_transient=is_transient, sleep=lambda _: None)
    assert calls["n"] == 3


# --- OpenAIClient (SDK stubbed, no network) ------------------------------------------


class _StubCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.kwargs = None

    def create(self, **kwargs):
        self.kwargs = kwargs
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class _StubSDK:
    def __init__(self, outcomes):
        self.chat = type("Chat", (), {})()
        self.chat.completions = _StubCompletions(outcomes)


def _completion(**message) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "c1",
            "object": "chat.completion",
            "created": 0,
            "model": "gpt-4o-mini",
            "choices": [
                {"index": 0, "finish_reason": "stop", "message": {"role": "assistant", **message}}
            ],
            "usage": {"prompt_tokens": 120, "completion_tokens": 30, "total_tokens": 150},
        }
    )


def _client(outcomes, **settings) -> tuple[OpenAIClient, _StubSDK]:
    sdk = _StubSDK(outcomes)
    config = Settings(retry_base_delay_s=0, **settings)
    return OpenAIClient(config, client=sdk), sdk  # type: ignore[arg-type]


def test_openai_client_maps_tool_calls_and_usage():
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "get_customer_history", "arguments": '{"customer_id": "c"}'},
    }
    client, sdk = _client([_completion(content=None, tool_calls=[tool_call])])
    response = client.complete([{"role": "user", "content": "hi"}], [], {"type": "json_object"})
    assert response.tool_calls[0].name == "get_customer_history"
    assert response.usage.prompt_tokens == 120
    assert sdk.chat.completions.kwargs["temperature"] == 0.0


def test_openai_client_retries_then_succeeds():
    client, _ = _client([_timeout(), _completion(content="{}")])
    assert client.complete([], [], {}).content == "{}"


def test_openai_client_wraps_final_failure_as_llm_error():
    client, _ = _client([_bad_request()])
    with pytest.raises(LLMError):
        client.complete([], [], {})


def test_empty_tool_list_is_not_sent():
    client, sdk = _client([_completion(content="{}")])
    client.complete([], [], {})
    assert "tools" not in sdk.chat.completions.kwargs


def test_temperature_omitted_when_disabled():
    client, sdk = _client([_completion(content="{}")], temperature=None)
    client.complete([], [], {})
    assert "temperature" not in sdk.chat.completions.kwargs


# --- FakeLLM ----------------------------------------------------------------------------


def test_fake_llm_replays_and_records():
    fake = FakeLLM([LLMResponse(content="a")])
    assert fake.complete([{"role": "user", "content": "x"}], [], {}).content == "a"
    assert fake.requests[0][0]["content"] == "x"
    with pytest.raises(LLMError):
        fake.complete([], [], {})
