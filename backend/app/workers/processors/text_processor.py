import asyncio
import logging
from typing import Dict, Any
from app.workers.processors.base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class TextProcessor(BaseProcessor):

    async def parse(self, file_path: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> Dict[str, Any]:
        # Try UTF-8 first, fall back to latin-1
        for enc in ('utf-8', 'latin-1', 'cp1252'):
            try:
                with open(file_path, 'r', encoding=enc) as f:
                    text = f.read()
                return {"text": text, "metadata": {"encoding": enc}}
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Could not decode text file: {file_path}")

    async def extract_structured_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        text = parsed_data["text"]
        return {
            "text": text,
            "title": self.extract_title(text),
            "category": self.detect_category(text),
            "summary": self.extract_summary(text),
            "keywords": self.extract_keywords(text),
            "metadata": parsed_data["metadata"],
        }
