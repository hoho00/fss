import os
import tempfile
import threading
from pathlib import Path

from app.services.encrypted_json import EncryptedJsonCodec


class MahjongEfficiencyStore:
    def __init__(self, file_path: str | Path | None = None):
        self.file_path = Path(
            file_path
            or os.getenv("FSS_MAHJONG_EFFICIENCY_STORE_PATH", "data/mahjong_efficiency.json")
        )
        self._codec = EncryptedJsonCodec()
        self._lock = threading.RLock()

    def load(self) -> dict:
        with self._lock:
            if not self.file_path.exists():
                return {"sessions": {}, "records": {}}
            content = self.file_path.read_text(encoding="utf-8")
            data, needs_rewrite = self._codec.loads(content)
            result = data if isinstance(data, dict) else {}
            result.setdefault("sessions", {})
            result.setdefault("records", {})
            if needs_rewrite:
                self.save(result)
            return result

    def save(self, data: dict) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, temporary_name = tempfile.mkstemp(
                dir=self.file_path.parent, prefix="mahjong_efficiency_", suffix=".tmp"
            )
            temporary = Path(temporary_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as file:
                    file.write(self._codec.dumps(data))
                    file.flush()
                    os.fsync(file.fileno())
                os.replace(temporary, self.file_path)
            finally:
                if temporary.exists():
                    temporary.unlink()
