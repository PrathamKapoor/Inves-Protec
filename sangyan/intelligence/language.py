"""Multilingual language identification and script analysis for Indian financial content.

Supports English, Hindi (Devanagari), Hinglish (Romanized Hindi), Marathi,
Gujarati, Bengali, Tamil, Telugu, and Kannada with script analysis and code-mixing detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LanguageResult:
    """Detailed result of language and script identification."""

    primary_language: str  # 'en', 'hi', 'hinglish', 'mr', 'gu', 'bn', 'ta', 'te', 'kn', 'unknown'
    confidence: float
    script: str            # 'Latn', 'Deva', 'Gujr', 'Beng', 'Taml', 'Telu', 'Knda', 'Mixed', 'Unknown'
    is_multilingual: bool = False
    language_scores: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "primary_language": self.primary_language,
            "confidence": round(self.confidence, 4),
            "script": self.script,
            "is_multilingual": self.is_multilingual,
            "language_scores": {k: round(v, 4) for k, v in self.language_scores.items()},
        }


# High-frequency Marathi diagnostic tokens (distinguishes Marathi from Hindi in Devanagari)
MARATHI_MARKERS = {
    "आहे", "नाही", "मिळेल", "मिळतील", "करा", "करणे", "झाले", "होते", "आणि", "यांचे",
    "नफा", "गुंतवणूक", "खात्रीशीर", "लवकर", "शेअर", "तुम्हाला", "त्यांना", "आमच्या",
    "करावे", "येथे", "पाहिजे", "सर्व", "चांगला", "राहतील", "उत्तम", "करण्यासाठी",
}

# High-frequency Hindi diagnostic tokens in Devanagari
HINDI_MARKERS = {
    "है", "नहीं", "मिलेगा", "मिलेंगे", "करो", "करना", "हुआ", "था", "और", "यह",
    "मुनाफा", "निवेश", "गारंटी", "जल्दी", "शेयर", "बाजार", "कमाए", "आपको", "उनको",
    "हमारे", "चाहिए", "यहाँ", "सकते", "देगा", "खोलें", "बेहतरीन", "करने", "के",
}

# Common Hinglish (Romanized Hindi) words heavily used in Indian financial messaging
HINGLISH_MARKERS = {
    "aapko", "aapka", "aap", "milega", "milenge", "karo", "kare", "karna", "kijiye",
    "paisa", "paise", "kamaye", "kamana", "munafa", "hoga", "honge", "nahi", "nahin",
    "sirf", "aaj", "jaldi", "dosto", "dost", "dhamaka", "pakka", "shandar", "bharosa",
    "suno", "bhai", "khata", "jama", "nivesh", "fayda", "faida", "sach", "dekho",
    "sabse", "bada", "mauka", "lut", "looto", "free", "call", "tip", "tips",
    "rokda", "garanti", "guarantee", "loss", "recovery", "dhamakedar", "asli",
}

# English common stopwords
ENGLISH_MARKERS = {
    "the", "and", "is", "in", "to", "for", "with", "on", "at", "by", "this", "that",
    "from", "are", "you", "your", "investment", "return", "guaranteed", "profit",
    "stock", "market", "trade", "trading", "money", "account", "register",
}


def _is_devanagari(ch: str) -> bool:
    return "\u0900" <= ch <= "\u097F"


def _is_bengali(ch: str) -> bool:
    return "\u0980" <= ch <= "\u09FF"


def _is_gujarati(ch: str) -> bool:
    return "\u0A80" <= ch <= "\u0AFF"


def _is_tamil(ch: str) -> bool:
    return "\u0B80" <= ch <= "\u0BFF"


def _is_telugu(ch: str) -> bool:
    return "\u0C00" <= ch <= "\u0C7F"


def _is_kannada(ch: str) -> bool:
    return "\u0C80" <= ch <= "\u0CFF"


def _is_latin(ch: str) -> bool:
    return ("a" <= ch <= "z") or ("A" <= ch <= "Z")


class LanguageDetector:
    """Fast, deterministic multilingual identifier for Indian financial contexts."""

    def detect(self, text: str) -> LanguageResult:
        if not text or not text.strip():
            return LanguageResult(
                primary_language="unknown",
                confidence=0.0,
                script="Unknown",
                is_multilingual=False,
                language_scores={"unknown": 1.0},
            )

        # 1. Script character frequency distribution
        counts = {
            "Deva": 0,
            "Latn": 0,
            "Gujr": 0,
            "Beng": 0,
            "Taml": 0,
            "Telu": 0,
            "Knda": 0,
        }
        total_alpha = 0

        for ch in text:
            if _is_devanagari(ch):
                counts["Deva"] += 1
                total_alpha += 1
            elif _is_latin(ch):
                counts["Latn"] += 1
                total_alpha += 1
            elif _is_gujarati(ch):
                counts["Gujr"] += 1
                total_alpha += 1
            elif _is_bengali(ch):
                counts["Beng"] += 1
                total_alpha += 1
            elif _is_tamil(ch):
                counts["Taml"] += 1
                total_alpha += 1
            elif _is_telugu(ch):
                counts["Telu"] += 1
                total_alpha += 1
            elif _is_kannada(ch):
                counts["Knda"] += 1
                total_alpha += 1

        if total_alpha == 0:
            return LanguageResult(
                primary_language="unknown",
                confidence=0.0,
                script="Unknown",
                is_multilingual=False,
                language_scores={"unknown": 1.0},
            )

        ratios = {k: v / total_alpha for k, v in counts.items()}
        primary_script = max(ratios.keys(), key=lambda k: ratios[k])
        script_ratio = ratios[primary_script]

        # Multi-script detection
        active_scripts = [k for k, v in ratios.items() if v >= 0.15]
        is_multilingual = len(active_scripts) > 1

        # Tokenize for lexical analysis preserving Indic scripts and combining marks
        cleaned_for_tokens = re.sub(r"[^\w\s\u0900-\u0D7F]", " ", text)
        tokens = [t.strip().lower() for t in cleaned_for_tokens.split() if t.strip()]
        token_count = max(len(tokens), 1)

        # 2. Devanagari script: Hindi vs Marathi
        if primary_script == "Deva" and script_ratio >= 0.35:
            marathi_hits = sum(1 for t in tokens if t in MARATHI_MARKERS)
            hindi_hits = sum(1 for t in tokens if t in HINDI_MARKERS)

            scores: dict[str, float] = {}
            if marathi_hits > hindi_hits:
                scores["mr"] = min(0.65 + (marathi_hits / token_count) * 2.0, 0.98)
                scores["hi"] = max(1.0 - scores["mr"], 0.05)
                return LanguageResult(
                    primary_language="mr",
                    confidence=scores["mr"],
                    script="Deva",
                    is_multilingual=is_multilingual,
                    language_scores=scores,
                )
            else:
                scores["hi"] = min(0.70 + (hindi_hits / token_count) * 2.0, 0.99)
                scores["mr"] = max(1.0 - scores["hi"], 0.05)
                return LanguageResult(
                    primary_language="hi",
                    confidence=scores["hi"],
                    script="Deva",
                    is_multilingual=is_multilingual,
                    language_scores=scores,
                )

        # 3. Indic regional scripts
        if primary_script == "Gujr" and script_ratio >= 0.4:
            return LanguageResult(
                primary_language="gu",
                confidence=round(min(script_ratio + 0.2, 0.99), 4),
                script="Gujr",
                is_multilingual=is_multilingual,
                language_scores={"gu": script_ratio},
            )

        if primary_script == "Beng" and script_ratio >= 0.4:
            return LanguageResult(
                primary_language="bn",
                confidence=round(min(script_ratio + 0.2, 0.99), 4),
                script="Beng",
                is_multilingual=is_multilingual,
                language_scores={"bn": script_ratio},
            )

        if primary_script == "Taml" and script_ratio >= 0.4:
            return LanguageResult(
                primary_language="ta",
                confidence=round(min(script_ratio + 0.2, 0.99), 4),
                script="Taml",
                is_multilingual=is_multilingual,
                language_scores={"ta": script_ratio},
            )

        if primary_script == "Telu" and script_ratio >= 0.4:
            return LanguageResult(
                primary_language="te",
                confidence=round(min(script_ratio + 0.2, 0.99), 4),
                script="Telu",
                is_multilingual=is_multilingual,
                language_scores={"te": script_ratio},
            )

        if primary_script == "Knda" and script_ratio >= 0.4:
            return LanguageResult(
                primary_language="kn",
                confidence=round(min(script_ratio + 0.2, 0.99), 4),
                script="Knda",
                is_multilingual=is_multilingual,
                language_scores={"kn": script_ratio},
            )

        # 4. Latin script: Hinglish vs Standard English
        hinglish_hits = sum(1 for t in tokens if t in HINGLISH_MARKERS)
        english_hits = sum(1 for t in tokens if t in ENGLISH_MARKERS)

        hinglish_ratio = hinglish_hits / token_count
        english_ratio = english_hits / token_count

        scores = {}
        # If substantial Hinglish markers are found, classify as hinglish
        if hinglish_hits >= 2 or (hinglish_hits >= 1 and hinglish_ratio >= 0.08):
            conf = min(0.60 + hinglish_ratio * 3.0, 0.95)
            scores["hinglish"] = round(conf, 4)
            scores["en"] = round(max(1.0 - conf, 0.05), 4)
            return LanguageResult(
                primary_language="hinglish",
                confidence=conf,
                script="Latn",
                is_multilingual=True,  # Code-mixed by definition
                language_scores=scores,
            )

        # Default Latin script is English
        scores["en"] = round(min(0.70 + english_ratio * 1.5, 0.99), 4)
        if hinglish_hits > 0:
            scores["hinglish"] = round(hinglish_ratio, 4)

        return LanguageResult(
            primary_language="en",
            confidence=scores["en"],
            script="Latn",
            is_multilingual=is_multilingual,
            language_scores=scores,
        )
