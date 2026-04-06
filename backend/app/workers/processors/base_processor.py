from abc import ABC, abstractmethod
from typing import Dict, Any, List
from collections import Counter
import re
import math
import os
import httpx
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Shared stopwords (English)
# ---------------------------------------------------------------------------
_STOPWORDS = frozenset([
    'the','a','an','and','or','but','in','on','at','to','for','of','with',
    'by','from','as','is','was','are','were','been','be','have','has','had',
    'do','does','did','will','would','could','should','may','might','must',
    'can','this','that','these','those','it','its','we','our','you','your',
    'he','she','they','their','i','my','me','us','not','no','so','if','then',
    'than','also','just','more','about','into','over','after','before','up',
    'out','all','any','each','both','few','more','most','other','some','such',
    'only','own','same','too','very','s','t','re','ll','ve','d','m',
])


class BaseProcessor(ABC):
    """Base class for document processors with shared NLP extraction logic."""

    # ------------------------------------------------------------------
    # Abstract interface
    # ------------------------------------------------------------------

    @abstractmethod
    async def parse(self, file_path: str) -> Dict[str, Any]:
        """Parse file and return {"text": str, "metadata": dict}."""
        pass

    @abstractmethod
    async def extract_structured_data(self, parsed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured fields from parsed content."""
        pass

    # ------------------------------------------------------------------
    # Title extraction
    # ------------------------------------------------------------------

    def extract_title(self, text: str, max_len: int = 120) -> str:
        """
        Pick the most title-like line:
        - Prefer lines that are short, capitalised, and near the top
        - Skip lines that look like noise (all-caps headers, page numbers, URLs)
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        candidates = []

        for i, line in enumerate(lines[:30]):  # only look at first 30 lines
            # Skip obvious noise
            if re.match(r'^[\d\s\W]+$', line):          # only numbers/symbols
                continue
            if re.match(r'^https?://', line):            # URL
                continue
            if len(line) > max_len:                      # too long to be a title
                continue
            if len(line) < 3:
                continue

            score = 0
            # Prefer lines near the top
            score += max(0, 20 - i)
            # Prefer title-case or sentence-case
            if line.istitle():
                score += 10
            elif line[0].isupper():
                score += 5
            # Penalise all-caps (usually a section header, not a title)
            if line.isupper():
                score -= 8
            # Prefer medium length (10-80 chars)
            if 10 <= len(line) <= 80:
                score += 5
            # Penalise lines ending with colon (section labels)
            if line.endswith(':'):
                score -= 5

            candidates.append((score, line))

        if candidates:
            candidates.sort(key=lambda x: -x[0])
            return candidates[0][1]

        # Fallback: first non-empty line truncated
        return lines[0][:max_len] if lines else "Untitled Document"

    # ------------------------------------------------------------------
    # Category detection  (weighted multi-signal scoring)
    # ------------------------------------------------------------------

    _CATEGORY_SIGNALS: Dict[str, List[str]] = {
        "invoice": [
            "invoice", "bill to", "payment due", "total amount", "subtotal",
            "tax", "due date", "purchase order", "po number", "remit",
            "amount due", "billing address", "net 30", "net 60",
        ],
        "contract": [
            "agreement", "contract", "whereas", "party", "parties",
            "terms and conditions", "obligations", "indemnify", "liability",
            "governing law", "jurisdiction", "termination", "clause",
            "hereinafter", "witnesseth",
        ],
        "report": [
            "report", "analysis", "findings", "conclusion", "executive summary",
            "methodology", "results", "recommendations", "appendix",
            "figure", "table", "data", "survey", "study",
        ],
        "resume": [
            "resume", "curriculum vitae", "cv", "work experience",
            "education", "skills", "objective", "references", "employment",
            "bachelor", "master", "degree", "gpa", "internship",
        ],
        "letter": [
            "dear", "sincerely", "regards", "to whom it may concern",
            "yours faithfully", "yours truly", "best regards",
            "i am writing", "please find", "enclosed",
        ],
        "receipt": [
            "receipt", "transaction", "payment received", "thank you for",
            "order number", "confirmation", "charged", "refund",
        ],
        "legal": [
            "plaintiff", "defendant", "court", "hereby", "pursuant",
            "affidavit", "deposition", "subpoena", "statute", "regulation",
        ],
    }

    def detect_category(self, text: str) -> str:
        text_lower = text.lower()
        scores: Dict[str, int] = {}

        for category, signals in self._CATEGORY_SIGNALS.items():
            score = sum(1 for s in signals if s in text_lower)
            if score:
                scores[category] = score

        if not scores:
            return "document"
        return max(scores, key=lambda k: scores[k])

    # ------------------------------------------------------------------
    # Summary  (extractive — top-scored sentences, no API needed)
    # ------------------------------------------------------------------

    def extract_summary(self, text: str, max_sentences: int = 3, max_chars: int = 600) -> str:
        """
        Lightweight extractive summarisation:
        1. Score each sentence by TF of its words vs the whole document
        2. Pick top-N sentences in original order
        """
        # Sentence tokenisation (handles Mr./Dr./etc. reasonably)
        sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 30]

        if not sentences:
            return text[:max_chars]

        # If GROQ summarization is configured, prefer it
        groq_key = os.getenv('GROQ_API_KEY')
        groq_url = os.getenv('GROQ_API_URL', 'https://api.groq.com/v1/summarize')
        if groq_key:
            try:
                resp = httpx.post(
                    groq_url,
                    headers={
                        'Authorization': f'Bearer {groq_key}',
                        'Content-Type': 'application/json',
                    },
                    json={
                        'text': text,
                        'max_sentences': max_sentences,
                        'max_chars': max_chars,
                    },
                    timeout=30,
                )
                resp.raise_for_status()
                j = resp.json()
                if 'summary' in j and isinstance(j['summary'], str):
                    return j['summary'][:max_chars] + ('...' if len(j['summary']) > max_chars else '')
            except Exception as e:
                logger.warning(f'GROQ summarizer failed, falling back to local summary: {e}')

        if len(sentences) <= max_sentences:
            summary = ' '.join(sentences)
            return summary[:max_chars] + ('...' if len(summary) > max_chars else '')

        # Word frequencies across full text
        words = re.findall(r'\b[a-z]{3,}\b', text.lower())
        words = [w for w in words if w not in _STOPWORDS]
        freq = Counter(words)
        max_freq = max(freq.values()) if freq else 1

        # Normalise
        norm_freq = {w: c / max_freq for w, c in freq.items()}

        # Score sentences
        def score_sentence(s: str) -> float:
            tokens = re.findall(r'\b[a-z]{3,}\b', s.lower())
            tokens = [t for t in tokens if t not in _STOPWORDS]
            if not tokens:
                return 0.0
            return sum(norm_freq.get(t, 0) for t in tokens) / len(tokens)

        scored = sorted(enumerate(sentences), key=lambda x: -score_sentence(x[1]))
        top_indices = sorted(i for i, _ in scored[:max_sentences])
        summary = ' '.join(sentences[i] for i in top_indices)

        if len(summary) > max_chars:
            summary = summary[:max_chars].rsplit(' ', 1)[0] + '...'

        return summary

    # ------------------------------------------------------------------
    # Keyword extraction  (TF-IDF approximation, no corpus needed)
    # ------------------------------------------------------------------

    def extract_keywords(self, text: str, max_keywords: int = 10) -> List[str]:
        """
        TF-IDF-inspired keyword extraction:
        - TF: term frequency within the document
        - IDF approximation: penalise very common short words via length bonus
        - Also boosts capitalised terms (likely proper nouns / named entities)
        """
        # Split into sentences for IDF approximation
        sentences = re.split(r'[.!?\n]', text)
        total_sentences = max(len(sentences), 1)

        words_in_doc = re.findall(r'\b[a-zA-Z]{3,}\b', text)
        words_lower = [w.lower() for w in words_in_doc if w.lower() not in _STOPWORDS]

        if not words_lower:
            return []

        tf = Counter(words_lower)

        # Sentence frequency (how many sentences contain this word)
        sf: Dict[str, int] = {}
        for sent in sentences:
            seen = set(re.findall(r'\b[a-z]{3,}\b', sent.lower()))
            for w in seen:
                if w not in _STOPWORDS:
                    sf[w] = sf.get(w, 0) + 1

        # Capitalisation bonus: word appears capitalised mid-sentence
        cap_words = set(
            w.lower() for w in re.findall(r'(?<!\. )\b[A-Z][a-z]{2,}\b', text)
        )

        def tfidf_score(word: str) -> float:
            t = tf[word] / len(words_lower)
            idf = math.log(total_sentences / (sf.get(word, 1)))
            cap_bonus = 1.4 if word in cap_words else 1.0
            return t * idf * cap_bonus

        scored = sorted(tf.keys(), key=lambda w: -tfidf_score(w))
        return scored[:max_keywords]
