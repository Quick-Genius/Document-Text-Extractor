import asyncio
import logging
from typing import Dict, Any
from app.workers.processors.base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class ImageProcessor(BaseProcessor):

    async def parse(self, file_path: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> Dict[str, Any]:
        try:
            import pytesseract
            from PIL import Image, ImageFilter, ImageEnhance

            img = Image.open(file_path)

            # Pre-process for better OCR accuracy
            img = img.convert('L')                          # greyscale
            img = ImageEnhance.Contrast(img).enhance(2.0)  # boost contrast
            img = img.filter(ImageFilter.SHARPEN)

            text = pytesseract.image_to_string(img, config='--psm 6')
            metadata = {
                "width": img.width,
                "height": img.height,
                "mode": "L",
            }
            return {"text": text, "metadata": metadata}
        except Exception as e:
            logger.error(f"Image parse error: {e}")
            raise

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
