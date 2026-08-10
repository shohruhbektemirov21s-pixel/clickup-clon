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


class RefreshRateThrottle(SimpleRateThrottle):
    """Per-source bound on `POST auth/refresh/`.

    The endpoint is `AllowAny` — a client that needs a new access token has no
    valid one to authenticate with — and every *successful* call performs two
    writes (rotate the refresh token, blacklist the old one). Without a bound,
    an anonymous client can drive unlimited inserts into the SimpleJWT tables.

    ``DEFAULT_RATE`` is a fallback, not the intended configuration: the rate
    belongs in ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["refresh"]`` next to
    the other scopes. Until that key exists, a missing scope must not turn into
    an ``ImproperlyConfigured`` 500 on a public endpoint, so ``get_rate()``
    falls back instead of raising.

    The default is deliberately loose. The key is the source address, and with
    ``NUM_PROXIES`` set correctly a whole office behind one NAT address shares
    a bucket, so a tight limit would lock out real users long before it
    inconvenienced an attacker. 30/min still turns "unbounded" into a
    bounded, alertable cost.
    """

    scope = "refresh"
    DEFAULT_RATE = "30/min"

    def get_rate(self):
        return self.THROTTLE_RATES.get(self.scope) or self.DEFAULT_RATE

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }
