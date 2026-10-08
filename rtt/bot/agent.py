from __future__ import annotations

from dataclasses import dataclass

from rtt.bot.toolbox import ToolBox, ToolOutcome

_JSON_RETRIES = 2


class BotError(Exception):
    pass


@dataclass(frozen=True)
class BotSettings:
    model: str = "claude-opus-5-5"
    effort: str = "high"
    max_tokens: int = 32_000


class TurnListener:
    def on_text(self, chunk: str) -> None:
        pass

    def on_tool_call(self, name: str, arguments: object) -> None:
        pass

    def on_tool_result(self, outcome: ToolOutcome) -> None:
        pass


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
            except ValueError:
                failures += 1
                if failures > _JSON_RETRIES:
                    raise

    def _tool_result(self, block, listener: TurnListener) -> dict:
        listener.on_tool_call(block.name, block.input)
        outcome = self._run_tool(block.name, block.input)
        listener.on_tool_result(outcome)
        result = {"type": "tool_result", "tool_use_id": block.id, "content": outcome.text}
        if outcome.is_error:
            result["is_error"] = True
        return result

    def ask(self, text: str, listener: TurnListener | None = None) -> str:
        listener = listener or TurnListener()
        self.messages.append({"role": "user", "content": text})
        while True:
            response = self._response_with_json_retries(listener)
            self.messages.append({"role": "assistant", "content": response.content})
            if response.stop_reason == "pause_turn":
                continue
            tool_uses = [block for block in response.content if block.type == "tool_use"]
            if response.stop_reason == "refusal" or not tool_uses:
                return "".join(b.text for b in response.content if b.type == "text")
            if response.stop_reason == "max_tokens":
                raise BotError(
                    "The reply hit max_tokens in the middle of a tool call; raise --max-tokens."
                )
            results = [self._tool_result(block, listener) for block in tool_uses]
            self.messages.append({"role": "user", "content": results})
