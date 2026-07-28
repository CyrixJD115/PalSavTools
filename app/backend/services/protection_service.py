"""Protection rule engine — pure functions, no per-instance state.

A rule blocks one or more actions (``delete`` / ``edit``) on one target entity
(player / guild / base). Rules are held on ``LoadedSave.protection_rules`` and
pushed from the frontend (localStorage is the source of truth).

Cascade: when a guild rule has ``cascade=True``, it implicitly protects the
guild's base_ids and member player_uids from the rule's actions. Cascade
coverage is resolved on demand against the live save via a ``build_mini_wsd``
slice (GroupSaveDataMap + BaseCampSaveData, ~3 MB — never ``level_dict``).

The backend HTTP gate (``app/backend/protection_gate.py``) calls
:func:`evaluate_request`; the legacy CLI path calls :func:`is_blocked` directly.
"""

from __future__ import annotations

from typing import Any, Iterable

from app.backend.services.world_service import (
    _g, _gplayers, _group_type, _k, _map_entries, _norm_uid, _s,
)
from app.backend.services.base_service import _s as _norm_str

Action = str  # "delete" | "edit"


def _matching_rules(
    rules: Iterable[dict[str, Any]],
    target_type: str,
    target_id: str,
) -> list[dict[str, Any]]:
    """Direct rules whose target_id matches (normalized)."""
    tid = _norm_str(target_id)
    return [
        r for r in rules
        if r.get("target_type") == target_type and _norm_str(r.get("target_id")) == tid
    ]


def _find_guild_in_wsd(wsd: dict, guild_id: str) -> dict | None:
    """Find a guild entry inside a wsd-shaped dict (mini or full).

    ``wsd`` follows the service convention: a dict whose keys are
    ``GroupSaveDataMap_0``, ``BaseCampSaveData_0``, … (``_k`` does the suffix
    fallback). Not the full ``level_dict``.
    """
    gid_clean = _norm_str(guild_id)
    for g in _map_entries(wsd, "GroupSaveDataMap"):
        if _group_type(g) != "EPalGroupType::Guild":
            continue
        if _norm_str(g.get("key")) == gid_clean:
            return g
    return None


def guild_cascade_targets(wsd: dict, guild_id: str) -> tuple[set[str], set[str]]:
    """Return (base_ids, player_uids) belonging to a guild — read-only walk.

    Uses only ``GroupSaveDataMap`` + ``BaseCampSaveData`` (already in the
    mini_wsd slice). Mirrors the same walk as ``guild_service.delete_guild``
    but without mutating anything. Returns empty sets if the guild isn't found.
    """
    base_ids: set[str] = set()
    player_uids: set[str] = set()
    g = _find_guild_in_wsd(wsd, guild_id)
    if g is None:
        return base_ids, player_uids
    # Members from the guild tail.
    for p in _gplayers(g):
        puid = _norm_uid(_k(p, "player_uid"))
        if puid:
            player_uids.add(_norm_str(puid))
    # Bases owned by this guild.
    gid_clean = _norm_str(guild_id)
    for b in _map_entries(wsd, "BaseCampSaveData"):
        bgid = _norm_uid(_g(b, "value", "RawData", "group_id_belong_to"))
        if _norm_str(bgid) == gid_clean:
            bid = b.get("key")
            if bid is not None:
                base_ids.add(_norm_str(bid))
    return base_ids, player_uids


def is_blocked(
    rules: Iterable[dict[str, Any]],
    target_type: str,
    target_id: str,
    action: Action,
    wsd: dict | None = None,
) -> bool:
    """True if any rule blocks ``action`` on (target_type, target_id).

    1) Direct rules on this exact target are checked first.
    2) Guild-cascade rules: a guild rule with ``cascade=True`` covers its
       bases + members. Resolved against the provided ``wsd`` (mini slice).
       If ``wsd`` is None, cascade can't be resolved and only direct rules
       apply (returns False for cascade-only coverage — fail-open, since the
       legacy direct checks never had cascade).

    ``action`` is matched case-insensitively against each rule's ``actions``.
    """
    rules = list(rules)
    tid = _norm_str(target_id)

    # 1) Direct rules on this exact target.
    for r in _matching_rules(rules, target_type, target_id):
        if action in [str(a).lower() for a in r.get("actions", [])]:
            return True

    # 2) Guild-cascade rules.
    if wsd is not None:
        for gr in rules:
            if gr.get("target_type") != "guild" or not gr.get("cascade", True):
                continue
            if action not in [str(a).lower() for a in gr.get("actions", [])]:
                continue
            base_ids, player_uids = guild_cascade_targets(wsd, gr.get("target_id", ""))
            if target_type == "base" and tid in base_ids:
                return True
            if target_type == "player" and tid in player_uids:
                return True
    return False


def is_save_locked(loaded) -> bool:
    """True if the whole save is edit-locked (master switch)."""
    return bool(getattr(loaded, "edit_locked", False))


# ---------------------------------------------------------------------------
# HTTP-request evaluation (used by the backend gate middleware)
# ---------------------------------------------------------------------------

# (path-prefix-after-/api, HTTP-method → action). DELETE methods map to
# "delete"; everything else (PUT/POST/PATCH) maps to "edit". Kept here so the
# rule engine owns the action vocabulary; the gate owns path → target parsing.
_METHOD_ACTION = {
    "DELETE": "delete",
    "PUT": "edit",
    "POST": "edit",
    "PATCH": "edit",
}


def evaluate_request(
    loaded,
    method: str,
    path_after_api: str,
    parsed: tuple[str, str] | None = None,
) -> dict[str, Any] | None:
    """Return a block-reason dict if the request is blocked, else None.

    ``path_after_api`` is the request path with the ``/api`` prefix stripped,
    e.g. ``"players/abc-123"`` or ``"guilds/xyz/members/p1"``.

    ``parsed`` is an optional ``(target_type, target_id)`` tuple from the
    gate's path parser; when None, this function does simple prefix matching
    against the known resource roots. Keeping the parser in the gate keeps
    this module FastAPI-agnostic and unit-testable.

    A blocked request returns ``{"reason": str, "target_type": str,
    "target_id": str, "action": str}`` so the gate can build a precise 409.
    """
    if is_save_locked(loaded):
        return {
            "reason": "save_edit_locked",
            "target_type": "save",
            "target_id": "",
            "action": _METHOD_ACTION.get(method.upper(), "edit"),
        }

    action = _METHOD_ACTION.get(method.upper())
    if action is None:
        return None  # GET / HEAD / OPTIONS — never blocked.

    target_type, target_id = parsed or _parse_target(path_after_api)
    if target_type is None or target_id is None:
        return None  # Not a gated resource.

    # Cascade resolution needs the guild/base slice. Build it lazily and only
    # when at least one cascading guild rule exists (avoid the slice otherwise).
    # Fail-open on infrastructure errors (handle missing, section decode error):
    # a protection gate must never turn a rule check into a 500 — direct rules
    # still apply, only cascade coverage is skipped on resolution failure.
    rules = list(getattr(loaded, "protection_rules", []))
    wsd = None
    if any(r.get("target_type") == "guild" and r.get("cascade", True) for r in rules):
        try:
            wsd = loaded.build_mini_wsd("GroupSaveDataMap", "BaseCampSaveData")
        except Exception:
            wsd = None  # cascade only; direct rules below still enforce

    if is_blocked(rules, target_type, target_id, action, wsd=wsd):
        return {
            "reason": "rule_match",
            "target_type": target_type,
            "target_id": target_id,
            "action": action,
        }
    return None


# Path → (target_type, target_id) for the resources we protect.
# ``parsed`` from the gate overrides this; kept here as a fallback / for tests.
_PREFIX_TABLE = (
    ("players/", "player", 0),
    ("guilds/", "guild", 0),
    ("bases/", "base", 0),
    ("pals/", "pal", 0),
    # containers are NOT gated as a target type — container slots are
    # per-item mutations, not entity-level protection. Leave them to
    # per-save edit_lock only.
)


def _parse_target(path_after_api: str) -> tuple[str | None, str | None]:
    """Best-effort path → (target_type, target_id). Returns (None, None) if
    the path isn't a directly-gated resource."""
    for prefix, ttype, seg_idx in _PREFIX_TABLE:
        if path_after_api.startswith(prefix):
            rest = path_after_api[len(prefix):]
            segs = rest.split("/")
            if seg_idx < len(segs) and segs[seg_idx]:
                return ttype, segs[seg_idx]
            return ttype, None
    return None, None


def find_protected_children(
    loaded,
    guild_id: str,
    action: Action = "delete",
) -> list[dict[str, Any]]:
    """Detect protected entities that a guild deletion would sweep up.

    ``delete_guild`` transitively removes the guild's bases AND removes the
    member players' character entries — so deleting an unprotected guild can
    destroy a base or player that has its OWN direct protection rule. The gate
    can't see this from a URL alone; the route handler must call this before
    the mutation.

    Returns a list of ``{target_type, target_id, rule_ids}`` dicts for every
    protected child that ``action`` would hit. Empty list = safe to proceed.
    """
    rules = list(getattr(loaded, "protection_rules", []))
    if not rules:
        return []
    try:
        wsd = loaded.build_mini_wsd("GroupSaveDataMap", "BaseCampSaveData")
    except Exception:
        return []  # can't resolve → fail-open (gate + direct rules still apply)
    base_ids, player_uids = guild_cascade_targets(wsd, guild_id)
    hits: list[dict[str, Any]] = []
    for bid in base_ids:
        if is_blocked(rules, "base", bid, action, wsd=None):
            hits.append({
                "target_type": "base", "target_id": bid,
                "rule_ids": [r["id"] for r in _matching_rules(rules, "base", bid)],
            })
    for puid in player_uids:
        if is_blocked(rules, "player", puid, action, wsd=None):
            hits.append({
                "target_type": "player", "target_id": puid,
                "rule_ids": [r["id"] for r in _matching_rules(rules, "player", puid)],
            })
    return hits


# ---------------------------------------------------------------------------
# Self-check (assert-based, no framework). Run with:
#   uv run python -m app.backend.services.protection_service
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    rules = [
        {"id": "1", "target_type": "player", "target_id": "P1",
         "actions": ["delete"], "cascade": True, "source": "manual"},
        {"id": "2", "target_type": "guild", "target_id": "G1",
         "actions": ["delete", "edit"], "cascade": True, "source": "manual"},
        {"id": "3", "target_type": "base", "target_id": "B2",
         "actions": ["edit"], "cascade": False, "source": "manual"},
    ]

    # Mini-wsd fixture (service convention: keys with _0 suffix, flat lists).
    # Guild G1 owns base B1 and has member P2. Guild G2 owns base B3.
    WSD = {
        "GroupSaveDataMap_0": [
            {
                "key": "G1",
                "value": {
                    "GroupType": "EPalGroupType::Guild",
                    "RawData": {"data": {"Guild": {
                        "tail": {"PostUpdate": {
                            "admin_player_uid": "P2",
                            "players": [{"player_uid": "P2"}],
                        }},
                    }}},
                },
            },
            {
                "key": "G2",
                "value": {
                    "GroupType": "EPalGroupType::Guild",
                    "RawData": {"data": {"Guild": {
                        "tail": {"PostUpdate": {
                            "admin_player_uid": "P9",
                            "players": [{"player_uid": "P9"}],
                        }},
                    }}},
                },
            },
        ],
        "BaseCampSaveData_0": [
            {"key": "B1", "value": {"RawData": {"group_id_belong_to": "G1"}}},
            {"key": "B3", "value": {"RawData": {"group_id_belong_to": "G2"}}},
        ],
    }

    # Direct blocks.
    assert is_blocked(rules, "player", "P1", "delete") is True, "direct player delete"
    assert is_blocked(rules, "player", "P1", "edit") is False, "direct player not edit"
    assert is_blocked(rules, "base", "B2", "edit") is True, "direct base edit"
    assert is_blocked(rules, "base", "B2", "delete") is False, "base edit-only not delete"
    assert is_blocked(rules, "guild", "G1", "delete") is True, "direct guild delete"
    assert is_blocked(rules, "guild", "G1", "edit") is True, "direct guild edit"

    # Cascade via wsd: G1 protects B1 and member P2 (delete + edit).
    assert is_blocked(rules, "base", "B1", "delete", wsd=WSD) is True, "cascade base delete"
    assert is_blocked(rules, "base", "B1", "edit", wsd=WSD) is True, "cascade base edit"
    assert is_blocked(rules, "player", "P2", "delete", wsd=WSD) is True, "cascade player delete"

    # Cascade unresolved without wsd → fail-open (must NOT block).
    assert is_blocked(rules, "base", "B1", "delete", wsd=None) is False, \
        "cascade unresolved without wsd must not block"

    # Reverse-cascade: a rule directly protecting base B2 means deleting its
    # parent guild G2 would destroy a protected child. find_protected_children
    # must surface this even though G2 itself has no rule.
    reverse_rules = [
        {"id": "rb2", "target_type": "base", "target_id": "B2",
         "actions": ["delete"], "cascade": False, "source": "manual"},
    ]
    # G2 owns B3 (unprotected) → no hits.
    class _FL2:
        protection_rules = reverse_rules
        def build_mini_wsd(self, *names):
            return WSD
    assert find_protected_children(_FL2(), "G2", "delete") == [], \
        "G2 has no protected children (B3 unprotected)"
    # If B3 had a rule, G2 deletion would be blocked. Simulate by adding a rule.
    _FL2.protection_rules = [
        {"id": "rb3", "target_type": "base", "target_id": "B3",
         "actions": ["delete"], "cascade": False, "source": "manual"},
    ]
    hits = find_protected_children(_FL2(), "G2", "delete")
    assert len(hits) == 1 and hits[0]["target_id"] == "b3", \
        f"G2 deletion should hit protected base B3: {hits}"
    # Nonexistent guild → no hits (fail-open).
    assert find_protected_children(_FL2(), "NOPE", "delete") == [], \
        "nonexistent guild → no protected children"

    # Path parsing.
    assert _parse_target("players/P1") == ("player", "P1"), "parse player"
    assert _parse_target("guilds/G1/members/P2") == ("guild", "G1"), "parse guild keeps id"
    assert _parse_target("bases/B1") == ("base", "B1"), "parse base"
    assert _parse_target("health") == (None, None), "non-gated passthrough"

    # Fake loaded object for evaluate_request.
    class _FakeLoaded:
        edit_locked = False
        protection_rules = rules
        def build_mini_wsd(self, *names):
            return WSD

    blocked = evaluate_request(_FakeLoaded(), "DELETE", "players/P1")
    assert blocked and blocked["reason"] == "rule_match" and blocked["action"] == "delete", \
        f"evaluate delete player: {blocked}"

    blocked = evaluate_request(_FakeLoaded(), "PUT", "players/P1/name")
    assert blocked is None, f"PUT on delete-only player should pass: {blocked}"

    blocked = evaluate_request(_FakeLoaded(), "DELETE", "bases/B1")
    assert blocked and blocked["reason"] == "rule_match", f"cascade base delete via gate: {blocked}"

    _FakeLoaded.edit_locked = True
    blocked = evaluate_request(_FakeLoaded(), "PUT", "players/other/name")
    assert blocked and blocked["reason"] == "save_edit_locked", f"save lock: {blocked}"
    _FakeLoaded.edit_locked = False

    print("protection_service self-check: OK")
