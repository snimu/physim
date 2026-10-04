"""Check that the displayed laws agree with all three published world genomes."""

import json
import math
import random
import re
import sys
import unittest
from decimal import Decimal
from html import unescape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from world_equations import equations, math_html


def rendered_expression(expression):
    """Recover arithmetic from the visible HTML, including superscript powers."""
    html = math_html(expression).replace("<sup>3</sup>", "** 3")
    return unescape(re.sub(r"<[^>]+>", "", html)).replace("∇²", "lap_").replace("·", "*").replace("−", "-")


class WorldEquationTests(unittest.TestCase):
    def test_displayed_derivatives_match_genome_dynamics(self):
        rng = random.Random(718)
        sources = json.loads((ROOT / "docs_source/data/equation-sources.json").read_text())
        for key, source in sources.items():
            text = (ROOT / "docs_source" / source["file"]).read_text()
            genome = json.loads(text)
            displayed = equations(json.loads(text, parse_float=Decimal))
            for _ in range(20):
                values = {"tanh": math.tanh, "max": max}
                for symbol, fields in (("u", genome["acts"]), ("x", genome["chans"])):
                    for i in range(len(fields)):
                        values[f"{symbol}{i}"] = rng.uniform(-2, 2)
                        values[f"lap_{symbol}{i}"] = rng.uniform(-0.8, 0.8)
                for i, (lhs, expression) in enumerate(displayed["activators"]):
                    act = genome["acts"][i]
                    u = values[f"u{i}"]
                    expected = act["Du"] * values[f"lap_u{i}"] + act["lam"] * u - u**3 + act["k1"]
                    expected -= sum(k * values[f"x{c}"] for c, k in enumerate(genome["K"][i]))
                    expected -= sum(
                        coefficient * values[f"x{c}"] * values[f"x{d}"]
                        for target, c, d, coefficient in genome["bilin"]
                        if target == i
                    )
                    with self.subTest(world=key, equation=lhs):
                        actual = eval(rendered_expression(expression), {"__builtins__": {}}, values)
                        self.assertAlmostEqual(actual, expected, places=11)
                for c, (lhs, expression) in enumerate(displayed["channels"]):
                    channel = genome["chans"][c]
                    drive = 0
                    for a, weight in enumerate(genome["W"][c]):
                        z = values[f"u{a}"] - genome["acts"][a]["u0"]
                        if channel["g"] == "tanh":
                            z = math.tanh(max(z - channel["thr"], 0) / channel["sc"])
                        drive += weight * z
                    expected = channel["D"] * values[f"lap_x{c}"] + (drive - values[f"x{c}"]) / channel["tau"]
                    with self.subTest(world=key, equation=lhs):
                        actual = eval(rendered_expression(expression), {"__builtins__": {}}, values)
                        self.assertAlmostEqual(actual, expected, places=11)

    def test_exact_coefficients_and_zero_diffusion_survive_rendering(self):
        path = ROOT / "docs_source/data/genomes/bf.json"
        laws = equations(json.loads(path.read_text(), parse_float=Decimal))
        self.assertIn("0.7035399190279497", math_html(laws["channels"][0][1]))
        # Background 0.7035399190279497 and threshold 0.9529890666304698, combined exactly.
        self.assertIn("u0 - 0.2494491476025201", laws["channels"][2][1])
        self.assertNotIn("z", "".join(rhs for _, rhs in laws["activators"] + laws["channels"]))
        self.assertNotIn("lap_x2", laws["channels"][2][1])
        shown = equations(json.loads(path.read_text(), parse_float=Decimal), digits=4)
        self.assertIn("u0 - 0.2494", shown["channels"][2][1])
        self.assertIn("0.7018 * lap_x0", shown["channels"][0][1])
        self.assertNotIn("0.2494491476025201", shown["channels"][2][1])
        self.assertTrue(laws["channels"][2][1].endswith("/ 200"))
        self.assertIn("- x2 * x1", laws["activators"][0][1])


if __name__ == "__main__":
    unittest.main()
