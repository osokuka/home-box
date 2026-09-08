"""Exceptions for HLK-DIO16."""


class HlkDio16Error(Exception):
    """Base error for HLK-DIO16."""


class HlkDio16ConnectionError(HlkDio16Error):
    """TCP connection failed or was lost."""


class HlkDio16ProtocolError(HlkDio16Error):
    """Invalid or unexpected protocol frame."""


class HlkDio16TimeoutError(HlkDio16Error):
    """Timed out waiting for a response."""
