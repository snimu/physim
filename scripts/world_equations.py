"""Render each world's field equations directly from its published definition.

Equations are written in the fields alone: each field's offset from its uniform
background and each thresholded response are expanded in place, with constants
combined exactly in decimal. Expressions also have a plain Python representation
for numerical verification. Only trusted, checked-in snapshots are used by the
documentation build.
"""

import re
from decimal import ROUND_HALF_EVEN, Decimal
from html import escape

DISPLAY_DIGITS = 4  # significant figures on the page; the downloadable JSON keeps every digit


def number(value, digits=None):
    """Format a coefficient with every stored digit, or rounded to `digits` significant figures."""
    if digits is not None:
        value = value if isinstance(value, Decimal) else Decimal(str(value))
        if value:
            value = value.quantize(Decimal(1).scaleb(value.adjusted() - digits + 1), rounding=ROUND_HALF_EVEN)
    text = format(value, "f") if isinstance(value, Decimal) else str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def linear_sum(terms, digits=None):
    result = ""
    for coefficient, variable in terms:
        if not coefficient:
            continue
        magnitude = abs(coefficient)
        body = variable if variable and magnitude == 1 else number(magnitude, digits)
        if variable and magnitude != 1:
            body += f" * {variable}"
        sign = " - " if coefficient < 0 else " + "
        result += (sign if result else "-" if coefficient < 0 else "") + body
    return result or "0"


def equations(genome, digits=None):
    """Return the time derivative of every field, written in terms of the fields only.

    Constants are combined exactly; `digits` rounds the displayed coefficients.
    """
    for channel in genome["chans"]:
        if channel["g"] not in ("id", "tanh"):
            raise ValueError(f"Unsupported channel drive: {channel['g']}")
    activators = []
    for i, act in enumerate(genome["acts"]):
        terms = [(act["Du"], f"lap_u{i}"), (act["lam"], f"u{i}"), (-1, f"u{i} ** 3"), (act["k1"], "")]
        terms += [(-coefficient, f"x{c}") for c, coefficient in enumerate(genome["K"][i])]
        terms += [
            (-coefficient, f"x{c} * x{d}") for target, c, d, coefficient in genome.get("bilin", []) if target == i
        ]
        activators.append((f"dt_u{i}", linear_sum(terms, digits)))
    channels = []
    for c, channel in enumerate(genome["chans"]):
        weights = [(a, w) for a, w in enumerate(genome["W"][c]) if w]
        if channel["g"] == "id":
            # Linear drive by each field's offset from its background, constants combined.
            constant = -sum((w * genome["acts"][a]["u0"] for a, w in weights), type(channel["tau"])(0))
            terms = [(w, f"u{a}") for a, w in weights] + [(constant, "")]
        else:
            sc = number(channel["sc"], digits)
            terms = []
            for a, w in weights:
                offset = linear_sum([(1, f"u{a}"), (-(genome["acts"][a]["u0"] + channel["thr"]), "")], digits)
                terms.append((w, f"tanh(max({offset}, 0) / {sc})"))
        drive = linear_sum(terms + [(-1, f"x{c}")], digits)
        relaxation = f"({drive}) / {number(channel['tau'], digits)}"
        channels.append((f"dt_x{c}", linear_sum([(channel["D"], f"lap_x{c}"), (1, relaxation)], digits)))
    return {"activators": activators, "channels": channels}


def math_html(expression):
    """Typeset the verified expression, retaining its grouping and digits."""
    token_pattern = r"((?:lap_|dt_)?[uxzh]\d+|\*\* 3|\*|\b(?:tanh|max|z)\b)"
    parts = []
    for token in re.split(token_pattern, expression):
        match = re.fullmatch(r"(lap_|dt_)?([uxzh])(\d+)", token)
        if match:
            prefix, symbol, index = match.groups()
            operator = "∇²" if prefix == "lap_" else "∂<sub>t</sub>" if prefix == "dt_" else ""
            parts.append(f"{operator}<var>{symbol}</var><sub>{index}</sub>")
        elif token == "** 3":
            parts.append("<sup>3</sup>")
        elif token == "*":
            parts.append("·")
        elif token == "z":
            parts.append("<var>z</var>")
        else:
            parts.append(escape(token).replace("-", "−"))
    return "".join(parts)


def render_equations(key, source, genome):
    groups = equations(genome, DISPLAY_DIGITS)
    rows = "".join(
        f'<div class="equation">{math_html(lhs)} = {math_html(rhs)}</div>'
        for lhs, rhs in groups["activators"] + groups["channels"]
    )
    return (
        f'<details class="world-equations" id="{escape(key)}-equations">'
        f"<summary>View the full {escape(source['label'])} field equations</summary>"
        f'<div class="equation-lines">{rows}</div>'
        f'<p><a href="{escape(source["file"])}" download>Download the world JSON</a> · '
        f'<a href="{escape(source["published_source"])}">Published source</a></p></details>'
    )
