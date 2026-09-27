"""django-axes reads the username from a "username" field; sign-in here is by email,
which allauth passes as `email` (and posts as `login`)."""


def username(request, credentials=None):
    for source in (credentials or {}, getattr(request, "POST", {})):
        for key in ("email", "username", "login"):
            value = source.get(key)
            if value:
                return str(value).strip().lower()
    return None
