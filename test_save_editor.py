import unittest
import tkinter as tk
import os
from types import SimpleNamespace

from rubymarshal.classes import RubyObject
from rubymarshal.reader import loads
from rubymarshal.writer import writes

from save_editor import (
    Editor,
    COMPUTED_FORM_SPECIES,
    FORM_OVERRIDE_DATA,
    FORM_DATA,
    HEART_GAUGE_SIZE,
    MOVE_DATA,
    NATURES,
    Ruby18Writer,
    SHADOW_MOVE_IDS,
    SHADOW_RUSH_ID,
    STATS,
    _display_stats_to_game,
    _nature_stat_multiplier,
    _scale_ev_preset,
    _valid_ev_edit,
    bag_add_button_text,
    _game_stats_to_display,
    _sanitize_evs,
    split_streams,
    ability_choices_for_species,
    ability_slot_from_value,
    apply_pokemon_form,
    apply_pokemon_identity,
    gender_choices_for_species,
    heart_stage,
    item_picker_id,
    item_source_id,
    make_shadow,
    marshal_stream_end,
    move_party_pokemon_to_box,
    pokemon_gender,
    pokemon_is_shadow,
    pokemon_is_shiny,
    pokemon_form,
    pokemon_base_stats,
    pokemon_learnset,
    pokemon_move_ids,
    pokemon_nature,
    purify,
    recommended_creation_move_ids,
    resource_path,
    set_heart_gauge,
    set_shadow_move_sets,
    seasonal_pokemon_form,
    shadow_move_sets,
)


class FakeVar:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class PokemonIdentityTests(unittest.TestCase):
    def test_clearing_editor_vars_tolerates_trace_cache_updates(self):
        class TracedStringVar(tk.StringVar):
            def __init__(self, value, on_set=None):
                self.value = value
                self.on_set = on_set

            def set(self, value):
                self.value = value
                if self.on_set:
                    self.on_set()

            def get(self):
                return self.value

            def __del__(self):
                pass

        variables = {
            "nature_idx": TracedStringVar("Modest"),
        }
        variables["species_id"] = TracedStringVar(
            "3", lambda: variables.update({"_ability_choices": {"Overgrow": 0}})
        )

        Editor._clear_pokemon_editor_vars(None, variables)

        self.assertEqual(variables["species_id"].get(), "")
        self.assertIn("_ability_choices", variables)

    def test_ability_choices_use_names_and_include_hidden_ability(self):
        self.assertEqual(
            ability_choices_for_species(3),
            [(0, "Overgrow"), (2, "Chlorophyll (Hidden)")],
        )
        self.assertEqual(ability_slot_from_value(3, "Chlorophyll (Hidden)"), 2)

    def test_duplicate_normal_abilities_are_collapsed(self):
        self.assertEqual(
            ability_choices_for_species(758),
            [(0, "White Smoke"), (2, "Flash Fire (Hidden)")],
        )

    def test_nature_override_takes_precedence_over_pid(self):
        attributes = {"@personalID": 2, "@natureflag": NATURES.index("Impish")}

        self.assertEqual(pokemon_nature(attributes), NATURES.index("Impish"))

    def test_editing_identity_preserves_pid_ivs_and_evs(self):
        attributes = {
            "@species": 3,  # Venusaur: male or female
            "@personalID": 0x12345678,
            "@iv": [31, 30, 29, 28, 27, 26],
            "@ev": [252, 0, 0, 252, 4, 0],
        }
        original_pid = attributes["@personalID"]

        apply_pokemon_identity(
            attributes,
            NATURES.index("Modest"),
            shiny=False,
            ability_slot=1,
            gender="Female",
        )

        self.assertEqual(attributes["@personalID"], original_pid)
        self.assertEqual(attributes["@natureflag"], NATURES.index("Modest"))
        self.assertEqual(attributes["@genderflag"], 1)
        self.assertEqual(attributes["@abilityflag"], 1)
        self.assertIs(attributes["@shinyflag"], False)
        self.assertEqual(attributes["@iv"], [31, 30, 29, 28, 27, 26])
        self.assertEqual(attributes["@ev"], [252, 0, 0, 252, 4, 0])

    def test_gender_override_is_resolved(self):
        attributes = {"@species": 280, "@personalID": 255, "@genderflag": 1}

        self.assertEqual(pokemon_gender(attributes), "Female")

    def test_fixed_gender_species_rejects_an_invalid_override(self):
        attributes = {"@species": 81, "@personalID": 123}  # Magnemite

        self.assertEqual(gender_choices_for_species(81), ["Genderless"])
        with self.assertRaises(ValueError):
            apply_pokemon_identity(attributes, 0, False, 0, "Male")

    def test_shiny_override_takes_precedence_over_pid(self):
        attributes = {"@personalID": 0, "@trainerID": 0, "@shinyflag": False}

        self.assertFalse(pokemon_is_shiny(attributes))

    def test_hp_and_special_attack_ev_spread_keeps_stat_order(self):
        self.assertEqual(_sanitize_evs([252, 0, 0, 252, 0, 0]), [252, 0, 0, 252, 0, 0])

    def test_saved_stat_order_is_converted_to_and_from_display_order(self):
        saved = [1, 2, 3, 4, 5, 6]  # HP, Atk, Def, Speed, SpA, SpD

        displayed = _game_stats_to_display(saved)

        self.assertEqual(displayed, [1, 2, 3, 5, 6, 4])
        self.assertEqual(_display_stats_to_game(displayed), saved)

    def test_ev_training_multipliers_scale_and_round_presets(self):
        physical = [4, 252, 0, 0, 0, 252]
        balanced = [85] * 6

        self.assertEqual(_scale_ev_preset(physical, 0.01), [0, 3, 0, 0, 0, 3])
        self.assertEqual(_scale_ev_preset(physical, 0.65), [3, 164, 0, 0, 0, 164])
        self.assertEqual(_scale_ev_preset(physical, 0.10), [0, 25, 0, 0, 0, 25])
        self.assertEqual(_scale_ev_preset(physical, 0.30), [1, 76, 0, 0, 0, 76])
        self.assertEqual(_scale_ev_preset(physical, 0.60), [2, 151, 0, 0, 0, 151])
        self.assertEqual(_scale_ev_preset(balanced, 0.65), [55] * 6)
        self.assertEqual(_scale_ev_preset(physical, 1.0), physical)

    def test_custom_ev_validation_enforces_each_stat_and_total_limits(self):
        current = [252, 252, 0, 0, 0, 0]

        self.assertTrue(_valid_ev_edit(current, 2, "6"))
        self.assertFalse(_valid_ev_edit(current, 2, "7"))
        self.assertFalse(_valid_ev_edit(current, 2, "253"))
        self.assertFalse(_valid_ev_edit(current, 2, "-1"))
        self.assertFalse(_valid_ev_edit(current, 2, "abc"))
        self.assertTrue(_valid_ev_edit(current, 0, ""))

    def test_nature_modifiers_match_the_game_nature_grid(self):
        modest = NATURES.index("Modest")

        self.assertEqual(_nature_stat_multiplier(modest, 0), 90)   # Attack
        self.assertEqual(_nature_stat_multiplier(modest, 3), 110)  # Sp. Attack
        self.assertEqual(_nature_stat_multiplier(modest, 1), 100)

    def test_held_item_picker_ids_round_trip_to_raw_save_ids(self):
        self.assertEqual(item_picker_id(554), 1109)
        self.assertEqual(item_source_id(1109), 554)
        self.assertEqual(item_picker_id(0), 0)
        self.assertEqual(item_source_id(0), 0)

    def test_bag_add_button_includes_the_selected_quantity(self):
        self.assertEqual(bag_add_button_text("99"), "Add 99")
        self.assertEqual(bag_add_button_text(" 5 "), "Add 5")
        self.assertEqual(bag_add_button_text(""), "Add")

    def _party_editor(self, attributes):
        pokemon = RubyObject("PokeBattle_Pokemon", attributes)
        editor = Editor.__new__(Editor)
        editor.trainer_id = 0
        editor.secret_id = 0
        editor.trainer = RubyObject("PokeBattle_Trainer", {"@party": [pokemon]})

        values = {
            "species_id": attributes.get("@species", 0),
            "form": attributes.get("@form", 0),
            "nickname": attributes.get("@name", b"").decode("utf-8"),
            "hp": attributes.get("@hp", 0),
            "totalhp": attributes.get("@totalhp", 0),
            "attack": attributes.get("@attack", 0),
            "defense": attributes.get("@defense", 0),
            "spatk": attributes.get("@spatk", 0),
            "spdef": attributes.get("@spdef", 0),
            "speed": attributes.get("@speed", 0),
            "exp": attributes.get("@exp", 0),
            "item": attributes.get("@item", 0),
            "happiness": attributes.get("@happiness", 0),
            "status": attributes.get("@status", 0),
            "ball": attributes.get("@ballused", 0),
            "obtain_lv": attributes.get("@obtainLevel", 0),
            "nature_idx": NATURES[pokemon_nature(attributes)],
            "gender": pokemon_gender(attributes),
            "shiny": pokemon_is_shiny(attributes),
            "ability_slot": "Overgrow",
        }
        display_iv = _game_stats_to_display(attributes.get("@iv", []))
        display_ev = _game_stats_to_display(attributes.get("@ev", []))
        for i, stat in enumerate(STATS):
            values["iv_" + stat.lower()] = display_iv[i]
            values["ev_" + stat.lower()] = display_ev[i]
        for i, move in enumerate(attributes.get("@moves", [])):
            values[f"move{i}"] = move.attributes.get("@id", 0)
            values[f"movepp{i}"] = move.attributes.get("@pp", 0)

        slot = {key: FakeVar(str(value)) for key, value in values.items()}
        slot["shiny"] = FakeVar(bool(values["shiny"]))
        slot["_ability_choices"] = {"Overgrow": 0}
        slot["_pkmn_obj"] = pokemon
        editor.pkmn_vars = [slot]
        editor._remember_identity_values(slot)
        return editor, pokemon, slot

    def test_untouched_party_save_does_not_add_identity_overrides(self):
        moves = [RubyObject("PBMove", {"@id": i + 1, "@pp": 10, "@ppup": 0}) for i in range(4)]
        attributes = {
            "@species": 3,
            "@name": b"Venusaur",
            "@personalID": 2,
            "@hp": 100,
            "@totalhp": 100,
            "@attack": 80,
            "@defense": 81,
            "@spatk": 100,
            "@spdef": 101,
            "@speed": 79,
            "@exp": 1000,
            "@item": 0,
            "@happiness": 70,
            "@status": 0,
            "@ballused": 4,
            "@obtainLevel": 5,
            "@iv": [1, 2, 3, 4, 5, 6],
            "@ev": [11, 12, 13, 14, 15, 16],
            "@moves": moves,
        }
        editor, pokemon, _slot = self._party_editor(attributes)
        before = writes(editor.trainer, cls=Ruby18Writer)

        editor._apply_party()

        self.assertEqual(writes(editor.trainer, cls=Ruby18Writer), before)
        for field in ("@natureflag", "@shinyflag", "@abilityflag", "@genderflag"):
            self.assertNotIn(field, pokemon.attributes)

    def test_speed_ev_edit_writes_saved_speed_index(self):
        attributes = {
            "@species": 3, "@name": b"Venusaur", "@personalID": 2,
            "@iv": [0] * 6, "@ev": [0] * 6, "@moves": [],
        }
        editor, pokemon, slot = self._party_editor(attributes)
        slot["ev_spe"].set("252")

        editor._apply_party()

        self.assertEqual(pokemon.attributes["@ev"], [0, 0, 0, 252, 0, 0])
        self.assertNotIn("@natureflag", pokemon.attributes)

    def test_held_item_picker_selection_writes_the_raw_game_item_id(self):
        attributes = {
            "@species": 3, "@name": b"Venusaur", "@personalID": 2,
            "@item": 0, "@iv": [0] * 6, "@ev": [0] * 6, "@moves": [],
        }
        editor, pokemon, slot = self._party_editor(attributes)
        slot["item"].set(str(item_source_id(395)))  # Griseous Orb

        editor._apply_party()

        self.assertEqual(pokemon.attributes["@item"], 197)

    def test_untouched_box_save_preserves_natural_identity_and_stat_arrays(self):
        attributes = {
            "@species": 3, "@name": b"Venusaur", "@personalID": 2,
            "@iv": [1, 2, 3, 4, 5, 6], "@ev": [11, 12, 13, 14, 15, 16],
            "@moves": [],
        }
        editor, pokemon, slot = self._party_editor(attributes)
        box = RubyObject("PokemonBox", {"@pokemon": [pokemon]})
        editor.pkmn_vars = []
        editor.box_vars = {0: (0, box, [(0, slot)])}
        before = writes(box, cls=Ruby18Writer)

        editor._apply_boxes()

        self.assertEqual(writes(box, cls=Ruby18Writer), before)
        self.assertEqual(pokemon.attributes["@iv"], [1, 2, 3, 4, 5, 6])
        self.assertEqual(pokemon.attributes["@ev"], [11, 12, 13, 14, 15, 16])
        self.assertNotIn("@natureflag", pokemon.attributes)


class PokemonFormTests(unittest.TestCase):
    @staticmethod
    def _clock(month=7, hour=12):
        return SimpleNamespace(month=month, hour=hour)

    @staticmethod
    def _attributes(species):
        return {
            "@species": species, "@form": 0, "@item": 0,
            "@hp": 100, "@status": 0, "@moves": [],
        }

    @staticmethod
    def _creation_editor():
        editor = Editor.__new__(Editor)
        editor.trainer_id = 0
        editor.secret_id = 0
        editor.storage = None
        editor.trainer = RubyObject("PokeBattle_Trainer", {"@party": []})
        return editor

    def test_generated_form_overrides_cover_known_stats_and_learnsets(self):
        self.assertGreater(len(FORM_OVERRIDE_DATA), 100)
        self.assertEqual(pokemon_base_stats(386, 1), [50, 180, 20, 180, 20, 150])
        attack_moves = pokemon_learnset(386, 1)
        defense_moves = pokemon_learnset(386, 2)
        self.assertIn((49, 88), attack_moves)   # Superpower
        self.assertIn((33, 239), defense_moves) # Spikes
        self.assertNotEqual(attack_moves, defense_moves)

    def test_you_decide_uses_each_move_slot_rule_without_duplicates(self):
        moves = {
            1: {"category": "Physical", "power": 110, "accuracy": 80},
            2: {"category": "Special", "power": 90, "accuracy": 100},
            3: {"category": "Special", "power": 120, "accuracy": 70},
            4: {"category": "Physical", "power": 80, "accuracy": 100},
            5: {"category": "Status", "power": 0, "accuracy": 0},
            6: {"category": "Status", "power": 0, "accuracy": 0},
        }
        learnset = [(1, 1), (5, 2), (10, 3), (15, 4), (20, 5), (30, 6)]

        self.assertEqual(
            recommended_creation_move_ids(learnset, 30, moves),
            [3, 2, 4, 6],
        )

    def test_you_decide_filters_by_level_and_uses_category_for_support(self):
        moves = {
            1: {"category": "Physical", "power": 80, "accuracy": 95},
            2: {"category": "Special", "power": 70, "accuracy": 100},
            3: {"category": "Physical", "power": 0, "accuracy": 100},
            4: {"category": "Status", "power": 0, "accuracy": 0},
            5: {"category": "Status", "power": 0, "accuracy": 0},
            6: {"category": "Physical", "power": 150, "accuracy": 100},
        }
        learnset = [(1, 1), (5, 2), (12, 3), (15, 4), (20, 5), (40, 6)]

        self.assertEqual(
            recommended_creation_move_ids(learnset, 20, moves),
            [1, 2, 3, 5],
        )

    def test_moving_party_pokemon_to_empty_box_slot_compacts_party(self):
        first = RubyObject("PokeBattle_Pokemon", {"@name": b"First"})
        second = RubyObject("PokeBattle_Pokemon", {"@name": b"Second"})
        party = [first, second]
        box_pokemon = []

        displaced = move_party_pokemon_to_box(party, 0, box_pokemon, 3)

        self.assertIsNone(displaced)
        self.assertEqual(party, [second])
        self.assertEqual(box_pokemon[:3], [None, None, None])
        self.assertIs(box_pokemon[3], first)

    def test_moving_party_pokemon_to_occupied_box_slot_swaps(self):
        party_pokemon = RubyObject("PokeBattle_Pokemon", {"@name": b"Party"})
        box_pokemon = RubyObject("PokeBattle_Pokemon", {"@name": b"Box"})
        party = [party_pokemon]
        box = [box_pokemon]

        displaced = move_party_pokemon_to_box(party, 0, box, 0)

        self.assertIs(displaced, box_pokemon)
        self.assertIs(party[0], box_pokemon)
        self.assertIs(box[0], party_pokemon)

    def test_every_generated_form_override_is_well_formed(self):
        named_forms = {
            (species_id, form_id)
            for species_id, forms in FORM_DATA.items()
            for form_id, _name in forms
        }
        for key, override in FORM_OVERRIDE_DATA.items():
            self.assertIn(key, named_forms)
            stats = override.get("stats")
            moves = override.get("moves")
            self.assertTrue(stats or moves)
            if stats:
                self.assertEqual(len(stats), 6)
                self.assertTrue(all(value > 0 for value in stats))
            if moves:
                self.assertTrue(all(level >= 1 and move_id in MOVE_DATA
                                    for level, move_id in moves))

    def test_creation_uses_selected_form_stats_and_nature(self):
        editor = self._creation_editor()

        pokemon = editor._create_pokemon_obj(
            386, form_id=1, nature_index=NATURES.index("Modest"),
            level=50, evs=[0] * 6,
        )

        attributes = pokemon.attributes
        self.assertEqual(pokemon_form(attributes), 1)
        self.assertEqual(attributes["@natureflag"], NATURES.index("Modest"))
        self.assertEqual(attributes["@attack"], 180)
        self.assertEqual(attributes["@spatk"], 220)

    def test_creation_applies_move_controlled_form_prerequisites(self):
        editor = self._creation_editor()

        pokemon = editor._create_pokemon_obj(647, form_id=1, level=50)

        self.assertEqual(pokemon_form(pokemon.attributes), 1)
        self.assertIn(95, pokemon_move_ids(pokemon.attributes))

    def test_bare_shadow_mewtwo_form_is_not_valid_game_state(self):
        attributes = {"@species": 150, "@form": 4, "@item": 0}

        self.assertEqual(pokemon_form(attributes), 0)

    def test_form_selection_refreshes_the_compact_box_sprite(self):
        class FakeLabel:
            def __init__(self):
                self.options = {}
                self.image = None

            def configure(self, **kwargs):
                self.options.update(kwargs)

        editor = Editor.__new__(Editor)
        requested = []
        editor._load_pokemon_sprite = lambda species, form, max_size: (
            requested.append((species, form, max_size)) or "shadow-mewtwo-image"
        )
        editor._set_gender_value = lambda _slot: None
        editor._set_ability_value = lambda _slot: None
        label = FakeLabel()
        slot = {
            "species_id": FakeVar("150"),
            "form": FakeVar("4 - Shadow Mewtwo"),
            "form_sprite": label,
            "form_sprite_size": 72,
        }

        editor._refresh_form_options(slot)

        self.assertEqual(requested, [(150, 4, 72)])
        self.assertEqual(label.options, {"image": "shadow-mewtwo-image", "text": ""})
        self.assertEqual(label.image, "shadow-mewtwo-image")

    def test_shadow_mewtwo_form_sets_the_native_state_flags(self):
        attributes = {"@species": 150, "@form": 0, "@item": 0}

        apply_pokemon_form(attributes, 4)

        self.assertEqual(pokemon_form(attributes), 4)
        self.assertIs(attributes["@normalMewtwo"], False)
        self.assertIs(attributes["@shadowMewtwo"], True)
        self.assertIs(attributes["@shadowMegaMewtwo"], False)

    def test_shadow_mewtwo_state_survives_a_writer_round_trip(self):
        pokemon = RubyObject("PokeBattle_Pokemon", {"@species": 150, "@form": 0, "@item": 0})
        apply_pokemon_form(pokemon.attributes, 5)

        reloaded = loads(writes(pokemon, cls=Ruby18Writer))

        self.assertEqual(pokemon_form(reloaded.attributes), 5)
        self.assertIs(reloaded.attributes["@shadowMewtwo"], True)
        self.assertIs(reloaded.attributes["@shadowMegaMewtwo"], True)

    def test_item_derived_mewtwo_forms_receive_the_required_item(self):
        attributes = {"@species": 150, "@form": 0, "@item": 0}

        apply_pokemon_form(attributes, 1)
        self.assertEqual((pokemon_form(attributes), attributes["@item"]), (1, 554))

        apply_pokemon_form(attributes, 2)
        self.assertEqual((pokemon_form(attributes), attributes["@item"]), (2, 637))

        apply_pokemon_form(attributes, 3)
        self.assertEqual((pokemon_form(attributes), attributes["@item"]), (3, 635))

    def test_every_direct_named_form_persists_without_hidden_prerequisites(self):
        """Audit every catalogued species that has no game getForm handler."""
        checked = 0
        for species, forms in FORM_DATA.items():
            if species in COMPUTED_FORM_SPECIES:
                continue
            for form_id, _name in forms:
                attributes = self._attributes(species)
                apply_pokemon_form(attributes, form_id, now=self._clock())
                self.assertEqual(
                    pokemon_form(attributes, now=self._clock()), form_id,
                    f"species {species}, form {form_id}",
                )
                reloaded = loads(writes(
                    RubyObject("PokeBattle_Pokemon", attributes), cls=Ruby18Writer
                ))
                self.assertEqual(
                    pokemon_form(reloaded.attributes, now=self._clock()), form_id,
                    f"writer round trip: species {species}, form {form_id}",
                )
                checked += 1
        self.assertGreater(checked, 300)

    def test_every_named_alternate_form_has_its_own_battler_sprite(self):
        battlers = resource_path(os.path.join("game_resources", "Graphics", "Battlers"))
        checked = 0
        for species, forms in FORM_DATA.items():
            for form_id, form_name in forms:
                if form_id == 0:
                    continue
                candidates = (
                    f"{species:03d}_{form_id}.png",
                    f"{species:03d}-{form_id}.png",
                    f"{species:03d}{form_id}.png",
                )
                self.assertTrue(
                    any(os.path.exists(os.path.join(battlers, name)) for name in candidates),
                    f"species {species}, form {form_id} ({form_name}) has no form sprite",
                )
                checked += 1
        self.assertEqual(checked, 264)

    def test_every_named_computed_form_gets_its_native_prerequisites(self):
        """Exercise every named form belonging to a getForm species."""
        for species in COMPUTED_FORM_SPECIES - {585, 586}:
            for form_id, _name in FORM_DATA.get(species, []):
                attributes = self._attributes(species)
                if species == 647 and form_id == 0:
                    attributes["@moves"] = [RubyObject(
                        "PBMove", {"@id": 1, "@pp": 10, "@ppup": 0}
                    )]
                apply_pokemon_form(attributes, form_id, now=self._clock())
                self.assertEqual(
                    pokemon_form(attributes, now=self._clock()), form_id,
                    f"species {species}, form {form_id}",
                )

                reloaded = loads(writes(
                    RubyObject("PokeBattle_Pokemon", attributes), cls=Ruby18Writer
                ))
                self.assertEqual(
                    pokemon_form(reloaded.attributes, now=self._clock()), form_id,
                    f"writer round trip: species {species}, form {form_id}",
                )

    def test_all_arceus_plate_forms_set_the_matching_game_item(self):
        expected = {
            1: 158, 2: 161, 3: 159, 4: 160, 5: 164, 6: 163,
            7: 165, 8: 168, 10: 153, 11: 154, 12: 156, 13: 155,
            14: 162, 15: 157, 16: 166, 17: 167, 18: 723,
        }
        for form_id, item_id in expected.items():
            attributes = self._attributes(493)
            apply_pokemon_form(attributes, form_id)
            self.assertEqual((pokemon_form(attributes), attributes["@item"]),
                             (form_id, item_id))

        mystery = self._attributes(493)
        apply_pokemon_form(mystery, 9)
        self.assertEqual((pokemon_form(mystery), mystery["@abilityflag"]), (9, 2))

        primal = self._attributes(493)
        apply_pokemon_form(primal, 19)
        self.assertEqual((pokemon_form(primal), primal["@item"], primal["@primalBattle"]),
                         (19, 812, True))

    def test_armor_drive_and_mega_handlers_resolve_like_the_game(self):
        cases = [
            (487, 1, 197, None), (487, 2, 812, "@primalBattle"),
            (248, 1, 0, "@megaTyranitar"), (248, 2, 753, None),
            (330, 1, 755, None), (330, 2, 0, "@megaFlygon"),
            (542, 1, 754, None), (644, 1, 752, None), (914, 1, 829, None),
            (649, 1, 199, None), (649, 2, 200, None),
            (649, 3, 201, None), (649, 4, 198, None),
        ]
        for species, form_id, item_id, flag in cases:
            attributes = self._attributes(species)
            apply_pokemon_form(attributes, form_id)
            self.assertEqual(pokemon_form(attributes), form_id,
                             f"species {species}, form {form_id}")
            self.assertEqual(attributes["@item"], item_id)
            if flag:
                self.assertIs(attributes[flag], True)

    def test_keldeo_form_is_derived_from_secret_sword(self):
        attributes = self._attributes(647)
        apply_pokemon_form(attributes, 1)
        self.assertIn(95, pokemon_move_ids(attributes))
        self.assertEqual(pokemon_form(attributes), 1)

        # A normal move keeps the Pokemon valid when Secret Sword is removed.
        attributes["@moves"][1] = RubyObject("PBMove", {"@id": 1, "@pp": 10, "@ppup": 0})
        apply_pokemon_form(attributes, 0)
        self.assertNotIn(95, pokemon_move_ids(attributes))
        self.assertEqual(pokemon_form(attributes), 0)

    def test_deerling_and_sawsbuck_are_month_controlled(self):
        expected = {1: 3, 2: 3, 3: 0, 5: 0, 6: 1, 8: 1,
                    9: 2, 11: 2, 12: 3}
        for month, form_id in expected.items():
            now = self._clock(month=month)
            self.assertEqual(seasonal_pokemon_form(now), form_id)
            for species in (585, 586):
                attributes = self._attributes(species)
                attributes["@form"] = (form_id + 1) % 4
                self.assertEqual(pokemon_form(attributes, now=now), form_id)

        with self.assertRaisesRegex(ValueError, "controlled by the current month"):
            apply_pokemon_form(self._attributes(585), 0, now=self._clock(month=7))

    def test_shaymin_sky_form_obeys_time_hp_and_frozen_state(self):
        attributes = self._attributes(492)
        apply_pokemon_form(attributes, 1)
        self.assertEqual(pokemon_form(attributes, now=self._clock(hour=12)), 1)
        self.assertEqual(pokemon_form(attributes, now=self._clock(hour=22)), 0)

        attributes["@hp"] = 0
        self.assertEqual(pokemon_form(attributes, now=self._clock(hour=12)), 0)
        attributes["@hp"] = 100
        attributes["@status"] = 5
        self.assertEqual(pokemon_form(attributes, now=self._clock(hour=12)), 0)


class ShadowPokemonTests(unittest.TestCase):
    """Mirrors makeShadow / pbUpdateShadowMoves / pbPurify from the game script."""

    def _pokemon(self, species=18, move_ids=(1, 2, 3, 4)):
        moves = [RubyObject("PBMove", {"@id": mid, "@pp": 10, "@ppup": 0}) for mid in move_ids]
        return {
            "@species": species,
            "@moves": moves,
            "@ev": [4, 0, 0, 0, 0, 0],
            "@exp": 1000,
            "@heartgauge": 0,
            "@hypermode": False,
        }

    def test_make_shadow_sets_state_and_swaps_in_shadow_moves(self):
        a = self._pokemon(species=18)  # has shadowmoves.dat entry [585, 602]

        make_shadow(a)

        self.assertTrue(pokemon_is_shadow(a))
        self.assertEqual(a["@heartgauge"], HEART_GAUGE_SIZE)
        self.assertEqual(heart_stage(a["@heartgauge"]), 5)
        self.assertEqual(a["@savedexp"], 0)
        self.assertEqual(a["@savedev"], [0] * 6)
        self.assertEqual(a["@shadowmovenum"], 2)
        self.assertEqual(a["@shadowmoves"], [585, 602, 0, 0, 1, 2, 3, 4])
        # Full gauge means no original moves are handed back yet.
        self.assertEqual(pokemon_move_ids(a), [585, 602, 0, 0])

    def test_species_without_shadow_moves_falls_back_to_shadow_rush(self):
        a = self._pokemon(species=1)

        make_shadow(a)

        self.assertEqual(a["@shadowmovenum"], 1)
        self.assertEqual(pokemon_move_ids(a), [SHADOW_RUSH_ID, 0, 0, 0])

    def test_lowering_the_gauge_hands_original_moves_back(self):
        a = self._pokemon(species=18)
        make_shadow(a)

        set_heart_gauge(a, 1000)  # stage 2 → two original moves returned

        self.assertEqual(heart_stage(a["@heartgauge"]), 2)
        self.assertEqual(pokemon_move_ids(a), [585, 602, 3, 4])

    def test_purify_restores_moves_evs_and_saved_exp(self):
        a = self._pokemon(species=18)
        make_shadow(a)
        a["@savedexp"] = 500
        a["@savedev"] = [0, 8, 0, 0, 0, 0]

        restored = purify(a)

        self.assertFalse(pokemon_is_shadow(a))
        self.assertIs(a["@shadow"], False)
        self.assertEqual(a["@heartgauge"], 0)
        self.assertEqual(pokemon_move_ids(a), [1, 2, 3, 4])
        self.assertEqual(a["@ev"], [4, 8, 0, 0, 0, 0])
        self.assertEqual(a["@exp"], 1500)
        self.assertEqual(restored["exp"], 500)
        self.assertNotIn("@shadowmoves", a)
        self.assertNotIn("@savedev", a)
        self.assertNotIn("@savedexp", a)

    def test_custom_shadow_moves_are_packed_and_applied(self):
        a = self._pokemon(species=1)
        make_shadow(a)
        shadow_set, original_set = shadow_move_sets(a)

        # a gap in the middle must be compacted so @shadowmovenum stays meaningful
        set_shadow_move_sets(a, [586, 0, 590, 0], original_set)

        self.assertEqual(a["@shadowmovenum"], 2)
        self.assertEqual(a["@shadowmoves"], [586, 590, 0, 0, 1, 2, 3, 4])
        self.assertEqual(pokemon_move_ids(a), [586, 590, 0, 0])

    def test_dropping_a_shadow_move_leaves_no_gap_in_the_move_slots(self):
        a = self._pokemon(species=1)
        make_shadow(a)
        _, original_set = shadow_move_sets(a)
        set_shadow_move_sets(a, [SHADOW_RUSH_ID, 586], original_set)
        self.assertEqual(pokemon_move_ids(a), [SHADOW_RUSH_ID, 586, 0, 0])

        set_shadow_move_sets(a, [586], original_set)  # drop the first shadow move

        self.assertEqual(pokemon_move_ids(a), [586, 0, 0, 0])

    def test_restashing_originals_changes_what_purify_returns(self):
        a = self._pokemon(species=1)
        make_shadow(a)
        shadow_set, _ = shadow_move_sets(a)

        set_shadow_move_sets(a, shadow_set, [10, 20, 0, 0])
        purify(a)

        self.assertEqual(pokemon_move_ids(a), [10, 20, 0, 0])

    def test_shadow_move_ids_cover_the_shadow_type_and_shadow_sword(self):
        self.assertIn(593, SHADOW_MOVE_IDS)  # Shadow Rush
        self.assertIn(631, SHADOW_MOVE_IDS)  # Shadow Sword — typed Normal
        self.assertTrue(all(mid in MOVE_DATA for mid in SHADOW_MOVE_IDS))
        # Ghost moves that merely start with "Shadow" are not Shadow moves
        for ghost_move in (174, 175, 176, 178, 180):  # Force, Ball, Claw, Punch, Sneak
            self.assertNotIn(ghost_move, SHADOW_MOVE_IDS)

    def test_shadow_state_survives_a_ruby18_writer_round_trip(self):
        pkmn = RubyObject("PokeBattle_Pokemon", self._pokemon(species=18))
        make_shadow(pkmn.attributes)

        reloaded = loads(writes(pkmn, cls=Ruby18Writer))

        a = reloaded.attributes
        self.assertIs(a["@shadow"], True)
        self.assertEqual(a["@heartgauge"], HEART_GAUGE_SIZE)
        self.assertEqual(a["@shadowmoves"], [585, 602, 0, 0, 1, 2, 3, 4])
        self.assertTrue(pokemon_is_shadow(a))


class StreamSplittingTests(unittest.TestCase):
    """A save file is a bare concatenation of Marshal streams with no index."""

    @staticmethod
    def _stream(obj):
        return writes(obj, cls=Ruby18Writer)

    def test_marshal_stream_end_measures_a_single_stream(self):
        blob = self._stream(RubyObject("PokemonBox", {"@name": b"Box 1", "@pokemon": [None, 5]}))
        self.assertEqual(marshal_stream_end(blob + b"\x99" * 7, 0), len(blob))

    def test_payload_containing_the_header_bytes_does_not_split_a_stream(self):
        # 0x01020408 serialises as "i" \x04 \x08 \x02 \x01 - a literal 04 08 pair
        # inside the data, exactly like a Pokemon's @personalID can produce.
        payload = RubyObject("PokeBattle_Pokemon", {"@personalID": 0x01020408})
        storage = RubyObject("PokemonStorage", {"@boxes": [payload]})
        blob = self._stream(storage)
        self.assertIn(b"\x04\x08", blob[2:])

        raw = self._stream(RubyObject("PokeBattle_Trainer", {"@money": 1})) + blob
        positions = split_streams(raw)

        self.assertEqual(len(positions), 2)
        self.assertEqual(positions[1], len(raw) - len(blob))
        reloaded = loads(raw[positions[1]:])
        self.assertEqual(reloaded.ruby_class_name, "PokemonStorage")
        self.assertEqual(reloaded.attributes["@boxes"][0].attributes["@personalID"], 0x01020408)

    def test_every_stream_start_is_reported_in_order(self):
        parts = [
            self._stream(RubyObject("PokeBattle_Trainer", {"@money": 3})),
            self._stream(7),
            self._stream([1, b"two", 3.5, {b"k": True}, None, False]),
            self._stream(RubyObject("PokemonBag", {"@pockets": [[], [[1, 2]]]})),
        ]
        raw = b"".join(parts)

        positions = split_streams(raw)

        expected, offset = [], 0
        for part in parts:
            expected.append(offset)
            offset += len(part)
        self.assertEqual(positions, expected)

    def test_unreadable_data_falls_back_to_the_header_scan(self):
        raw = b"\x04\x08\xff\xff\xff"
        self.assertEqual(split_streams(raw), [0])


class RealSaveFileTests(unittest.TestCase):
    """Opt-in checks against real save files, when any are available locally."""

    @staticmethod
    def _save_files():
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        if not os.path.isdir(base):
            return []
        return [os.path.join(base, f) for f in sorted(os.listdir(base))
                if f.lower().endswith(".rxdata")]

    def test_pc_storage_is_readable_in_every_local_save(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        for path in files:
            with self.subTest(save=os.path.basename(path)):
                with open(path, "rb") as fd:
                    raw = fd.read()
                positions = split_streams(raw)
                self.assertEqual(positions[-1] + len(raw[positions[-1]:]), len(raw))
                found = None
                for idx, start in enumerate(positions):
                    end = positions[idx + 1] if idx + 1 < len(positions) else len(raw)
                    try:
                        obj = loads(raw[start:end])
                    except Exception:
                        continue
                    if getattr(obj, "ruby_class_name", None) == "PokemonStorage":
                        found = obj
                self.assertIsNotNone(found, "PokemonStorage stream did not parse")
                self.assertTrue(any(isinstance(b, RubyObject)
                                    for b in found.attributes.get("@boxes", [])))


if __name__ == "__main__":
    unittest.main()
