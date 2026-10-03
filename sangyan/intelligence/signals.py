"""Content safety signal and manipulative persuasion detector.

Detects 20+ observable, factual safety signals with contextual negation handling
to prevent false positives on regulatory warnings, disclaimers, and awareness materials.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from sangyan.domain.base import new_id
from sangyan.domain.models import SIGNAL_TYPES, Signal


# ---------------------------------------------------------------------------
# Negation and Educational Warning Suppression
# ---------------------------------------------------------------------------

# Patterns indicating an educational, cautionary, or regulatory disclaimer
WARNING_CONTEXT_PATTERNS = re.compile(
    r"(?i)\b(?:beware\s+of|warns?\s+investors?|caution|alert|advises?|regulatory\s+warning|never\s+share|"
    r"do\s+not\s+(?:share|invest|send|transfer|pay)|not\s+guaranteed|subject\s+to\s+market\s+risks?|"
    r"past\s+performance\s+is\s+not|sebi\s+does\s+not|does\s+not\s+guarantee|avoid\s+fraud|"
    r"savdhan|satark|dhoke\s+se\s+bache|nahi\s+kare|na\s+kare|nahi\s+deta)\b"
    r"|(?:धोखाधड़ी\s+से\s+बचें|सावधान|सतर्क|चेतावनी|सलाह|सेबी\s+ने\s+चेतावनी\s+दी|शेयर\s+बाजार\s+जोखिमों\s+के\s+अधीन)"
)

# Generic negation words that invert an assertion when immediately preceding a keyword
NEGATION_PREFIXES = re.compile(
    r"(?i)\b(?:not|never|no|neither|nor|without|do\s+not|don't|cannot|can't|nahi|nahin|na|mat)\s+$"
)


# ---------------------------------------------------------------------------
# Affirmative Signal Detection Patterns
# ---------------------------------------------------------------------------

SIGNAL_RULES: list[dict[str, Any]] = [
    {
        "signal_type": "GUARANTEED_RETURN",
        "pattern": re.compile(
            r"(?i)\b(?:guaranteed?\s+(?:(?:\d+%|fixed)\s+)?returns?|"
            r"(?:100%|\d+%)\s+guarantee[ds]?(?:\s+returns?)?|"
            r"fixed\s+(?:monthly|daily|weekly|annual)?\s*returns?|"
            r"risk[- ]free\s+returns?|zero\s+risk(?:\s+investment)?|loss[- ]proof|"
            r"pakka\s+(?:munafa|profit|return)|100%\s+sure[- ]shot|100%\s+safe\s+and\s+secure\s+profit)\b"
            r"|(?:100%\s*गारंटी|निश्चित\s+परतावा|खात्रीशीर\s+नफा|पक्का\s+मुनाफा|शून्य\s+जोखिम)"
        ),
        "basis": "Explicit promise of guaranteed or fixed investment returns, prohibited under SEBI regulations.",
        "confidence": 0.95,
    },
    {
        "signal_type": "HIGH_RETURN_PROMISE",
        "pattern": re.compile(
            r"(?i)\b(?:(?:double|triple)\s+your\s+money\s+in\s+\d+\s+(?:days?|weeks?|months?|hours?)|"
            r"\b[2-9]\d{1,2}%\s*(?:daily|weekly|monthly)\s*(?:returns?|profit|roi)|"
            r"earn\s+₹?\s*\d[\d,]*\s*daily\s+from\s+home|"
            r"invest\s+₹?\s*\d[\d,]*\s*(?:and\s+get|to\s+get)\s+₹?\s*\d[\d,]*\s+in\s+\d+\s+(?:hours?|days?)|"
            r"10x\s+gains?|1000%\s+return)\b"
            r"|(?:पैसे\s+दुपट्ट|२\s+दिवसात\s+पैसे\s+दुगने|रोज\s+हजारों\s+कमाए)"
        ),
        "basis": "Abnormally high or mathematically implausible short-term return promises characteristic of Ponzi/task scams.",
        "confidence": 0.92,
    },
    {
        "signal_type": "URGENCY",
        "pattern": re.compile(
            r"(?i)\b(?:hurry\s+up|last\s+chance\s+to\s+join|only\s+\d+\s+(?:seats?|slots?|spots?)\s+left|"
            r"offer\s+closes?\s+(?:in\s+\d+\s+min(?:ute)?s?|today|tonight)|valid\s+only\s+for\s+today|"
            r"act\s+fast\s+before\s+price\s+hikes?|jaldi\s+karo\s+aaj\s+hi)\b"
            r"|(?:लवकर\s+करा|आजच\s+अंतिम\s+संधी|फक्त\s+\d+\s+जागा\s+शिल्लक|जल्दी\s+करें)"
        ),
        "basis": "Artificial urgency or countdown pressure designed to prevent deliberate due diligence.",
        "confidence": 0.85,
    },
    {
        "signal_type": "SCARCITY",
        "pattern": re.compile(
            r"(?i)\b(?:exclusive\s+vip\s+group|private\s+inner\s+circle|insider\s+trading\s+leak|"
            r"secret\s+operator\s+call|confidential\s+institutional\s+tips?|secret\s+formula|"
            r"selected\s+few\s+investors?\s+only)\b"
            r"|(?:खास\s+व्हीआयपी|गुप्त\s+टिप्स|इनसाइडर\s+माहिती)"
        ),
        "basis": "False scarcity and exclusivity appeals claiming non-public or privileged trading access.",
        "confidence": 0.88,
    },
    {
        "signal_type": "AUTHORITY_IMPERSONATION",
        "pattern": re.compile(
            r"(?i)\b(?:sebi\s+(?:officer|chairman|director|approved|certified\s+tipster|registered\s+whatsapp)|"
            r"nse\s+(?:insider|official\s+leak|partner\s+portal)|rbi\s+approved\s+scheme|"
            r"govt\s+approved\s+trading\s+platform|pm\s+(?:mudra\s+share|yojana\s+trading))\b"
            r"|(?:सेबी\s+प्रमाणित|सरकार\s+मान्यताप्राप्त\s+ट्रेडिंग)"
        ),
        "basis": "Misuse or impersonation of statutory regulators (SEBI/RBI) or government bodies to induce false trust.",
        "confidence": 0.95,
    },
    {
        "signal_type": "WITHDRAWAL_FEE",
        "pattern": re.compile(
            r"(?i)\b(?:pay\s+(?:[₹$€£]?\s*[\d,]+\s+)?(?:withdrawal\s+)?(?:tax|fee|deposit|charges?|margin)\s+(?:to\s+(?:withdraw|unlock)|before\s+withdrawal)|"
            r"withdrawal\s+(?:processing\s+)?(?:fee|charge)|"
            r"pay\s+\d+%\s+(?:gst|tax)\s+to\s+release\s+funds?|gas\s+fee\s+for\s+withdrawal)\b"
            r"|(?:पैसे\s+काढण्यासाठी\s+शुल्क|विड्रॉल\s+फी|टॅक्स\s+भरावा\s+लागेल)"
        ),
        "basis": "Demand for advance fee/tax/margin to release purported investment profits (hallmark of pig butchering/task scam).",
        "confidence": 0.98,
    },
    {
        "signal_type": "OTP_REQUEST",
        "pattern": re.compile(
            r"(?i)\b(?:share\s+(?:your\s+)?otp|send\s+the\s+6[- ]digit\s+code|tell\s+me\s+the\s+sms\s+code|"
            r"share\s+screen\s+via\s+(?:anydesk|teamviewer|rustdesk)|install\s+anydesk)\b"
            r"|(?:ओटीपी\s+सांगा|ओटीपी\s+शेअर\s+करा|एनीडेस्क\s+इन्स्टॉल)"
        ),
        "basis": "Solicitation of OTP, two-factor code, or remote desktop screen-sharing application.",
        "confidence": 0.98,
    },
    {
        "signal_type": "CREDENTIAL_REQUEST",
        "pattern": re.compile(
            r"(?i)\b(?:share\s+(?:your\s+)?(?:demat|trading|broker)\s+(?:login|password|pin)|"
            r"give\s+account\s+access|provide\s+your\s+netbanking\s+password|account\s+handling\s+service|"
            r"we\s+trade\s+on\s+your\s+behalf)\b"
            r"|(?:लॉगिन\s+आयडी\s+आणि\s+पासवर्ड|खाते\s+हँडलिंग)"
        ),
        "basis": "Request for private trading credentials or unauthorized portfolio account management.",
        "confidence": 0.95,
    },
    {
        "signal_type": "FAKE_PROFIT",
        "pattern": re.compile(
            r"(?i)\b(?:today\s+profit\s+screenshot|client\s+pnl\s+statement|proof\s+of\s+profit|"
            r"daily\s+profit\s+payout\s+proof|see\s+our\s+daily\s+earnings?)\b"
            r"|(?:नफ्याचा\s+स्क्रीनशॉट|कमाईचा\s+पुरावा)"
        ),
        "basis": "Fabricated profit screenshots or unverified P&L cards used as deceptive social proof.",
        "confidence": 0.80,
    },
    {
        "signal_type": "SOCIAL_MEDIA_SOLICITATION",
        "pattern": re.compile(
            r"(?i)\b(?:join\s+(?:our\s+)?(?:telegram|whatsapp)\s+(?:channel|group|community)|"
            r"click\s+link\s+to\s+join\s+vip\s+group|t\.me/|chat\.whatsapp\.com/|"
            r"daily\s+sure\s+calls\s+in\s+group)\b"
            r"|(?:टेलिग्राम\s+ग्रुप\s+जॉईन\s+करा|व्हॉट्सअ‍ॅप\s+ग्रुपमध्ये\s+शामिल\s+व्हा)"
        ),
        "basis": "Solicitation directing retail investors into unregulated private messaging groups.",
        "confidence": 0.88,
    },
    {
        "signal_type": "PRESSURE_LANGUAGE",
        "pattern": re.compile(
            r"(?i)\b(?:recover\s+all\s+(?:your\s+)?past\s+losses?|100%\s+loss\s+recovery\s+plan|"
            r"don'?t\s+miss\s+this\s+golden\s+opportunity|jackpot\s+call\s+today|sure-shot\s+multibagger)\b"
            r"|(?:सर्व\s+नुकसान\s+भरून\s+काढा|जॅकपॉट\s+कॉल)"
        ),
        "basis": "Psychological pressure targeting vulnerable investors through loss recovery or jackpot claims.",
        "confidence": 0.85,
    },
    {
        "signal_type": "SUSPICIOUS_URL",
        "pattern": re.compile(
            r"(?i)https?://[^\s/$.?#].[^\s]*\.(?:top|vip|cc|work|click|xyz|link|cfd|tokyo|rest|live|fit)\b|"
            r"https?://\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"
        ),
        "basis": "Presence of suspicious top-level domain (TLD) or raw IP address URL commonly associated with phishing infrastructure.",
        "confidence": 0.90,
    },
    {
        "signal_type": "UNVERIFIED_APP",
        "pattern": re.compile(
            r"(?i)\b(?:download\s+(?:our\s+)?(?:apk|app\s+directly)|install\s+from\s+link|not\s+on\s+play\s*store|"
            r"bypass\s+play\s*store|direct\s+apk\s+download)\b|\bhttps?://[^\s]+\.apk\b"
        ),
        "basis": "Direction to download unverified sideloaded Android APK outside official app stores.",
        "confidence": 0.95,
    },
    {
        "signal_type": "THIRD_PARTY_PAYMENT",
        "pattern": re.compile(
            r"(?i)\b(?:pay\s+to\s+personal\s+upi|transfer\s+to\s+individual\s+savings\s+account|"
            r"send\s+usdt|pay\s+via\s+crypto|deposit\s+in\s+savings\s+account\s+of)\b"
        ),
        "basis": "Payment solicitation to third-party personal accounts or cryptocurrency addresses instead of registered intermediary client accounts.",
        "confidence": 0.92,
    },
    {
        "signal_type": "UPI_MISMATCH",
        "pattern": re.compile(
            r"(?i)\b(?:pay\s+on\s+[a-z0-9._\-]+@(?:okhdfcbank|okaxis|oksbi|paytm)\s+for\s+(?:sebi|zerodha|groww|nse|bse))\b"
        ),
        "basis": "Personal retail UPI handle requested for payments purportedly destined for institutional entities.",
        "confidence": 0.96,
    },
]


class SignalDetector:
    """Detects observable content safety signals while filtering out hard negative disclaimers."""

    def detect_signals(self, text: str, content_item_id: str) -> list[Signal]:
        if not text or not text.strip():
            return []

        # Split text into sentence-level chunks to localize negation context
        sentences = re.split(r"(?<=[.!?।\n])\s+", text)
        signals: list[Signal] = []
        seen_types_and_excerpts: set[tuple[str, str]] = set()

        for sentence in sentences:
            sentence_clean = sentence.strip()
            if not sentence_clean:
                continue

            # Hard Negative Check:
            # If the entire sentence is an official warning or caution, skip signal extraction on it
            if WARNING_CONTEXT_PATTERNS.search(sentence_clean):
                continue

            for rule in SIGNAL_RULES:
                signal_type = rule["signal_type"]
                pattern: re.Pattern = rule["pattern"]
                basis = rule["basis"]
                conf = rule["confidence"]

                for match in pattern.finditer(sentence_clean):
                    excerpt = match.group(0)

                    # Check for immediate preceding negation within the sentence
                    prefix_text = sentence_clean[: match.start()]
                    if NEGATION_PREFIXES.search(prefix_text):
                        # Negated signal (e.g. "returns are not guaranteed", "never share OTP")
                        continue

                    key = (signal_type, excerpt.lower())
                    if key in seen_types_and_excerpts:
                        continue
                    seen_types_and_excerpts.add(key)

                    signals.append(
                        Signal(
                            content_item_id=content_item_id,
                            signal_type=signal_type,
                            excerpt=excerpt,
                            detection_basis=basis,
                            confidence=conf,
                            metadata={
                                "rule_name": signal_type.lower(),
                                "sentence_context": sentence_clean[:200],
                            },
                        )
                    )

        return signals
