"""Pattern Intent Parser — NLP-based intent classifier for mapping natural language to skill templates."""

import re
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel

from autopoiesis.registry.manager import RegistryManager


class IntentEntity(BaseModel):
    """Extracted intent entity from natural language."""
    action: str          # verb phrase (e.g., "fetch", "calculate", "save")
    target: str          # object/target (e.g., "candles", "SMA", "Postgres")
    modifiers: List[str] # qualifiers (e.g., "historical", "from Upstox")
    raw_text: str        # original text segment


class IntentClassification(BaseModel):
    """Classification result for an intent string."""
    original_intent: str
    entities: List[IntentEntity]
    primary_action: str
    confidence: float
    suggested_skill_template: Optional[str] = None


class PatternIntentParser:
    """Uses pattern matching + heuristics to classify intents into skill templates.

    Unlike the simple keyword-based LookAheadParser, this parser:
    - Extracts verb + object pairs from natural language
    - Identifies target systems (files, APIs, databases)
    - Maps patterns to registered skill templates
    - Provides confidence scores for ambiguous requests
    """

    # Common action verbs with associated skill templates
    ACTION_PATTERNS = {
        "fetch": {"template": "data_fetch", "verbs": ["fetch", "retrieve", "get", "pull", "download", "load"]},
        "calculate": {"template": "data_transform", "verbs": ["calculate", "compute", "derive", "analyze", "process"]},
        "save": {"template": "data_store", "verbs": ["save", "store", "write", "persist", "dump", "export"]},
        "notify": {"template": "notification_send", "verbs": ["notify", "alert", "send", "message", "ping", "inform"]},
        "parse": {"template": "data_parse", "verbs": ["parse", "read", "extract", "decode", "unpack"]},
        "transform": {"template": "data_transform", "verbs": ["transform", "convert", "map", "reshape", "modify"]},
        "validate": {"template": "schema_validate", "verbs": ["validate", "check", "verify", "assert"]},
        "filter": {"template": "data_filter", "verbs": ["filter", "select", "query", "find", "search"]},
        "aggregate": {"template": "data_aggregate", "verbs": ["aggregate", "summarize", "group", "count", "rollup"]},
        "visualize": {"template": "data_visualize", "verbs": ["visualize", "plot", "chart", "render", "display"]},
    }

    # Target system patterns
    TARGET_PATTERNS = {
        "file": ["file", "csv", "json", "yaml", "excel", "spreadsheet", "document", "path"],
        "database": ["database", "db", "postgres", "mysql", "sqlite", "mongodb", "query"],
        "api": ["api", "endpoint", "rest", "graphql", "url", "http", "service", "upstox"],
        "message_queue": ["queue", "kafka", "redis", "rabbitmq", "pubsub", "channel"],
        "notification": ["slack", "telegram", "email", "webhook", "alert", "notification"],
    }

    def __init__(self, registry_manager: RegistryManager):
        self.registry = registry_manager

    def classify_intent(self, intent_text: str) -> IntentClassification:
        """Classifies a natural language intent into structured entities and skill templates."""
        entities = self._extract_entities(intent_text)
        primary = self._determine_primary_action(entities)
        template = self._suggest_skill_template(primary, entities)
        confidence = self._compute_confidence(entities, primary, template)

        return IntentClassification(
            original_intent=intent_text,
            entities=entities,
            primary_action=primary,
            confidence=confidence,
            suggested_skill_template=template,
        )

    def _extract_entities(self, text: str) -> List[IntentEntity]:
        """Extracts action-target pairs from natural language text."""
        # Split into clauses
        clauses = re.split(r'[,\s]+and\s+|,\s*|\.\s+', text)
        clauses = [c.strip() for c in clauses if c.strip()]

        entities = []
        for clause in clauses:
            words = clause.lower().split()
            if not words:
                continue

            # Identify action verb (first verb-like word)
            action = words[0]
            for word in words:
                if word in [v for verbs in self.ACTION_PATTERNS.values() for v in verbs["verbs"]]:
                    action = word
                    break

            # Identify target (noun after action)
            target = ""
            modifiers = []
            try:
                action_idx = words.index(action)
                target_words = words[action_idx + 1 : action_idx + 4]  # next 3 words
                target = " ".join(target_words).strip()

                # Extract modifiers (qualifiers like "from Upstox", "to file")
                modifier_patterns = [
                    r'from\s+(\w+)',
                    r'to\s+(\w+)',
                    r'via\s+(\w+)',
                    r'using\s+(\w+)',
                    r'in\s+(\w+)',
                ]
                for pattern in modifier_patterns:
                    matches = re.findall(pattern, clause, re.IGNORECASE)
                    modifiers.extend(matches)
            except ValueError:
                pass

            entities.append(IntentEntity(
                action=action,
                target=target,
                modifiers=modifiers,
                raw_text=clause,
            ))

        return entities

    def _determine_primary_action(self, entities: List[IntentEntity]) -> str:
        """Determines the primary action from extracted entities."""
        if not entities:
            return "unknown"

        # Look for highest-priority action
        for entity in entities:
            for action_name, action_info in self.ACTION_PATTERNS.items():
                if entity.action in action_info["verbs"]:
                    return action_name

        # Fallback to first entity's action
        return entities[0].action

    def _suggest_skill_template(self, primary_action: str, entities: List[IntentEntity]) -> Optional[str]:
        """Suggests a skill template based on the primary action and entities."""
        action_info = self.ACTION_PATTERNS.get(primary_action)
        if not action_info:
            return None

        template = action_info["template"]

        # Refine based on target systems
        for entity in entities:
            target_lower = entity.target.lower() + " " + " ".join(entity.modifiers).lower()
            for target_type, keywords in self.TARGET_PATTERNS.items():
                if any(kw in target_lower for kw in keywords):
                    template = f"{target_type}_{template}"
                    break

        return template

    def _compute_confidence(self, entities: List[IntentEntity], primary: str, template: Optional[str]) -> float:
        """Computes confidence score for the classification."""
        if not entities:
            return 0.3

        # Check if primary action is in known patterns
        action_conf = 0.7 if primary in self.ACTION_PATTERNS else 0.4

        # Check if template exists in registry
        template_conf = 0.9 if template and self._template_exists(template) else 0.5

        # Check if entities have targets
        target_conf = 0.8 if any(e.target for e in entities) else 0.5

        # Weighted average
        confidence = (action_conf * 0.4 + template_conf * 0.35 + target_conf * 0.25)
        return round(confidence, 2)

    def _template_exists(self, template_id: str) -> bool:
        """Checks if a template exists in the registry."""
        try:
            return self.registry.get_template(template_id) is not None
        except Exception:
            return False

    def resolve_with_vector_fallback(self, intent_text: str, active_namespaces: List[str]) -> List[Dict[str, Any]]:
        """Combines pattern classification with vector similarity search for best results."""
        classification = self.classify_intent(intent_text)

        # Get vector search results
        vector_results = self.registry.search_skills(query=intent_text, active_namespaces=active_namespaces, limit=5)

        combined = []

        # Add pattern-based suggestion if confident enough
        if classification.confidence >= 0.6 and classification.suggested_skill_template:
            combined.append({
                "skill_id": classification.suggested_skill_template,
                "score": classification.confidence,
                "source": "pattern",
                "classification": classification.model_dump(),
            })

        # Add vector results
        for res in vector_results:
            combined.append({
                "skill_id": res["skill"].id,
                "score": res["score"],
                "source": "vector",
                "classification": None,
            })

        # Sort by score descending
        combined.sort(key=lambda x: x["score"], reverse=True)

        return combined[:5]

    def parse_intent_steps(self, intent_text: str) -> List[str]:
        """Splits multi-step pipeline intent into semantic step clauses (enhanced version)."""
        # Try pattern-based splitting first
        raw_lines = [line.strip() for line in intent_text.splitlines() if line.strip()]
        steps = []

        for line in raw_lines:
            # Split on "and", comma, or semicolon
            sub_steps = re.split(r'\s+and\s+|,\s*|;\s*', line)
            for s in sub_steps:
                s = s.strip()
                if s:
                    steps.append(s)

        return steps if steps else [intent_text]