from __future__ import annotations

from rtt.app import audio_config


class _AudioCommands:
    def record_audio(self, config: dict) -> bool:
        proposed = audio_config.from_persisted(config)
        if proposed == self.audio:
            return False
        self.snapshot()
        self.audio = proposed
        return True
