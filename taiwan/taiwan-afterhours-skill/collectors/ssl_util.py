# -*- coding: utf-8 -*-
"""SSL context for Windows / corporate CA issues when fetching TWSE/TAIFEX/cnyes."""
from __future__ import annotations

import ssl
import urllib.request


def ssl_context():
    """Prefer certifi CA bundle; fall back to unverified if local store is broken."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        pass
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()


_CTX = None
_UNVERIFIED = None


def urlopen(req, timeout=20):
    """urlopen with certifi; one retry with unverified context on CERTIFICATE_VERIFY_FAILED."""
    global _CTX, _UNVERIFIED
    if _CTX is None:
        _CTX = ssl_context()
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_CTX)
    except Exception as e:
        msg = str(e).lower()
        if "certificate" in msg or "ssl" in msg:
            if _UNVERIFIED is None:
                _UNVERIFIED = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED)
        raise
