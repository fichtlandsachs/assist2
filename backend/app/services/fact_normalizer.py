"""Fact Normalizer - Normalizes fact values per category."""
from __future__ import annotations

import re
from typing import Optional


class FactNormalizer:
    """Normalizes fact values based on category-specific rules."""

    # Role mappings for normalization
    ROLE_MAPPINGS = {
        "orgadmins": "OrgAdmin",
        "orgadmin": "OrgAdmin",
        "org-admins": "OrgAdmin",
        "org-admin": "OrgAdmin",
        "organisationsadmin": "OrgAdmin",
        "organisationsadmins": "OrgAdmin",
        "fachbereichsleiter": "Fachbereichsleiter",
        "fachbereichsleitung": "Fachbereichsleiter",
        "abteilungsleiter": "Abteilungsleiter",
        "abteilungsleitung": "Abteilungsleiter",
        "entwickler": "Entwickler",
        "developer": "Entwickler",
        "dev": "Entwickler",
        "programmierer": "Entwickler",
        "product owner": "Product Owner",
        "po": "Product Owner",
        "produkt owner": "Product Owner",
        "scrum master": "Scrum Master",
        "sm": "Scrum Master",
        "team lead": "Team Lead",
        "teamleiter": "Team Lead",
        "tech lead": "Tech Lead",
        "admin": "Admin",
        "administrator": "Admin",
        "superadmin": "Superadmin",
    }

    # System name mappings
    SYSTEM_MAPPINGS = {
        "jira": "Jira",
        "confluence": "Confluence",
        "github": "GitHub",
        "gitlab": "GitLab",
        "salesforce": "Salesforce",
        "sap": "SAP",
        "servicenow": "ServiceNow",
        "postgresql": "PostgreSQL",
        "postgres": "PostgreSQL",
        "mysql": "MySQL",
        "mariadb": "MariaDB",
        "redis": "Redis",
    }

    @staticmethod
    def normalize_role(value: str) -> str:
        """Normalize role names."""
        lower = value.lower().strip()

        # Check exact mappings
        if lower in FactNormalizer.ROLE_MAPPINGS:
            return FactNormalizer.ROLE_MAPPINGS[lower]

        # Try to extract role from longer text
        for key, normalized in FactNormalizer.ROLE_MAPPINGS.items():
            if key in lower:
                return normalized

        # Default: title case, remove plural
        value = value.strip()
        if value.endswith("s") and len(value) > 3:
            value = value[:-1]

        return value

    @staticmethod
    def normalize_system(value: str) -> str:
        """Normalize system names."""
        lower = value.lower().strip()

        if lower in FactNormalizer.SYSTEM_MAPPINGS:
            return FactNormalizer.SYSTEM_MAPPINGS[lower]

        for key, normalized in FactNormalizer.SYSTEM_MAPPINGS.items():
            if key in lower:
                return normalized

        return value.strip()

    @staticmethod
    def normalize_target_user(value: str) -> str:
        """Normalize target user values."""
        return FactNormalizer.normalize_role(value)

    @staticmethod
    def normalize_affected_system(value: str) -> str:
        """Normalize affected system values."""
        return FactNormalizer.normalize_system(value)

    @staticmethod
    def normalize_business_capability(value: str) -> str:
        """Normalize business capability values."""
        value = value.strip()
        # Title case
        return value[0].upper() + value[1:] if value else value

    @staticmethod
    def normalize_acceptance_criteria(value: str) -> str:
        """Normalize acceptance criteria - minimal changes."""
        # Keep testable statement, just trim
        value = value.strip()
        # Ensure it starts with a verb-like structure
        # but don't modify the content significantly
        return value

    @staticmethod
    def normalize_generic(value: str) -> str:
        """Generic normalization - trim and lowercase for comparison."""
        return value.lower().strip()

    @staticmethod
    def normalize(value: str, category: str) -> str:
        """Normalize a fact value based on its category."""
        if not value:
            return ""

        normalizers = {
            "target_user": FactNormalizer.normalize_target_user,
            "target_users": FactNormalizer.normalize_target_user,
            "affected_system": FactNormalizer.normalize_affected_system,
            "affected_systems": FactNormalizer.normalize_affected_system,
            "business_capability": FactNormalizer.normalize_business_capability,
            "business_capabilities": FactNormalizer.normalize_business_capability,
            "acceptance_criteria": FactNormalizer.normalize_acceptance_criteria,
            "acceptance_criterion": FactNormalizer.normalize_acceptance_criteria,
        }

        normalizer = normalizers.get(category, FactNormalizer.normalize_generic)
        return normalizer(value)

    @staticmethod
    def calculate_similarity(value1: str, value2: str, category: str) -> float:
        """Calculate similarity between two normalized values."""
        norm1 = FactNormalizer.normalize(value1, category)
        norm2 = FactNormalizer.normalize(value2, category)

        # Exact match
        if norm1 == norm2:
            return 1.0

        # Word overlap
        words1 = set(norm1.split())
        words2 = set(norm2.split())

        if not words1 or not words2:
            return 0.0

        intersection = words1 & words2
        union = words1 | words2

        if not union:
            return 0.0

        jaccard = len(intersection) / len(union)

        # Boost for high overlap
        if jaccard > 0.7:
            return jaccard + 0.1

        return jaccard
