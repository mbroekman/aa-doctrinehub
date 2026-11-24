"""Parse and write fittings in EFT format.

EFT has no slot markers, only blocks separated by blank lines, in the order
low, medium, high, rigs, subsystems. Blocks whose lines carry a quantity
(``Hobgoblin II x5``) are drones, fighters or cargo. Without the SDE the parser
places blocks by position; type resolution by name happens in a later step.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field

SLOT_BLOCKS: tuple[str, ...] = ("LoSlot", "MedSlot", "HiSlot", "RigSlot", "SubSystemSlot", "ServiceSlot")
BAY_BLOCKS: tuple[str, ...] = ("DroneBay", "Cargo")
EXPORT_SLOT_ORDER: tuple[str, ...] = SLOT_BLOCKS
EXPORT_BAY_ORDER: tuple[str, ...] = ("FighterBay", "DroneBay", "Cargo")

_HEADER_RE = re.compile(r"^\[(?P<ship>[^,\]]+),\s*(?P<name>[^\]]*)\]$")
_QUANTITY_RE = re.compile(r"^(?P<name>.+?)\s+x(?P<qty>\d+)$")
_EMPTY_RE = re.compile(r"^\[Empty .+ slot\]$", re.IGNORECASE)
_OFFLINE_SUFFIX = "/offline"


class EftParseError(ValueError):
    """The text is not a valid EFT fitting."""


@dataclass(frozen=True)
class ParsedItem:
    """One item of a parsed fitting."""

    flag: str
    type_name: str
    quantity: int = 1
    charge_name: str = ""
    is_offline: bool = False


@dataclass
class ParsedFitting:
    """A fitting parsed from EFT."""

    ship_type_name: str
    name: str
    items: list[ParsedItem] = field(default_factory=list)


def _split_blocks(lines: Iterable[str]) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            if current:
                blocks.append(current)
                current = []
            continue
        current.append(line)
    if current:
        blocks.append(current)
    return blocks


def _parse_module(line: str, flag: str) -> ParsedItem | None:
    if _EMPTY_RE.match(line):
        return None
    is_offline = line.endswith(_OFFLINE_SUFFIX)
    if is_offline:
        line = line[: -len(_OFFLINE_SUFFIX)].rstrip()
    module, _sep, charge = line.partition(",")
    return ParsedItem(flag=flag, type_name=module.strip(), charge_name=charge.strip(), is_offline=is_offline)


def _parse_bay_line(line: str, flag: str) -> ParsedItem:
    match = _QUANTITY_RE.match(line)
    if not match:
        return ParsedItem(flag=flag, type_name=line)
    return ParsedItem(flag=flag, type_name=match["name"].strip(), quantity=int(match["qty"]))


def _is_bay_block(block: list[str]) -> bool:
    return all(_QUANTITY_RE.match(line) for line in block)


def parse_eft(text: str) -> ParsedFitting:
    """Parse an EFT fitting into ship, name and items.

    Raises:
        EftParseError: when the header line is missing or malformed.
    """
    lines = text.strip().splitlines()
    if not lines:
        raise EftParseError("Empty fitting")
    header = _HEADER_RE.match(lines[0].strip())
    if not header:
        raise EftParseError("The first line must look like [Ship, Fitting name]")

    fitting = ParsedFitting(ship_type_name=header["ship"].strip(), name=header["name"].strip())
    slot_index = 0
    bay_index = 0
    for block in _split_blocks(lines[1:]):
        if _is_bay_block(block) or slot_index >= len(SLOT_BLOCKS):
            flag = BAY_BLOCKS[min(bay_index, len(BAY_BLOCKS) - 1)]
            bay_index += 1
            fitting.items.extend(_parse_bay_line(line, flag) for line in block)
            continue
        prefix = SLOT_BLOCKS[slot_index]
        slot_index += 1
        for position, line in enumerate(block):
            item = _parse_module(line, f"{prefix}{position}")
            if item:
                fitting.items.append(item)
    return fitting


@dataclass(frozen=True)
class ExportItem:
    """Minimal item shape needed to write EFT and multibuy text."""

    flag: str
    type_name: str
    quantity: int = 1
    charge_name: str = ""
    is_offline: bool = False


def _slot_prefix(flag: str) -> str:
    return flag.rstrip("0123456789")


def _slot_number(flag: str) -> int:
    digits = flag[len(_slot_prefix(flag)) :]
    return int(digits) if digits else 0


def to_eft(ship_type_name: str, name: str, items: Iterable[ExportItem]) -> str:
    """Write a fitting as EFT text."""
    by_prefix: dict[str, list[ExportItem]] = {}
    for item in items:
        by_prefix.setdefault(_slot_prefix(item.flag), []).append(item)

    sections: list[str] = []
    for prefix in EXPORT_SLOT_ORDER:
        modules = sorted(by_prefix.get(prefix, []), key=lambda i: _slot_number(i.flag))
        if not modules:
            continue
        lines = []
        for module in modules:
            line = module.type_name
            if module.charge_name:
                line += f", {module.charge_name}"
            if module.is_offline:
                line += f" {_OFFLINE_SUFFIX}"
            lines.append(line)
        sections.append("\n".join(lines))
    for prefix in EXPORT_BAY_ORDER:
        bay = by_prefix.get(prefix, [])
        if bay:
            sections.append("\n".join(f"{i.type_name} x{i.quantity}" for i in bay))

    body = "\n\n".join(sections)
    return f"[{ship_type_name}, {name}]\n\n{body}\n" if body else f"[{ship_type_name}, {name}]\n"


def to_multibuy(ship_type_name: str, items: Iterable[ExportItem], amount: int = 1) -> str:
    """Write a multibuy list (ship plus every item and charge) for ``amount`` fits."""
    counts: Counter[str] = Counter()
    for item in items:
        counts[item.type_name] += item.quantity * amount
    lines = [f"{ship_type_name} x{amount}"]
    lines.extend(f"{type_name} x{count}" for type_name, count in counts.items())
    return "\n".join(lines)
