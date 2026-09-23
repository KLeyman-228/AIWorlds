from django.test import SimpleTestCase

from generator.services.ai_client import _parse_json
from generator.services.instances import place_instances
from generator.services.scene_builder import _fallback_landforms, _infer_style, _prompt_uv
from generator.services.templates import infer_palette, instantiate_prop, instantiate_terrain_shader, resolve_template_id, tint_spec_from_prompt, wants_custom
from generator.services.terrain import apply_features, generate_color_map, generate_heightmap, mix_seed
from generator.services.validator import PlanValidationError, validate_and_place_props, validate_plan, _ground_geometry


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

    def test_expands_object_props(self):
        data = _parse_json(
            '{"n":"Meadow","d":"day","t":{"sc":40,"oc":3,"sd":7,"w":0.2,"g":[[0,[20,40,80]],[1,[80,140,60]]],"f":[{"k":"rv","pts":[[0,0.5],[1,0.5]],"w":0.05,"dp":0.4}]},"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[{"n":"oak","c":"veg","k":12,"d":"fr","t":"oak","p":{"size":1.2}}],"pp":["void main(){ gl_FragColor=vec4(1.0); }"]}'
        )
        self.assertEqual(data["prop_list"][0]["name"], "oak")
        self.assertEqual(data["prop_list"][0]["template"], "oak")
        self.assertEqual(data["prop_list"][0]["count"], 12)
        self.assertEqual(data["terrain"]["features"][0]["type"], "river")

    def test_expands_mountain_feature(self):
        data = _parse_json(
            '{"n":"Peak","d":"гора","t":{"sc":30,"oc":3,"sd":9,"w":0.1,"g":[[0,[80,90,40]],[1,[140,140,140]]],"f":[{"k":"mt","c":[0.5,0.5],"r":0.2,"h":0.9}]},"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[{"n":"pine","c":"veg","k":8,"d":"fr","t":"pine"}],"pp":["void main(){ gl_FragColor=vec4(1.0); }"]}'
        )
        feat = data["terrain"]["features"][0]
        self.assertEqual(feat["type"], "mountain")
        self.assertEqual(feat["center"], [0.5, 0.5])
        self.assertGreaterEqual(feat["height"], 0.8)

    def test_expands_style_and_canyon(self):
        data = _parse_json(
            '{"n":"Cut","d":"каньон","t":{"st":"canyon","sc":28,"oc":3,"sd":4,"amp":1.3,"w":0.1,"g":[[0,[80,70,40]],[1,[120,110,90]]],"f":[{"k":"cn","pts":[[0.1,0.5],[0.9,0.45]],"w":0.12,"dp":0.6}]},"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[{"n":"cactus","c":"veg","k":6,"d":"sc","t":"cactus"}],"pp":["void main(){ gl_FragColor=vec4(1.0); }"]}'
        )
        self.assertEqual(data["terrain"]["style"], "canyon")
        self.assertEqual(data["terrain"]["amplitude"], 1.3)
        self.assertEqual(data["terrain"]["features"][0]["type"], "canyon")

    def test_expands_custom_sky(self):
        data = _parse_json(
            '{"n":"Orbit","d":"космос","t":{"sc":40,"oc":3,"sd":2,"w":0.1,"g":[[0,[10,10,20]],[1,[40,40,60]]],"f":[]},"a":{"td":"night","sky":"x","fg":[10,12,30],"fd":0.01,"sk":[8,10,28],"su":[180,190,255],"am":[40,50,80]},"ss":["varying vec3 vDir;","void main(){ vec3 d=normalize(vDir); gl_FragColor=vec4(d*0.2,1.0); }"],"p":[{"n":"crystal","c":"mag","k":4,"d":"sc","t":"crystal"}],"pp":["void main(){ gl_FragColor=vec4(1.0); }"]}'
        )
        self.assertEqual(data["atmosphere"]["sky_mode"], "custom")
        self.assertIn("vDir", data["atmosphere"]["sky_shader"]["fragment"])

    def test_expands_terrain_shader_and_leaf(self):
        meta = _parse_json(
            '{"n":"Meadow","d":"day","t":{"sc":40,"oc":3,"sd":7,"w":0.2,"g":[[0,[20,40,80]],[1,[80,140,60]]],"f":[]},"ts":["void main(){ gl_FragColor=vec4(0.2,0.5,0.1,1.0); }"],"a":{"td":"day","fg":[170,200,230],"fd":0.01,"sk":[135,185,235],"su":[255,244,220],"am":[150,170,200]},"p":[["oak","veg",8,"fr"]],"pp":["void main(){ gl_FragColor=vec4(1.0); }"]}'
        )
        self.assertIn("gl_FragColor", meta["terrain"]["shader"]["fragment"])
        prop = _parse_json(
            '{"n":"oak","g":[["cyl",[0.1,0.2,1.2,6],[0,0.6,0]],["sph",[0.5,6,4],[0,1.5,0]]],"fs":["void main(){ gl_FragColor=vec4(0.3,0.2,0.1,1.0); }"],"ls":["void main(){ gl_FragColor=vec4(0.1,0.5,0.1,1.0); }"],"lv":["void main(){ gl_Position=vec4(0.0); }"],"i":[8,"fr",[0.8,1.2]]}'
        )
        self.assertIn("0.3,0.2,0.1", prop["shader"]["fragment"])
        self.assertIn("0.1,0.5,0.1", prop["shader"]["leaf_fragment"])
        self.assertIn("gl_Position", prop["shader"]["leaf_vertex"])

    def test_expands_compact_prop(self):
        data = _parse_json(
            '{"n":"oak","g":[["cyl",[0.1,0.2,1.2,6],[0,0.6,0]],["con",[0.7,1.0,6],[0,1.5,0]],["sph",[0.3,6,4],[0,1.2,0]]],"fs":["void main(){ gl_FragColor=vec4(0.2,0.5,0.1,1.0); }"],"u":{"uColorA":[0.2,0.5,0.1]},"i":[10,"fr",[0.8,1.2]]}'
        )
        self.assertEqual(data["geometry"]["primitives"][0]["type"], "cylinder")
        self.assertEqual(data["instances"]["distribution"], "forest")
        self.assertIn("gl_FragColor", data["shader"]["fragment"])

    def test_inserts_missing_commas_between_keys(self):
        data = _parse_json(
            '{"n":"boulder","g":[["sph",[0.5,6,4],[0,0.2,0]]]"fs":["void main(){ gl_FragColor=vec4(1.0); }"]"u":{"uC":[0.4,0.4,0.4]}"i":[8,"sc",[0.8,1.2]]}'
        )
        self.assertEqual(data["name"], "boulder")
        self.assertEqual(data["instances"]["count"], 8)
        self.assertIn("gl_FragColor", data["shader"]["fragment"])

    def test_does_not_break_valid_compact_json(self):
        data = _parse_json(
            '{"n":"boulder","g":[["sph",[0.5,6,4],[0,0.2,0]]],"fs":["void main(){ gl_FragColor=vec4(1.0); }"],"u":{"uC":[0.4,0.4,0.4]},"i":[8,"sc",[0.8,1.2]]}'
        )
        self.assertEqual(data["name"], "boulder")
        self.assertEqual(data["geometry"]["primitives"][0]["type"], "sphere")


class InstancePlacementTests(SimpleTestCase):
    def test_forest_places_requested_count(self):
        items = place_instances(
            {"count": 12, "distribution": "forest", "scale_range": [0.7, 1.3]},
            seed=7,
        )
        self.assertEqual(len(items), 12)
        self.assertEqual(len(items[0]["position"]), 3)

    def test_avoids_river_bed(self):
        hm = generate_heightmap(
            size=48,
            seed=3,
            octaves=3,
            features=[{"type": "river", "points": [[0.0, 0.5], [1.0, 0.5]], "width": 0.08, "depth": 0.6}],
        )
        features = [{"type": "river", "points": [[0.0, 0.5], [1.0, 0.5]], "width": 0.08, "depth": 0.6}]
        items = place_instances(
            {"count": 10, "distribution": "scattered"},
            seed=4,
            heightmap=hm,
            features=features,
            water_level=0.08,
        )
        self.assertGreaterEqual(len(items), 6)
        for inst in items:
            self.assertGreater(abs(inst["position"][2]), 1.2)


class TemplateTests(SimpleTestCase):
    def test_resolves_oak_from_name(self):
        self.assertEqual(resolve_template_id("old_oak"), "oak")
        self.assertEqual(resolve_template_id("blue_oak", "blue_oak"), "oak")
        self.assertFalse(wants_custom({"name": "blue_oak", "template": "blue_oak"}))
        tinted = tint_spec_from_prompt({"name": "oak", "template": "oak"}, "синие деревья")
        self.assertGreater(tinted["leaf"][2], 0.8)
        snow = tint_spec_from_prompt({"name": "oak", "template": "oak"}, "снежный лес")
        self.assertGreater(snow["leaf"][0], 0.7)
        self.assertGreater(snow["leaf"][2], 0.7)
        self.assertFalse(wants_custom({"name": "oak", "template": "oak"}))
        self.assertTrue(wants_custom({"name": "crystal", "template": "x"}))
        self.assertTrue(wants_custom({"name": "cottage"}))
        self.assertIsNone(resolve_template_id("house1"))

    def test_blue_leaves_on_oak_template(self):
        prop = instantiate_prop({
            "name": "blue_oak",
            "template": "oak",
            "count": 6,
            "distribution": "forest",
            "leaf": [0.2, 0.3, 0.9],
            "bark": [0.3, 0.15, 0.08],
            "size": 1.2,
        })
        self.assertEqual(prop["template"], "oak")
        self.assertGreater(len(prop["geometry"]["primitives"]), 2)
        self.assertEqual(prop["shader"]["uniforms"]["uLeaf"]["value"][2], 0.9)
        self.assertIn("uBark", prop["shader"]["uniforms"])
        self.assertIn("shadeLit", prop["shader"]["fragment"])
        self.assertIn("fbm", prop["shader"]["leaf_fragment"])

    def test_crystal_has_emission(self):
        prop = instantiate_prop({"name": "glow_crystal", "template": "crystal", "em": 1.2, "count": 4})
        self.assertEqual(prop["template"], "crystal")
        self.assertGreater(prop["shader"]["uniforms"]["uEm"]["value"], 0.5)
        self.assertIn("uEm", prop["shader"]["fragment"])
        em_pos = prop["shader"]["fragment"].rfind("uEm")
        shade_pos = prop["shader"]["fragment"].rfind("shadeLit")
        self.assertGreater(em_pos, shade_pos)

    def test_new_templates_exist(self):
        for tid in ("mushroom", "ruin", "hay", "flower", "pine", "fir"):
            prop = instantiate_prop({"name": tid, "template": tid, "count": 3})
            self.assertGreaterEqual(len(prop["geometry"]["primitives"]), 3)
            self.assertEqual(prop["shader"]["uniforms"]["uEm"]["value"], 0.0)
        self.assertEqual(resolve_template_id("ёлка"), "pine")
        self.assertEqual(resolve_template_id("ель"), "fir")
        pine = instantiate_prop({"name": "pine", "template": "pine", "count": 4})
        types = [p["type"] for p in pine["geometry"]["primitives"]]
        self.assertIn("cone", types)

    def test_terrain_material_params(self):
        shader = instantiate_terrain_shader({
            "grass": [0.1, 0.5, 0.2],
            "dirt": [0.4, 0.25, 0.1],
            "rock": [0.5, 0.48, 0.44],
            "snow": [0.9, 0.92, 0.95],
        })
        u = shader["uniforms"]
        self.assertEqual(u["uGrass"]["value"][1], 0.5)
        self.assertEqual(u["uDirt"]["value"][0], 0.4)
        self.assertEqual(u["uSnow"]["value"][2], 0.95)
        self.assertIn("texture2D(uMap", shader["fragment"])
        self.assertIn("noise", shader["fragment"])
        self.assertNotIn("precision mediump float", shader["fragment"])
        self.assertNotIn("precision mediump float", shader["vertex"])

    def test_snow_palette_is_white(self):
        pal = infer_palette("снежный лес с елками")
        self.assertEqual(pal["biome"], "snow")
        self.assertGreater(pal["terrain"]["grass"][2], pal["terrain"]["grass"][1] - 0.05)
        shader = instantiate_terrain_shader(pal["terrain"])
        self.assertGreater(shader["uniforms"]["uGrass"]["value"][0], 0.7)

    def test_giant_mushroom_size(self):
        prop = instantiate_prop({
            "name": "giant_fly_agaric",
            "template": "mushroom",
            "size": 4.5,
            "count": 5,
        })
        lo, hi = prop["instances"]["scale_range"]
        self.assertGreater(lo, 3.5)
        self.assertGreater(hi, 4.5)


class TerrainFeatureTests(SimpleTestCase):
    def test_river_lowers_center_of_map(self):
        base = generate_heightmap(size=32, scale=20, octaves=2, seed=3, features=[])
        carved = apply_features(
            base.copy(),
            [{"type": "river", "points": [[0.0, 0.5], [1.0, 0.5]], "width": 0.08, "depth": 0.6}],
        )
        self.assertLess(carved[16, 16], carved[4, 16])

    def test_heightmap_is_smooth(self):
        hm = generate_heightmap(size=48, seed=5, octaves=4, features=[])
        diffs = abs(hm[1:] - hm[:-1])
        self.assertLess(float(diffs.max()), 0.28)

    def test_mountain_raises_center(self):
        hm = generate_heightmap(
            size=48,
            scale=40,
            octaves=3,
            seed=11,
            features=[{"type": "mountain", "center": [0.5, 0.5], "radius": 0.22, "height": 0.9}],
        )
        self.assertGreater(float(hm[24, 24]), float(hm[6, 6]) + 0.18)

    def test_prompt_seed_changes_relief(self):
        a = generate_heightmap(size=32, seed=mix_seed("луг", 1), octaves=3, features=[])
        b = generate_heightmap(size=32, seed=mix_seed("пустыня", 1), octaves=3, features=[])
        self.assertGreater(float(abs(a - b).mean()), 0.02)

    def test_styles_look_different(self):
        plains = generate_heightmap(size=32, seed=8, octaves=3, style="plains", features=[])
        peaks = generate_heightmap(size=32, seed=8, octaves=3, style="mountains", features=[])
        island = generate_heightmap(size=32, seed=8, octaves=3, style="island", features=[])
        self.assertGreater(float(peaks.max() - peaks.min()), float(plains.max() - plains.min()))
        self.assertGreater(float(island[16, 16]), float(island[2, 2]))

    def test_prompt_places_mountain_left(self):
        extra = _fallback_landforms("гора слева", [], 1)
        self.assertEqual(extra[0]["type"], "mountain")
        self.assertLess(extra[0]["center"][0], 0.35)
        self.assertEqual(_infer_style("пустыня с дюнами"), "dunes")
        self.assertEqual(_prompt_uv("озеро на севере")[1], 0.82)

    def test_colormap_is_banded(self):
        hm = generate_heightmap(size=24, seed=2, octaves=3, features=[])
        cm = generate_color_map(
            hm,
            [
                {"height": 0.0, "color": [20, 80, 180]},
                {"height": 0.5, "color": [40, 160, 50]},
                {"height": 1.0, "color": [180, 170, 150]},
            ],
        )
        unique = len({tuple(px) for row in cm for px in row})
        self.assertLessEqual(unique, 3)


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
        self.assertEqual(plan["atmosphere"]["sky_mode"], "default")
        self.assertEqual(len(plan["terrain"]["features"]), 1)

    def test_keeps_custom_sky_shader(self):
        plan = validate_plan(
            {
                "world_name": "Orbit",
                "terrain": {
                    "scale": 40,
                    "octaves": 3,
                    "seed": 1,
                    "color_gradient": [
                        {"height": 0, "color": [10, 20, 30]},
                        {"height": 1, "color": [40, 50, 60]},
                    ],
                    "features": [],
                },
                "atmosphere": {
                    "fog_color": [10, 12, 30],
                    "fog_density": 0.01,
                    "sky_color": [8, 10, 40],
                    "sun_color": [180, 190, 255],
                    "ambient_color": [40, 50, 80],
                    "time_of_day": "night",
                    "sky_mode": "custom",
                    "sky_shader": {
                        "fragment": "varying vec3 vDir; void main(){ gl_FragColor=vec4(0.05,0.07,0.16,1.0); }"
                    },
                },
            }
        )
        self.assertEqual(plan["atmosphere"]["sky_mode"], "custom")
        self.assertIn("vDir", plan["atmosphere"]["sky_shader"]["fragment"])

    def test_gradient_from_material_when_missing(self):
        plan = validate_plan(
            {
                "world_name": "Dunes",
                "terrain": {
                    "scale": 40,
                    "octaves": 3,
                    "seed": 1,
                    "material": {
                        "grass": [0.72, 0.55, 0.22],
                        "dirt": [0.55, 0.38, 0.16],
                        "rock": [0.45, 0.40, 0.32],
                    },
                },
                "atmosphere": {
                    "fog_color": [200, 180, 140],
                    "fog_density": 0.01,
                    "sky_color": [135, 185, 235],
                    "sun_color": [255, 240, 200],
                    "ambient_color": [160, 140, 110],
                    "time_of_day": "day",
                },
            }
        )
        self.assertGreaterEqual(len(plan["terrain"]["color_gradient"]), 4)
        self.assertEqual(plan["terrain"]["color_gradient"][0]["color"], [140, 97, 41])

    def test_nested_feature_center(self):
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
                        {"type": "lake", "center": [[0.4], [0.6]], "radius": [0.1], "depth": ["0.3"]}
                    ],
                },
                "atmosphere": {
                    "fog_color": [170, 200, 230],
                    "fog_density": 0.01,
                    "sky_color": [135, 185, 235],
                    "sun_color": [255, 240, 200],
                    "ambient_color": [120, 140, 160],
                    "time_of_day": "day",
                },
                "post_process": {
                    "shader": {"fragment": "void main(){ gl_FragColor = vec4(1.0); }"}
                },
            }
        )
        self.assertEqual(plan["terrain"]["features"][0]["center"], [0.4, 0.6])
        self.assertAlmostEqual(plan["terrain"]["features"][0]["radius"], 0.1)

    def test_grounds_floating_cactus(self):
        geo = _ground_geometry(
            {
                "primitives": [
                    {
                        "type": "cylinder",
                        "params": {"rTop": 0.12, "rBottom": 0.16, "height": 1.4, "segments": 6},
                        "position": [0.0, 1.2, 0.0],
                    },
                    {
                        "type": "sphere",
                        "params": {"radius": 0.18},
                        "position": [0.0, 2.0, 0.0],
                    },
                ]
            }
        )
        bottoms = []
        for prim in geo["primitives"]:
            half = 0.7 if prim["type"] == "cylinder" else 0.18
            bottoms.append(prim["position"][1] - half)
        self.assertAlmostEqual(min(bottoms), -0.03, places=2)

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
