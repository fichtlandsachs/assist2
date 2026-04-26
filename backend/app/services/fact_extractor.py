"""Fact Extractor - Extracts structured facts from user messages."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_engine import AnswerSignal, ConversationFact


@dataclass
class CandidateFact:
    """A candidate fact extracted from a user message."""
    category: str
    value: str
    normalized_value: Optional[str]
    source_message_id: uuid.UUID
    confidence: float
    matched_signal_id: Optional[uuid.UUID]
    target_protocol_area_key: Optional[str]
    evidence_text: str
    extraction_method: str  # pattern | synonym | llm


class FactExtractor:
    """Extracts facts from user messages using signals and pattern matching."""

    # Base confidence scores
    CONFIDENCE_PATTERN_MATCH = 0.85
    CONFIDENCE_SYNONYM_MATCH = 0.75
    CONFIDENCE_LLM_FALLBACK = 0.65
    CONFIDENCE_SEMANTIC_GUESS = 0.55

    @staticmethod
    def preprocess(text: str) -> dict:
        """Preprocess text for extraction.

        Returns dict with:
        - original: Original text
        - trimmed: Trimmed text
        - lowercase: Lowercase version for matching
        - sentences: List of sentences
        """
        trimmed = text.strip()
        lowercase = trimmed.lower()

        # Simple sentence splitting
        sentences = re.split(r'[.!?]+', trimmed)
        sentences = [s.strip() for s in sentences if s.strip()]

        return {
            "original": text,
            "trimmed": trimmed,
            "lowercase": lowercase,
            "sentences": sentences,
        }

    @staticmethod
    def detect_entities(text: str) -> dict:
        """Simple entity detection for roles, systems, projects."""
        entities = {
            "roles": [],
            "systems": [],
            "projects": [],
        }

        # Common role patterns
        role_patterns = [
            r'\b(OrgAdmin|orgadmin|org-admin|organisationsadmin)\b',
            r'\b(Fachbereichsleiter|Fachbereichsleitung|Abteilungsleiter)\b',
            r'\b(Entwickler|Developer|Dev|Programmierer)\b',
            r'\b(Product Owner|PO|Produkt Owner)\b',
            r'\b(Scrum Master|SM)\b',
            r'\b(Team Lead|Teamleiter|Tech Lead)\b',
            r'\b(Admin|Administrator|Superadmin)\b',
        ]

        for pattern in role_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities["roles"].append(match.group(1))

        # System patterns
        system_patterns = [
            r'\b(JIRA|Jira|Confluence|GitHub|GitLab)\b',
            r'\b(Salesforce|SAP|ServiceNow)\b',
            r'\b(PostgreSQL|Postgres|MySQL|MariaDB|Redis)\b',
        ]

        for pattern in system_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                entities["systems"].append(match.group(1))

        return entities

    @staticmethod
    async def load_active_signals(db: AsyncSession) -> list[AnswerSignal]:
        """Load all active answer signals from database."""
        result = await db.execute(
            select(AnswerSignal).where(AnswerSignal.is_active == True)
        )
        return list(result.scalars().all())

    @staticmethod
    def match_patterns(
        text: str,
        signals: list[AnswerSignal],
        preprocessed: dict,
    ) -> list[CandidateFact]:
        """Match text against signal patterns."""
        candidates = []
        text_lower = preprocessed["lowercase"]
        sentences = preprocessed["sentences"]

        for signal in signals:
            matched = False
            matched_pattern = None
            extraction_method = None

            # Check patterns (pipe-separated keywords)
            if signal.pattern:
                patterns = [p.strip() for p in signal.pattern.split("|")]
                for pattern in patterns:
                    if pattern.lower() in text_lower:
                        matched = True
                        matched_pattern = pattern
                        extraction_method = "pattern"
                        break

            # Note: synonyms field doesn't exist in current model
            # Pattern field can contain pipe-separated keywords for synonym matching

            if matched:
                # Extract the relevant sentence as evidence
                evidence = text
                for sentence in sentences:
                    if matched_pattern and matched_pattern.lower() in sentence.lower():
                        evidence = sentence
                        break

                # Calculate base confidence
                confidence = (
                    FactExtractor.CONFIDENCE_PATTERN_MATCH
                    if extraction_method == "pattern"
                    else FactExtractor.CONFIDENCE_SYNONYM_MATCH
                )

                candidate = CandidateFact(
                    category=signal.fact_category,
                    value=evidence[:200],  # Truncate for storage
                    normalized_value=None,  # Will be set by normalizer
                    source_message_id=uuid.uuid4(),  # Placeholder, will be updated
                    confidence=confidence,
                    matched_signal_id=signal.id,
                    target_protocol_area_key=signal.fact_category,  # Use category as fallback
                    evidence_text=evidence,
                    extraction_method=extraction_method,
                )
                candidates.append(candidate)

        return candidates

    @staticmethod
    def apply_confidence_adjustments(
        candidate: CandidateFact,
        existing_facts: list[ConversationFact],
        entities: dict,
    ) -> float:
        """Apply confidence adjustments based on context."""
        confidence = candidate.confidence

        # Boost for clear role mentions
        if candidate.category == "target_user" and entities["roles"]:
            confidence += 0.05

        # Boost for system mentions in affected_system category
        if candidate.category == "affected_system" and entities["systems"]:
            confidence += 0.05

        # Reduce for very long text with multiple topics
        if len(candidate.evidence_text) > 200:
            confidence -= 0.10

        # Reduce for vague formulations
        vague_words = ["irgendwie", "vielleicht", "irgendwas", "etwas", "jemand"]
        if any(word in candidate.evidence_text.lower() for word in vague_words):
            confidence -= 0.10

        # Check for conflicts with existing facts
        for fact in existing_facts:
            if fact.category == candidate.category:
                # Simple similarity check
                if fact.normalized_value and candidate.normalized_value:
                    if fact.normalized_value != candidate.normalized_value:
                        # Potential conflict
                        confidence -= 0.20

        # Clamp to valid range
        return max(0.0, min(1.0, confidence))

    @staticmethod
    def assign_status(confidence: float, mode: str) -> str:
        """Assign fact status based on confidence and mode."""
        if mode == "exploration":
            return "suggested" if confidence >= 0.80 else "detected"
        else:  # story mode
            if confidence >= 0.85:
                return "confirmed_candidate"
            elif confidence >= 0.60:
                return "suggested"
            else:
                return "detected"

    @staticmethod
    async def extract_facts(
        db: AsyncSession,
        message_text: str,
        message_id: uuid.UUID,
        conversation_id: uuid.UUID,
        org_id: uuid.UUID,
        mode: str,
        existing_facts: list[ConversationFact],
    ) -> list[CandidateFact]:
        """Main extraction pipeline."""
        # Preprocessing
        preprocessed = FactExtractor.preprocess(message_text)

        # Entity detection
        entities = FactExtractor.detect_entities(message_text)

        # Load signals
        signals = await FactExtractor.load_active_signals(db)

        # Pattern matching
        candidates = FactExtractor.match_patterns(message_text, signals, preprocessed)

        # Update source message ID
        for candidate in candidates:
            candidate.source_message_id = message_id

        # Apply confidence adjustments
        for candidate in candidates:
            candidate.confidence = FactExtractor.apply_confidence_adjustments(
                candidate, existing_facts, entities
            )

        return candidates
