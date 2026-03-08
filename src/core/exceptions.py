"""Custom exceptions for the invoice processing pipeline."""


class IngestionError(Exception):
    """Raised when invoice extraction fails or validation gate rejects incomplete data."""


class LLMConfigurationError(Exception):
    """Raised when LLM extraction is requested but XAI_API_KEY is not configured."""


class VisionConfigurationError(Exception):
    """Raised when vision extraction is requested but XAI_API_KEY is not configured."""
