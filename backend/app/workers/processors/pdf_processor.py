import PyPDF2
import pytesseract
import asyncio
import logging
from typing import Dict, Any
from app.workers.processors.base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class PDFProcessor(BaseProcessor):

    async def parse(self, file_path: str) -> Dict[str, Any]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._parse_sync, file_path)

    def _parse_sync(self, file_path: str) -> Dict[str, Any]:
        try:
            with open(file_path, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                metadata = {"pages": len(reader.pages), "has_images": False}
                parts = []
                for page in reader.pages:
                    parts.append(page.extract_text() or "")
                    if '/Resources' in page and '/XObject' in page['/Resources']:
                        metadata["has_images"] = True

            full_text = "\n\n".join(parts)

            if len(full_text.strip()) < 100:
                logger.info("Sparse text — attempting OCR")
                full_text = self._ocr_sync(file_path)
                metadata["ocr_used"] = True

            return {"text": full_text, "metadata": metadata}
        except Exception as e:
            logger.error(f"PDF parse error: {e}")
            raise

    def _ocr_sync(self, file_path: str) -> str:
        try:
            import pdf2image
            images = pdf2image.convert_from_path(file_path)
            return "\n\n".join(pytesseract.image_to_string(img) for img in images)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""

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
