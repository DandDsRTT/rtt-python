from types import SimpleNamespace

from rtt.bot.agent import TurnListener


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(identifier, name, arguments):
    return SimpleNamespace(type="tool_use", id=identifier, name=name, input=arguments)


def message(*blocks, stop_reason="end_turn"):
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason)


class FakeStream:
    def __init__(self, final, failure=None):
        self._final = final
        self._failure = failure

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False

    def __iter__(self):
        if self._failure:
            raise self._failure
        for block in self._final.content:
            if block.type == "text":
                yield SimpleNamespace(type="text", text=block.text)

    def get_final_message(self):
        return self._final


class FakeStreamer:
    def __init__(self, *scripted):
        self._scripted = list(scripted)
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self._scripted.pop(0)


class RecordingListener(TurnListener):
    def __init__(self):
        self.chunks = []
        self.tool_calls = []
        self.tool_results = []

    def on_text(self, chunk):
        self.chunks.append(chunk)

    def on_tool_call(self, name, arguments):
        self.tool_calls.append((name, arguments))

    def on_tool_result(self, outcome):
        self.tool_results.append(outcome)
