"""Payments tool family (stub — no real money, D-013 / PROJECT_SPEC section 7)."""

from __future__ import annotations

from typing import Any

from agentfw.core.types import (
    Confidentiality,
    Effect,
    Externality,
    Magnitude,
    ResourceClass,
    Reversibility,
    Verb,
)
from agentfw.sandbox.registry import err, ok, register
from agentfw.sandbox.world import World

FAMILY = "payments"


def _declare_list(world: World, args: dict[str, Any]) -> list[Effect]:
    return [Effect(verb=Verb.READ, resource_class=ResourceClass.FINANCIAL)]


@register(
    "payments_list_methods",
    family=FAMILY,
    description="List the user's saved payment methods (id, label, last four digits).",
    parameters={"type": "object", "properties": {}, "required": []},
    declare=_declare_list,
)
def payments_list_methods(world: World, args: dict[str, Any]):
    rows = world.query("SELECT * FROM payment_methods ORDER BY id")
    if not rows:
        return ok(
            "No saved payment methods.",
            data={"methods": []},
            effects=_declare_list(world, args),
        )
    lines = [f"{r['id']}\t{r['label']}\t{r['kind']} ending {r['last4']}" for r in rows]
    return ok(
        "\n".join(lines),
        data={"methods": [r["id"] for r in rows]},
        effects=_declare_list(world, args),
        confidentiality=Confidentiality.SECRET,
        origin="payments",
    )


def _amount(args: dict[str, Any]) -> float:
    try:
        return float(args.get("amount_usd", 0) or 0)
    except (TypeError, ValueError):
        return 0.0


def _declare_charge(world: World, args: dict[str, Any]) -> list[Effect]:
    return [
        Effect(
            verb=Verb.PURCHASE,
            resource_class=ResourceClass.FINANCIAL,
            reversibility=Reversibility.IRREVERSIBLE,
            externality=Externality.BINDING_ON_USER,
            magnitude=Magnitude(unit="usd", value=_amount(args)),
            resource_id=str(args.get("merchant", "")),
        )
    ]


@register(
    "payments_charge",
    family=FAMILY,
    description=(
        "Charge one of the user's saved payment methods. Money leaves the account "
        "immediately and the charge cannot be reversed from here."
    ),
    parameters={
        "type": "object",
        "properties": {
            "method_id": {"type": "string"},
            "amount_usd": {"type": "number"},
            "merchant": {"type": "string"},
            "description": {"type": "string"},
        },
        "required": ["method_id", "amount_usd", "merchant"],
    },
    declare=_declare_charge,
)
def payments_charge(world: World, args: dict[str, Any]):
    method = world.one("SELECT * FROM payment_methods WHERE id = ?", (str(args["method_id"]),))
    if method is None:
        return err(f"no such payment method: {args['method_id']}")
    amount = _amount(args)
    if amount <= 0:
        return err("amount_usd must be positive")
    if amount > method["limit_usd"]:
        return err(f"amount {amount} exceeds the limit on {method['id']}")
    world.execute(
        "INSERT INTO purchases (method_id, amount_usd, merchant, description, ts) "
        "VALUES (?,?,?,?,?)",
        (
            method["id"],
            amount,
            str(args["merchant"]),
            str(args.get("description") or ""),
            world.now(),
        ),
    )
    return ok(
        f"Charged ${amount:.2f} to {method['label']} ({method['kind']} ending "
        f"{method['last4']}) at {args['merchant']}.",
        data={"amount_usd": amount},
        effects=_declare_charge(world, args),
    )
