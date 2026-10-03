"""Render each world's field equations directly from its published genome.

Expressions also have a plain Python representation for numerical verification.
Only trusted, checked-in genome snapshots are used by the documentation build.
"""

import re
from decimal import Decimal
from html import escape


def number(value):
    """Preserve every decimal digit in the genome, without redundant zeros."""
    text = format(value, "f") if isinstance(value, Decimal) else str(value)
    return text.rstrip("0").rstrip(".") if "." in text else text


def linear_sum(terms):
    result = ""
    for coefficient, variable in terms:
        if not coefficient:
            continue
        magnitude = abs(coefficient)
        body = variable if variable and magnitude == 1 else number(magnitude)
        if variable and magnitude != 1:
            body += f" * {variable}"
        sign = " - " if coefficient < 0 else " + "
        result += (sign if result else "-" if coefficient < 0 else "") + body
    return result or "0"


def equations(genome):
    """Return background, nonlinear-drive, and time-derivative expressions."""
    background = [(f"z{i}", linear_sum([(1, f"u{i}"), (-act["u0"], "")])) for i, act in enumerate(genome["acts"])]
    drives = []
    for c, channel in enumerate(genome["chans"]):
        if channel["g"] == "tanh":
            argument = linear_sum([(1, "z"), (-channel["thr"], "")])
            drives.append((f"h{c}(z)", f"tanh(max({argument}, 0) / {number(channel['sc'])})"))
        elif channel["g"] != "id":
            raise ValueError(f"Unsupported channel drive: {channel['g']}")
    activators = []
    for i, act in enumerate(genome["acts"]):
        terms = [(act["Du"], f"lap_u{i}"), (act["lam"], f"u{i}"), (-1, f"u{i} ** 3"), (act["k1"], "")]
        terms += [(-coefficient, f"x{c}") for c, coefficient in enumerate(genome["K"][i])]
        terms += [
            (-coefficient, f"x{c} * x{d}") for target, c, d, coefficient in genome.get("bilin", []) if target == i
        ]
        activators.append((f"dt_u{i}", linear_sum(terms)))
    channels = []
    for c, channel in enumerate(genome["chans"]):
        terms = [
            (coefficient, f"z{a}" if channel["g"] == "id" else f"h{c}(z{a})")
            for a, coefficient in enumerate(genome["W"][c])
        ]
        drive = linear_sum(terms + [(-1, f"x{c}")])
        relaxation = f"({drive}) / {number(channel['tau'])}"
        channels.append((f"dt_x{c}", linear_sum([(channel["D"], f"lap_x{c}"), (1, relaxation)])))
    return {"background": background, "drives": drives, "activators": activators, "channels": channels}


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
    groups = equations(genome)
    rows = []
    for name, label in (
        ("background", "Deviations from the uniform background"),
        ("drives", "Thresholded field response"),
        ("activators", "Fields u"),
        ("channels", "Fields x"),
    ):
        if not groups[name]:
            continue
        rows.append(f'<h4>{label}</h4><div class="equation-lines">')
        for lhs, rhs in groups[name]:
            rows.append(f'<div class="equation">{math_html(lhs)} = {math_html(rhs)}</div>')
        rows.append("</div>")
    return (
        f'<details class="world-equations" id="{escape(key)}-equations">'
        f"<summary>View the full {escape(source['label'])} field equations</summary>"
        "<p>Coefficients are shown at their full stored precision. Indices start at zero, as in the genome. "
        'These are the deterministic field equations; the <a href="#numerics">numerical profile</a> '
        "specifies discretization and noise, and experiments may add source forcing.</p>"
        + "".join(rows)
        + f'<p><a href="{escape(source["file"])}" download>Download the genome JSON</a> · '
        f'<a href="{escape(source["published_source"])}">Published source</a></p></details>'
    )
