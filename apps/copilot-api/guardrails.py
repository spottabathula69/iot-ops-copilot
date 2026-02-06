"""
Basic guardrails for copilot API.

Includes prompt injection detection and PII detection.
"""

import re
from typing import List, Dict


class Guardrails:
    """Security and safety guardrails for LLM inputs/outputs."""
    
    # Prompt injection patterns
    INJECTION_PATTERNS = [
        r"ignore\s+(previous|all|the)\s+(instructions?|rules?|prompts?)",
        r"disregard\s+(previous|all|the)",
        r"forget\s+(everything|all|previous)",
        r"new\s+instructions?:",
        r"system\s*:\s*you\s+are",
        r"<\s*\/?system\s*>",
        r"sudo\s+mode",
        r"developer\s+mode",
        r"jailbreak",
        r"pretend\s+(you|to)\s+(are|be)",
    ]
    
    # PII patterns
    PII_PATTERNS = {
        'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
        'credit_card': r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b',
        'phone': r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
    }
    
    @classmethod
    def detect_prompt_injection(cls, text: str) -> Dict[str, any]:
        """
        Detect potential prompt injection attempts.
        
        Args:
            text: Input text to check
        
        Returns:
            Dict with 'detected' (bool) and 'patterns' (list of matched patterns)
        """
        text_lower = text.lower()
        matched_patterns = []
        
        for pattern in cls.INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                matched_patterns.append(pattern)
        
        return {
            'detected': len(matched_patterns) > 0,
            'patterns': matched_patterns,
            'severity': 'high' if matched_patterns else 'none'
        }
    
    @classmethod
    def detect_pii(cls, text: str) -> Dict[str, any]:
        """
        Detect personally identifiable information.
        
        Args:
            text: Text to scan for PII
        
        Returns:
            Dict with 'detected' (bool) and 'types' (list of PII types found)
        """
        found_pii = []
        
        for pii_type, pattern in cls.PII_PATTERNS.items():
            if re.search(pattern, text):
                found_pii.append(pii_type)
        
        return {
            'detected': len(found_pii) > 0,
            'types': found_pii,
            'severity': 'high' if found_pii else 'none'
        }
    
    @classmethod
    def check_input(cls, text: str) -> Dict[str, any]:
        """
        Run all input checks.
        
        Args:
            text: User input to validate
        
        Returns:
            Dict with check results and whether input is safe
        """
        injection_check = cls.detect_prompt_injection(text)
        pii_check = cls.detect_pii(text)
        
        is_safe = not (injection_check['detected'] or pii_check['detected'])
        
        return {
            'safe': is_safe,
            'injection': injection_check,
            'pii': pii_check,
            'warnings': [
                'Potential prompt injection detected' if injection_check['detected'] else None,
                'PII detected in input' if pii_check['detected'] else None
            ]
        }
