"""Throttles for the authentication endpoints.

IP-based throttling alone does not stop credential stuffing: an attacker with a
proxy pool gets a fresh bucket per address while the victim's account keeps
absorbing guesses. These throttles key on the *account* instead, so the cost of
attacking one account is the same no matter how many source addresses are used.
"""

import hashlib

from rest_framework.throttling import SimpleRateThrottle


class LoginEmailThrottle(SimpleRateThrottle):
    """Rate-limit login attempts per submitted email address.

    Stack this next to the IP-based ScopedRateThrottle; the two are independent
    buckets and a request must pass both.
    """

    scope = "auth_burst"

    def get_cache_key(self, request, view):
        try:
            data = request.data
        except Exception:
            # Unparseable body — the view will reject it; nothing to key on.
            return None
        if not hasattr(data, "get"):
            return None
        email = data.get("email")
        if not isinstance(email, str):
            return None
        email = email.strip().lower()
        if not email:
            return None
        # Hashed so raw addresses never land in the cache backend (which may be
        # a shared Redis) as plaintext keys.
        ident = hashlib.sha256(email.encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}
