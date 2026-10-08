from __future__ import annotations

from dataclasses import dataclass

from rtt.bot.toolbox import ToolBox, ToolOutcome

_JSON_RETRIES = 2
_PAUSE_LIMIT = 5
_UNPARSEABLE_TOOL_JSON = "Unable to parse tool parameter JSON"
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
_MODEL_INTERNAL_BLOCKS = frozenset({"thinking", "redacted_thinking", "tool_use", "server_tool_use"})


class BotError(Exception):
    pass


class BotDeclined(BotError):
    def __init__(self, category: str) -> None:
        super().__init__(f"the request was declined ({category})")
        self.category = category


@dataclass(frozen=True)
class BotSettings:
    model: str = "claude-opus-5-5"
    effort: str = "high"
    max_tokens: int = 64_000


class TurnListener:
    def on_text(self, chunk: str) -> None:
        pass

    def on_tool_call(self, name: str, arguments: object) -> None:
        pass

    def on_tool_result(self, outcome: ToolOutcome) -> None:
        pass

    def on_retry(self) -> None:
        pass


def echoable_content(content: list) -> list:
    boundary = max((i for i, block in enumerate(content) if block.type == "fallback"), default=-1)
    return [
        block
        for i, block in enumerate(content)
        if i > boundary or block.type not in _MODEL_INTERNAL_BLOCKS
    ]


def _refusal_category(response) -> str:
    details = getattr(response, "stop_details", None)
    return getattr(details, "category", None) or "unspecified"


class Conversation:
    def __init__(
        self, stream, toolbox: ToolBox, system_prompt: str, settings: BotSettings | None = None
    ) -> None:
        self._stream = stream
        self._run_tool = toolbox.run
        self._tool_definitions = toolbox.definitions()
        self._system_prompt = system_prompt
        self._settings = settings or BotSettings()
        self.messages: list[dict] = []
        self.last_stop_reason: str | None = None

    def _request(self) -> dict:
        return {
            "model": self._settings.model,
            "max_tokens": self._settings.max_tokens,
            "system": [
                {
                    "type": "text",
                    "text": self._system_prompt,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            "tools": self._tool_definitions,
            "messages": self.messages,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self._settings.effort},
            "betas": [_FALLBACK_BETA],
            "fallbacks": "default",
            "cache_control": {"type": "ephemeral"},
        }

    def _stream_one_response(self, listener: TurnListener):
        with self._stream(**self._request()) as stream:
            for event in stream:
                if event.type == "text":
                    listener.on_text(event.text)
            return stream.get_final_message()

    def _response_with_json_retries(self, listener: TurnListener):
        failures = 0
        while True:
            try:
                return self._stream_one_response(listener)
            except ValueError as error:
                if not str(error).startswith(_UNPARSEABLE_TOOL_JSON):
                    raise
                failures += 1
                if failures > _JSON_RETRIES:
                    raise BotError(
                        f"the model's tool-call JSON could not be parsed after {failures} attempts"
                    ) from error
                listener.on_retry()

    def _tool_result(self, block, listener: TurnListener) -> dict:
        listener.on_tool_call(block.name, block.input)
        outcome = self._run_tool(block.name, block.input)
        listener.on_tool_result(outcome)
        result = {"type": "tool_result", "tool_use_id": block.id, "content": outcome.text}
        if outcome.is_error:
            result["is_error"] = True
        return result

    def ask(self, text: str, listener: TurnListener | None = None) -> str:
        start = len(self.messages)
        try:
            return self._complete_turn(text, listener or TurnListener())
        except BaseException:
            del self.messages[start:]
            raise

    def _complete_turn(self, text: str, listener: TurnListener) -> str:
        self.messages.append({"role": "user", "content": text})
        pauses = 0
        answer: list[str] = []
        while True:
            response = self._response_with_json_retries(listener)
            self.last_stop_reason = response.stop_reason
            if response.stop_reason == "refusal":
                raise BotDeclined(_refusal_category(response))
            echoed = echoable_content(list(response.content))
            self.messages.append({"role": "assistant", "content": echoed})
            answer.extend(block.text for block in echoed if block.type == "text")
            if response.stop_reason == "pause_turn":
                pauses += 1
                if pauses > _PAUSE_LIMIT:
                    raise BotError(f"The reply stayed paused after {_PAUSE_LIMIT} continuations.")
                continue
            tool_uses = [block for block in echoed if block.type == "tool_use"]
            if not tool_uses:
                return "".join(answer)
            if response.stop_reason == "max_tokens":
                raise BotError(
                    "The reply hit max_tokens in the middle of a tool call; raise --max-tokens."
                )
            results = [self._tool_result(block, listener) for block in tool_uses]
            self.messages.append({"role": "user", "content": results})
