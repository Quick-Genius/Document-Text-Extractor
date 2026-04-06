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
            images = pdf2image.convert_from_path(file_path, timeout=120)
        except Exception as e:
            logger.error(f"Failed to convert PDF to images: {e}")
            return ""
            
        try:
            # Enforce 120 second strict C++ subprocess timeout
            extracted_text = "\n\n".join(pytesseract.image_to_string(img, timeout=120) for img in images)
        except Exception as e:
            logger.error(f"pytesseract failed or timed out: {e}")
            extracted_text = ""
            
        if len(extracted_text.strip()) < 100:
            logger.info("OCR returned sparse/no text; attempting Groq Vision fallback...")
            groq_text = self._groq_vision_fallback_sync(images)
            if groq_text.strip():
                return groq_text
                
        return extracted_text

    def _groq_vision_fallback_sync(self, images) -> str:
        import os
        import httpx
        import base64
        import io

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            logger.warning("GROQ_API_KEY not set. Cannot use Groq Vision fallback.")
            return ""

        # Determine page limit from environment (default to 10, set to 0 for unlimited)
        max_pages_str = os.getenv("GROQ_VISION_MAX_PAGES", "10")
        try:
            max_pages = int(max_pages_str)
        except ValueError:
            max_pages = 10

        url = "https://api.groq.com/openai/v1/chat/completions"
        extracted_parts = []
        
        # Slice images based on the configured limit
        images_to_process = images[:max_pages] if max_pages > 0 else images
        
        for i, img in enumerate(images_to_process):
            try:
                buffer = io.BytesIO()
                img.save(buffer, format="JPEG", quality=80)
                base64_img = base64.b64encode(buffer.getvalue()).decode('utf-8')
                
                payload = {
                    "model": "llama-3.2-11b-vision-preview",
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text", 
                                    "text": "Extract all readable text from this document image exactly as it appears. Output only the transcribed text without any markdown formatting or extra commentary."
                                },
                                {
                                    "type": "image_url", 
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_img}"}
                                }
                            ]
                        }
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2048
                }
                
                response = httpx.post(
                    url,
                    headers={"Authorization": f"Bearer {groq_key}"},
                    json=payload,
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()
                
                if "choices" in data and len(data["choices"]) > 0:
                    text = data["choices"][0].get("message", {}).get("content", "")
                    extracted_parts.append(text.strip())
            except Exception as e:
                logger.error(f"Groq Vision fallback failed on page {i+1}: {e}")
                
        return "\n\n".join(extracted_parts)

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
