from django.test import SimpleTestCase

from generator.services.ai_client import _parse_json
from generator.services.instances import place_instances
from generator.services.terrain import apply_features, generate_heightmap
from generator.services.validator import PlanValidationError, validate_and_place_props, validate_plan


class JsonParseTests(SimpleTestCase):
    def test_repairs_raw_newlines_inside_glsl_string(self):
        raw = (
            '{\n'
            '  "name": "stone_donjon",\n'
            '  "shader": {\n'
            '    "fragment": "void main() {\n'
            '  gl_FragColor = vec4(1.0);\n'
            '}"\n'
            '  }\n'
            '}'
        )
        data = _parse_json(raw)
        self.assertIn("gl_FragColor", data["shader"]["fragment"])

    def test_joins_fragment_lines(self):
        data = _parse_json(
            '{"shader": {"fragment_lines": ["void main() {", "  gl_FragColor = vec4(1.0);", "}"]}}'
        )
        self.assertIn("gl_FragColor", data["shader"]["fragment"])


class InstancePlacementTests(SimpleTestCase):
    def test_forest_places_requested_count(self):
        items = place_instances(
            {"count": 12, "distribution": "forest", "scale_range": [0.7, 1.3]},
            seed=7,
        )
        self.assertEqual(len(items), 12)
        self.assertEqual(len(items[0]["position"]), 3)


class TerrainFeatureTests(SimpleTestCase):
    def test_river_lowers_center_of_map(self):
        base = generate_heightmap(size=32, scale=20, octaves=2, seed=3, features=[])
        carved = apply_features(
            base.copy(),
            [{"type": "river", "points": [[0.0, 0.5], [1.0, 0.5]], "width": 0.08, "depth": 0.6}],
        )
        self.assertLess(carved[16, 16], carved[4, 16])


class ValidatorTests(SimpleTestCase):
    def test_rejects_empty_props(self):
        with self.assertRaises(PlanValidationError):
            validate_and_place_props({}, seed=1)

    def test_forces_day_sky_blue(self):
        plan = validate_plan(
            {
                "world_name": "X",
                "terrain": {
                    "scale": 40,
                    "octaves": 3,
                    "seed": 1,
                    "color_gradient": [
                        {"height": 0, "color": [10, 20, 30]},
                        {"height": 1, "color": [40, 50, 60]},
                    ],
                    "features": [
                        {"type": "lake", "center": [0.4, 0.4], "radius": 0.1, "depth": 0.3}
                    ],
                },
                "atmosphere": {
                    "fog_color": [200, 80, 40],
                    "fog_density": 0.08,
                    "sky_color": [220, 60, 40],
                    "sun_color": [255, 240, 200],
                    "ambient_color": [120, 140, 160],
                    "time_of_day": "day",
                },
                "post_process": {
                    "shader": {"fragment": "void main(){ gl_FragColor = vec4(1.0); }"}
                },
            }
        )
        self.assertGreater(plan["atmosphere"]["sky_color"][2], plan["atmosphere"]["sky_color"][0])
        self.assertEqual(len(plan["terrain"]["features"]), 1)

    def test_expands_instance_rules(self):
        props = validate_and_place_props(
            {
                "gold_mine": {
                    "geometry": {
                        "primitives": [
                            {"type": "box", "params": {"width": 1, "height": 1, "depth": 1}},
                        ]
                    },
                    "shader": {
                        "fragment": "void main(){ gl_FragColor = vec4(1.0, 0.8, 0.2, 1.0); }"
                    },
                    "instances": {"count": 5, "distribution": "cluster"},
                }
            },
            seed=1,
        )
        self.assertEqual(len(props["gold_mine"]["instances"]), 5)
        self.assertIn("uTime", props["gold_mine"]["shader"]["uniforms"])
