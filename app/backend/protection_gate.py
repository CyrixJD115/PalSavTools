"""HTTP protection gate — single middleware that enforces protection rules
and the whole-save edit lock across all mutation endpoints.

One file gates ~40 endpoints (and any future ones) by mapping the request
method + path to a (target_type, target_id) tuple, then delegating to
:func:`protection_service.evaluate_request`. Per-router ``Depends()`` would
be ~40 touch-points — rejected as non-lazy.

Exempt prefixes (never blocked, even under save lock): save lifecycle
(load/upload/persist/export/unload), the protection API itself, health,
and the read-only / pure-calc routers. Deliberate transform tools
(``/api/tools/*``) are also exempt for now — gating them needs per-tool
semantics; add a ``tools`` action class when required.

Blocked requests get ``409 Conflict`` with a JSON body the frontend can
surface: ``{"detail": {"reason": "rule_match"|"save_edit_locked",
"target_type": ..., "target_id": ..., "action": ...}}``.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.backend.services import protection_service
from app.backend.state import save_state

# Methods that can mutate state. GET / HEAD / OPTIONS always pass.
_WRITE_METHODS = frozenset({"DELETE", "PUT", "POST", "PATCH"})

# Path prefixes (after stripping ``/api/``) that are never gated, even when
# the whole save is edit-locked. These are lifecycle, diagnostic, or the
# protection API itself.
_EXEMPT_PREFIXES = (
    "save/",          # load / upload / persist / export / unload / state
    "protection/",    # the protection API — must work while locked
    "health",         # liveness
    "breeding/",      # pure calculator, no save mutation
    "tools/",         # deliberate transforms (deferred — see module docstring)
)


class ProtectionGateMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method.upper()
        if method not in _WRITE_METHODS:
            return await call_next(request)

        # Strip the /api/ prefix; non-API paths (static assets, /ws) pass.
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)
        after_api = path[len("/api/"):]

        # Exempt prefixes always pass (even under save lock).
        if after_api.startswith(_EXEMPT_PREFIXES):
            return await call_next(request)

        loaded = save_state.get()
        if loaded is None:
            return await call_next(request)  # nothing to protect

        # The engine handles both edit_locked (master switch) and per-rule
        # checks. Parsed target is None for non-gated resources (pals,
        # containers, world) — those only block under edit_locked.
        # Fail-open: any unexpected error in the gate lets the request through
        # (the route handlers still validate normally). A protection feature
        # must never turn a normal request into a 500.
        try:
            parsed = protection_service._parse_target(after_api)
            block = protection_service.evaluate_request(
                loaded, method, after_api, parsed=parsed,
            )
        except Exception:
            return await call_next(request)
        if block is None:
            return await call_next(request)

        return JSONResponse(
            status_code=409,
            content={"detail": block},
            headers={"X-Protection-Block": block["reason"]},
        )


def install_protection_gate(app) -> None:
    """One-line wiring for the app factory."""
    app.add_middleware(ProtectionGateMiddleware)
