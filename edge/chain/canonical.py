"""Canonical record: the exact bytes that get signed (Phase 4).

WHAT SIGNING DOES AND DOES NOT DO. Signatures and the hash chain protect records AFTER they are
signed. They detect edits, deletions, reordering and impersonation by someone without the key.
They do NOT stop a lie at the sensor before the device signs it: if the sensor input is false,
the device signs the false value. A sensor-level mimic liar needs attested or redundant sensors,
or out-of-band data (GPS, carrier records).

The format is language-neutral so another implementation (for example TypeScript) can reproduce
the same bytes. The full rules are in docs/01-architecture/signed-record-format.md; in short:

  * Only integers, strings and null. No floating-point numbers appear in the bytes.
  * Every real-valued field is converted to an integer in a fixed unit (see UNITS below). The
    conversion takes the shortest decimal text that round-trips the double (Python repr, which
    is also what JavaScript prints for a Number), multiplies that decimal EXACTLY by the unit and
    rounds half AWAY from zero (2.5 -> 3, -2.5 -> -3). It never rounds a binary double directly.
  * Canonical bytes = UTF-8 JSON, keys sorted by code point, no whitespace, no escaping of
    non-ASCII characters beyond what JSON requires, integers in plain decimal.
  * Integers must fit in +/- 2**53 so that JavaScript Numbers hold them exactly.
"""

from __future__ import annotations

import json
import math
from decimal import ROUND_HALF_UP, Context, Decimal

SCHEMA_VERSION = "pg-record/1"
MAX_SAFE_INT = 2**53

# unit = how many integer steps per one unit of the real value
UNIT_MS = 1000  # seconds -> milliseconds
UNIT_E4 = 10**4  # temperature, humidity, shock, ambient, cooling duty
UNIT_E9 = 10**9  # potency and shelf_life_used_fraction
UNIT_E6 = 10**6  # tau_eq_h and the bounds (hours)

# field name -> kind. "int" fields are plain integers already (seq); "str" are text.
FIELDS: dict[str, str] = {
    "schema": "str",
    "device_id": "str",
    "seq": "int",
    "t_ms": "int",
    "source": "str",
    "temp": "int",
    "rh": "int",
    "shock": "int",
    "ambient_c": "int?",
    "cooling_duty": "int?",
    "potency": "int",
    "shelf_life_used_fraction": "int",
    "tau_eq_h": "int",
    "verdict": "str",
    "trust_level": "str",
    "bound_tau_eq_h": "int?",
    "bound_low_tau_eq_h": "int?",
}

_CONTEXT = Context(prec=60)


def to_scaled_int(value: float | int | None, unit: int) -> int | None:
    """Real value -> integer in `unit` steps, rounding half away from zero (see module docs)."""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float) or not math.isfinite(value):
        raise ValueError(f"cannot scale {value!r}: need a finite number")
    exact = _CONTEXT.multiply(Decimal(repr(float(value))), Decimal(unit))
    magnitude = int(abs(exact).to_integral_value(rounding=ROUND_HALF_UP))
    result = -magnitude if exact < 0 else magnitude
    _check_safe(result)
    return result


def _check_safe(value: int) -> None:
    if abs(value) > MAX_SAFE_INT:
        raise ValueError(f"integer {value} does not fit in +/- 2**53")


def build_record(
    *,
    device_id: str,
    seq: int,
    t_s: float,
    source: str,
    temp_c: float,
    rh_pct: float,
    shock_g: float,
    ambient_c: float | None,
    cooling_duty: float | None,
    potency: float,
    shelf_life_used_fraction: float,
    tau_eq_h: float,
    verdict: str,
    trust_level: str,
    bound_tau_eq_h: float | None,
    bound_low_tau_eq_h: float | None,
) -> dict:
    """The record as a dict of integers, strings and None (units: see the module docs)."""
    record = {
        "schema": SCHEMA_VERSION,
        "device_id": device_id,
        "seq": seq,
        "t_ms": to_scaled_int(t_s, UNIT_MS),
        "source": source,
        "temp": to_scaled_int(temp_c, UNIT_E4),
        "rh": to_scaled_int(rh_pct, UNIT_E4),
        "shock": to_scaled_int(shock_g, UNIT_E4),
        "ambient_c": to_scaled_int(ambient_c, UNIT_E4),
        "cooling_duty": to_scaled_int(cooling_duty, UNIT_E4),
        "potency": to_scaled_int(potency, UNIT_E9),
        "shelf_life_used_fraction": to_scaled_int(shelf_life_used_fraction, UNIT_E9),
        "tau_eq_h": to_scaled_int(tau_eq_h, UNIT_E6),
        "verdict": verdict,
        "trust_level": trust_level,
        "bound_tau_eq_h": to_scaled_int(bound_tau_eq_h, UNIT_E6),
        "bound_low_tau_eq_h": to_scaled_int(bound_low_tau_eq_h, UNIT_E6),
    }
    validate_record(record)
    return record


def validate_record(record: object) -> None:
    """Raise ValueError unless `record` has exactly the schema's fields with the right types."""
    if not isinstance(record, dict):
        raise ValueError("a record must be a JSON object")
    if set(record) != set(FIELDS):
        missing = sorted(set(FIELDS) - set(record))
        extra = sorted(set(record) - set(FIELDS))
        raise ValueError(f"wrong fields (missing {missing}, unexpected {extra})")
    for name, kind in FIELDS.items():
        value = record[name]
        if value is None and kind.endswith("?"):
            continue
        if kind.startswith("int"):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{name} must be an integer (got {value!r})")
            _check_safe(value)
        elif not isinstance(value, str) or not value:
            raise ValueError(f"{name} must be a non-empty string (got {value!r})")
    if record["schema"] != SCHEMA_VERSION:
        raise ValueError(f"unsupported schema {record['schema']!r}")
    if record["seq"] < 0:
        raise ValueError("seq must not be negative")


def canonical_bytes(record: dict) -> bytes:
    """UTF-8 JSON, sorted keys, no whitespace; integers, strings and null only."""
    validate_record(record)
    return json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def parse_canonical(data: bytes) -> dict:
    """Read canonical bytes back. Raises ValueError for anything that is not a valid record.

    The bytes must be EXACTLY the canonical form (re-serialising gives the same bytes), so two
    different byte strings can never stand for the same record.
    """
    try:
        text = data.decode("utf-8")
        record = json.loads(text, parse_float=_reject_float, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, AttributeError) as exc:
        raise ValueError(f"not valid canonical JSON: {exc}") from exc
    validate_record(record)
    if canonical_bytes(record) != data:
        raise ValueError("bytes are valid JSON but not in canonical form")
    return record


def _reject_float(text: str):
    raise ValueError(f"floating-point number {text} is not allowed in a record")


def _reject_constant(text: str):
    raise ValueError(f"{text} is not allowed in a record")
