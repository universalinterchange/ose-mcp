mport random
import re
from typing import Any

DICE_RE = re.compile(r"^\s*(\d*)d(\d+)\s*([+-]\s*\d+)?\s*$", re.IGNORECASE)

def _roll_ndm(n: int, m: int) -> list[int]:
    return [random.randint(1, m) for _ in range(n)]

def register_mechanics(mcp):
    @mcp.tool()
    def roll(expr: str) -> dict[str, Any]:
        """Roll dice like '3d6+1'."""
        m = DICE_RE.match(expr)
        if not m:
            raise ValueError("Bad dice expression. Example: 3d6+1")

        n = int(m.group(1) or 1)
        sides = int(m.group(2))
        mod = int((m.group(3) or "0").replace(" ", ""))

        rolls = _roll_ndm(n, sides)
        total = sum(rolls) + mod
        return {"expr": expr, "rolls": rolls, "mod": mod, "total": total}

    @mcp.tool()
    def reaction_roll(mod: int = 0) -> dict[str, Any]:
        """OSE/OSR style 2d6 reaction roll with bands."""
        rolls = _roll_ndm(2, 6)
        total = sum(rolls) + mod
        if total <= 2:
            band = "hostile"
        elif total <= 5:
            band = "unfriendly"
        elif total <= 8:
            band = "uncertain"
        elif total <= 11:
            band = "positive"
        else:
            band = "enthusiastic"
        return {"rolls": rolls, "mod": mod, "total": total, "result": band}

    @mcp.tool()
    def morale_check(morale: int, mod: int = 0) -> dict[str, Any]:
        """2d6 morale check: pass if (2d6+mod) <= morale."""
        rolls = _roll_ndm(2, 6)
        total = sum(rolls) + mod
        return {"rolls": rolls, "mod": mod, "total": total, "morale": morale, "pass": total <= morale}

    @mcp.tool()
    def encounter_check(chance: int = 1, in_6: bool = True) -> dict[str, Any]:
        """Wandering encounter check (default: 1-in-6)."""
        die = 6 if in_6 else 8
        r = random.randint(1, die)
        hit = r <= chance
        return {"die": die, "roll": r, "chance": chance, "encounter": hit}

