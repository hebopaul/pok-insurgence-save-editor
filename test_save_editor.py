import unittest
import tkinter as tk
import datetime
import os
import re
import shutil
import tempfile
from types import SimpleNamespace
from unittest import mock

from rubymarshal.classes import RubyObject
from rubymarshal.reader import loads
from rubymarshal.writer import writes

import save_editor
from save_editor import (
    Editor,
    BALL_NAMES,
    BALL_ITEM_IDS,
    BUILD_LIBRARY,
    MAP_NAMES,
    TOWN_MAP_REGIONS,
    map_display_name,
    map_image_path,
    BUILD_STYLES,
    BUILD_TIERS,
    MOVE_KIND_COLOURS,
    MOVE_KIND_LABELS,
    MOVE_UTILITY_VALUE,
    PKMN_DATA,
    TEACHABLE_DATA,
    pokemon_teachable,
    _build_fields,
    _build_move_ids,
    EV_PRESETS,
    COMPUTED_FORM_SPECIES,
    FORM_OVERRIDE_DATA,
    FORM_DATA,
    HEART_GAUGE_SIZE,
    ITEM_DATA,
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
    build_score,
    build_style,
    build_summary,
    build_tier,
    build_title,
    possessive,
    species_id_from_text,
    ability_slot_from_value,
    apply_pokemon_form,
    apply_pokemon_identity,
    gender_choices_for_species,
    heart_stage,
    item_picker_id,
    item_source_id,
    make_shadow,
    marshal_stream_end,
    move_max_pp,
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


class EditorCatalogTests(unittest.TestCase):
    def test_ball_constants_match_insurgence_stored_ids(self):
        # Order comes from $BallTypes in the game's PokemonBalls script.  It is
        # NOT the vanilla Essentials order: 2/3/4 are Safari/Ultra/Master.
        self.assertEqual("Poké Ball", BALL_NAMES[0])
        self.assertEqual("Safari Ball", BALL_NAMES[2])
        self.assertEqual("Ultra Ball", BALL_NAMES[3])
        self.assertEqual("Master Ball", BALL_NAMES[4])
        self.assertEqual("Love Ball", BALL_NAMES[20])
        self.assertEqual("Delta Ball", BALL_NAMES[26])

    def test_every_named_ball_resolves_to_a_bundled_item_icon(self):
        for ball_id in BALL_NAMES:
            if ball_id == 29:                     # Sync Ball has no item entry
                continue
            self.assertIn(ball_id, BALL_ITEM_IDS)
            self.assertIn(BALL_ITEM_IDS[ball_id], ITEM_DATA)

    def test_standard_ev_presets_use_the_full_510_ev_total(self):
        for name in ("Physical attacker", "Special attacker", "Bulky physical", "Bulky special"):
            self.assertEqual(510, sum(EV_PRESETS[name]), name)

class MovePpTests(unittest.TestCase):
    def test_pp_ups_raise_maximum_by_twenty_percent_each(self):
        self.assertEqual([15, 18, 21, 24], [move_max_pp(175, ups) for ups in range(4)])

    def test_pp_up_count_is_clamped_to_save_field_range(self):
        self.assertEqual(15, move_max_pp(175, -10))
        self.assertEqual(24, move_max_pp(175, 10))


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


class SaveRoundTripTests(unittest.TestCase):
    """Opening a save and saving it again must not change a single byte.

    The stat-recalculation traces on the nature/IV/EV vars fire while the editor
    populates its widgets from the file, so an unguarded fill silently rewrote
    every Pokemon's stored stats - and full-healed them - in saves the user never
    edited.  _fill_party and _fill_pkmn_slot must hold "_syncing" while they
    populate, and recalculation must still run for real edits afterwards.
    """

    @staticmethod
    def _save_files():
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        if not os.path.isdir(base):
            return []
        return [os.path.join(base, f) for f in sorted(os.listdir(base))
                if f.lower().endswith(".rxdata")]

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _editor(self):
        # Building an Editor is expensive, and these tests only ever drive it
        # through _do_load, so one shared instance serves the whole class.
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:                  # no display available
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        return type(self)._app

    def test_loading_then_saving_leaves_the_file_untouched(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        with mock.patch.object(save_editor, "messagebox"):
            app = self._editor()
            for path in files:
                with self.subTest(save=os.path.basename(path)):
                    with tempfile.TemporaryDirectory() as tmp:
                        copy = os.path.join(tmp, os.path.basename(path))
                        shutil.copy2(path, copy)
                        with open(copy, "rb") as fd:
                            original = fd.read()

                        app._do_load(copy)
                        app.update()
                        app._do_save()
                        app.update()

                        with open(copy, "rb") as fd:
                            self.assertEqual(original, fd.read(),
                                             "an untouched save was rewritten")
                        # Backups live in their own folder beside the save now.
                        folder = os.path.join(tmp, save_editor.BACKUP_DIR_NAME)
                        backups = [f for f in os.listdir(folder) if f.endswith(".bak")]
                        self.assertEqual(1, len(backups))
                        with open(os.path.join(folder, backups[0]), "rb") as fd:
                            self.assertEqual(original, fd.read())

    def test_every_save_gets_its_own_backup(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        with mock.patch.object(save_editor, "messagebox"):
            app = self._editor()
            with tempfile.TemporaryDirectory() as tmp:
                copy = os.path.join(tmp, os.path.basename(files[0]))
                shutil.copy2(files[0], copy)
                app._do_load(copy)
                app.update()
                for _ in range(3):
                    app._do_save()
                    app.update()
                folder = os.path.join(tmp, save_editor.BACKUP_DIR_NAME)
                backups = [f for f in os.listdir(folder) if f.endswith(".bak")]
                self.assertEqual(3, len(backups), "backups must never overwrite each other")
                self.assertEqual(3, len(set(backups)))

    def test_loading_does_not_recalculate_but_editing_does(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        stat_keys = ("totalhp", "attack", "defense", "spatk", "spdef", "speed")
        stat_attrs = ("@totalhp", "@attack", "@defense", "@spatk", "@spdef", "@speed")
        with mock.patch.object(save_editor, "messagebox"):
            app = self._editor()
            for path in files:
                with tempfile.TemporaryDirectory() as tmp:
                    copy = os.path.join(tmp, os.path.basename(path))
                    shutil.copy2(path, copy)
                    app._do_load(copy)
                    app.update()
                    v = next((s for s in app.pkmn_vars
                              if isinstance(s.get("_pkmn_obj"), RubyObject)), None)
                    if v is None:
                        continue

                    stored = [str(v["_pkmn_obj"].attributes.get(a, 0)) for a in stat_attrs]
                    self.assertEqual(stored, [v[k].get() for k in stat_keys],
                                     "loading a save must not recalculate stats")

                    v["ev_hp"].set("252")
                    v["ev_atk"].set("252")
                    app.update()
                    app.update_idletasks()
                    app.update()
                    self.assertNotEqual(stored, [v[k].get() for k in stat_keys],
                                        "editing EVs must still recalculate stats")
                    return
        self.skipTest("no local save contains a party Pokemon")


ARCEUS_BUILD = """Trainer: Wild
Species: Arceus
Description: Life Orb Calm Mind set
Level: 100
Nature: Timid
IVs: 31/31/31/31/31/31
EVs: 6 HP / 252 SpA / 252 Spe
Moves:
- Judgment
- Earth Power
- Calm Mind
- Recover
Item: Life Orb
Happiness: 255"""


class BuildLibraryTests(unittest.TestCase):
    """Tier and Style are computed; only Tier may be overridden in the file."""

    def test_tier_follows_the_score_not_the_species_alone(self):
        self.assertIn(build_tier(ARCEUS_BUILD), BUILD_TIERS)
        # A bare species line is not a build, so it must not reach the top tier.
        self.assertNotEqual("S", build_tier("Species: Arceus\nLevel: 100"))

    def test_a_stored_tier_line_wins_over_the_calculation(self):
        self.assertEqual("C", build_tier(ARCEUS_BUILD + "\nTier: C"))

    def test_an_unresolvable_species_does_not_raise(self):
        self.assertEqual("?", build_tier("Species: Nonexistent\nLevel: 100"))
        self.assertEqual("?", build_tier("Level: 100"))
        self.assertEqual(0, build_score("Species: Nonexistent"))

    def test_species_resolves_from_id_name_or_label(self):
        self.assertEqual(493, species_id_from_text("493"))
        self.assertEqual(493, species_id_from_text("Arceus"))
        self.assertEqual(493, species_id_from_text("493 - Arceus"))
        self.assertEqual(0, species_id_from_text("nope"))

    def test_investment_and_power_raise_the_score(self):
        bare = "Species: Arceus\nLevel: 100\nIVs: 0/0/0/0/0/0\nEVs: 0 HP"
        self.assertGreater(build_score(ARCEUS_BUILD), build_score(bare))

    def test_utility_moves_are_all_real_insurgence_moves(self):
        names = {data.get("name") for data in MOVE_DATA.values()}
        for move_name in MOVE_UTILITY_VALUE:
            self.assertIn(move_name, names, f"{move_name} is not an Insurgence move")

    def test_style_reads_the_final_stats(self):
        # 252 SpA / 252 Spe on a frail special attacker is a special sweeper.
        self.assertEqual("Special Sweeper", build_style(ARCEUS_BUILD))
        wall = ARCEUS_BUILD.replace("EVs: 6 HP / 252 SpA / 252 Spe",
                                    "EVs: 252 HP / 252 Def / 6 SpD")
        self.assertNotIn("Sweeper", build_style(wall))

    def test_every_style_returned_is_a_known_tag(self):
        for text in self._bundled_builds():
            with self.subTest(build=build_title(text)):
                self.assertIn(build_style(text), BUILD_STYLES)

    def test_possessive_titles_follow_the_apostrophe_rule(self):
        self.assertEqual("Ash's", possessive("Ash"))
        self.assertEqual("Jesus'", possessive("Jesus"))
        self.assertEqual("Brock's", possessive("Brock"))
        self.assertEqual("Misty's Starmie",
                         build_title("Trainer: Misty\nSpecies: Starmie"))
        # A wild build is titled by species alone.
        self.assertEqual("Arceus", build_title(ARCEUS_BUILD))

    def test_summary_exposes_every_library_column(self):
        summary = build_summary(ARCEUS_BUILD)
        self.assertEqual("Wild", summary["trainer"])
        self.assertEqual("Arceus", summary["species_name"])
        self.assertEqual("Life Orb Calm Mind set", summary["description"])
        self.assertIn(summary["tier"], BUILD_TIERS)
        self.assertIn(summary["style"], BUILD_STYLES)

    @staticmethod
    def _bundled_builds():
        # Only the shipped file: the user's own saved builds are their data, and
        # must not be able to fail the suite.
        return save_editor._read_build_blocks(save_editor.data_path("pokemon_builds.txt"))

    def test_the_bundled_library_is_field_only_and_fully_resolvable(self):
        self.assertTrue(self._bundled_builds(), "bundled build library failed to load")
        for text in self._bundled_builds():
            with self.subTest(build=text.splitlines()[0]):
                self.assertFalse(text.startswith("["), "stored tier prefix left behind")
                summary = build_summary(text)
                self.assertTrue(summary["species_id"], "species did not resolve")
                self.assertTrue(summary["trainer"])
                self.assertTrue(summary["description"])
                self.assertIn(summary["tier"], BUILD_TIERS)

    def test_every_bundled_build_lists_moves_the_game_knows(self):
        for text in self._bundled_builds():
            with self.subTest(build=build_title(text)):
                move_ids = _build_move_ids(text)
                self.assertGreaterEqual(len(move_ids), 3)
                for move_id in move_ids:
                    self.assertIn(move_id, MOVE_DATA)

    def test_a_legacy_display_header_is_ignored_by_the_field_parser(self):
        fields = _build_fields("Giratina - Bulky Special\nSpecies: Giratina")
        self.assertEqual("Giratina", fields.get("species"))

class UserBuildLibraryTests(unittest.TestCase):
    """Builds saved from the editor go to a writable file, not the bundle."""

    def test_saved_builds_land_outside_the_read_only_bundle(self):
        # The bundled file lives inside the PyInstaller archive at runtime, so
        # the user's own library must never resolve to the same path.
        self.assertNotEqual(os.path.abspath(save_editor.data_path("pokemon_builds.txt")),
                            os.path.abspath(save_editor.user_builds_path()))

    def test_appending_a_build_makes_it_visible_to_the_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "nested", "pokemon_builds.user.txt")
            # Restoring the real library must happen after the patch is lifted,
            # or the reload would just re-read the temporary file again.
            self.addCleanup(save_editor.reload_build_library)
            with mock.patch.object(save_editor, "user_builds_path", lambda: target):
                # Baseline is taken under the patch, so whatever the user has
                # saved in their own library cannot affect the counts.
                baseline = len(save_editor.reload_build_library())

                save_editor.append_user_build(ARCEUS_BUILD)
                self.assertTrue(os.path.exists(target))
                self.assertEqual(baseline + 1, len(save_editor.BUILD_LIBRARY))

                save_editor.append_user_build(
                    "Trainer: Misty\nSpecies: Starmie\nLevel: 50\n"
                    "IVs: 31/31/31/31/31/31\nEVs: 252 SpA / 252 Spe\n"
                    "Moves:\n- Hydro Pump\n- Ice Beam")
                self.assertEqual(baseline + 2, len(save_editor.BUILD_LIBRARY))
                titles = [build_title(text) for text in save_editor.BUILD_LIBRARY]
                self.assertIn("Misty's Starmie", titles)


class BuildExportTests(unittest.TestCase):
    """A slot serialises to a block that applies back onto the same slot."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    @staticmethod
    def _save_files():
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        if not os.path.isdir(base):
            return []
        return [os.path.join(base, f) for f in sorted(os.listdir(base))
                if f.lower().endswith(".rxdata")]

    def _loaded_slot(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        app = type(self)._app
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        copy = os.path.join(tmp, os.path.basename(files[0]))
        shutil.copy2(files[0], copy)
        with mock.patch.object(save_editor, "messagebox"):
            app._do_load(copy)
            app.update()
        slot = next((s for s in app.pkmn_vars
                     if isinstance(s.get("_pkmn_obj"), RubyObject)), None)
        if slot is None:
            self.skipTest("no party Pokemon in the local save")
        return app, slot

    def test_an_exported_slot_reapplies_to_the_same_values(self):
        app, slot = self._loaded_slot()
        text = app._build_text_from_slot(slot, "Ash", "Exported set")
        before = [slot[key].get() for key in
                  ("species_id", "level", "nature_idx", "iv_hp", "ev_spa", "happiness")]
        with mock.patch.object(save_editor, "messagebox"):
            app._apply_build_text(slot, text)
            app.update()
        after = [slot[key].get() for key in
                 ("species_id", "level", "nature_idx", "iv_hp", "ev_spa", "happiness")]
        self.assertEqual(before, after)

    def test_an_exported_slot_carries_its_trainer_and_description(self):
        app, slot = self._loaded_slot()
        text = app._build_text_from_slot(slot, "Ash", "Exported set")
        summary = build_summary(text)
        self.assertEqual("Ash", summary["trainer"])
        self.assertEqual("Exported set", summary["description"])
        self.assertTrue(summary["species_id"])
        self.assertIn(summary["style"], BUILD_STYLES)
        self.assertTrue(build_title(text).startswith("Ash's "))

    def test_a_wild_export_omits_the_trainer_line(self):
        app, slot = self._loaded_slot()
        text = app._build_text_from_slot(slot)
        self.assertNotIn("Trainer:", text)
        self.assertEqual("Wild", build_summary(text)["trainer"])

    def test_an_empty_slot_cannot_be_exported(self):
        app, _slot = self._loaded_slot()
        with self.assertRaises(ValueError):
            app._build_text_from_slot({})


class MoveLegalityTests(unittest.TestCase):
    """Level-up and TM/tutor legality come from two different game tables."""

    def test_teachable_data_loaded_for_most_species(self):
        self.assertGreater(len(TEACHABLE_DATA), 800)

    def test_teachable_moves_are_real_moves_for_real_species(self):
        for species_id, moves in list(TEACHABLE_DATA.items())[:60]:
            self.assertIn(species_id, PKMN_DATA)
            for move_id in moves:
                self.assertIn(move_id, MOVE_DATA)

    def test_egg_moves_count_as_teachable(self):
        # eggEmerald.dat is the second source: Charmander inherits these, it
        # never levels into them and no TM teaches them.
        teachable = pokemon_teachable(4)
        levelup = {mid for _lvl, mid in pokemon_learnset(4, 0)}
        names = {MOVE_DATA[m]["name"] for m in teachable - levelup}
        for move in ("Belly Drum", "Dragon Dance", "Crunch"):
            self.assertIn(move, names)

    def test_charizard_can_be_taught_moves_it_never_levels_into(self):
        teachable = pokemon_teachable(6)
        levelup = {mid for _lvl, mid in pokemon_learnset(6, 0)}
        names = {MOVE_DATA[m]["name"] for m in teachable - levelup}
        # Classic TM/tutor coverage that no learnset provides.
        self.assertIn("Outrage", names)
        self.assertIn("Focus Blast", names)
        self.assertTrue(teachable - levelup)

    def test_an_unknown_species_has_no_teachable_moves(self):
        self.assertEqual(set(), pokemon_teachable(999999))

    def test_the_three_legality_kinds_are_distinctly_coloured(self):
        self.assertEqual({"levelup", "teachable", "illegal"}, set(MOVE_KIND_COLOURS))
        self.assertEqual({"levelup", "teachable", "illegal"}, set(MOVE_KIND_LABELS))
        self.assertEqual(3, len(set(MOVE_KIND_COLOURS.values())))


class MapDataTests(unittest.TestCase):
    """Map names and the town map come from the game's own data files."""

    def test_map_names_load_and_resolve(self):
        if not MAP_NAMES:
            self.skipTest("game_resources/Data/MapInfos.rxdata not extracted")
        self.assertGreater(len(MAP_NAMES), 800)
        self.assertIn("Pok\u00e9mon Center", map_display_name(812))

    def test_town_map_regions_and_linked_points(self):
        if not TOWN_MAP_REGIONS:
            self.skipTest("game_resources/Data/townmap.dat not extracted")
        self.assertEqual(2, len(TOWN_MAP_REGIONS))
        linked = [p for region in TOWN_MAP_REGIONS
                  for p in region["points"] if p["map_id"] is not None]
        # Only some town-map points carry a destination; the rest are labels,
        # which is why the viewer also offers the full searchable map list.
        self.assertTrue(linked)
        helios = next(p for p in linked if p["name"] == "Helios City")
        self.assertEqual((13, 12), helios["cell"])
        self.assertEqual(178, helios["map_id"])
        self.assertEqual((49, 82), (helios["x"], helios["y"]))

    def test_route_squares_resolve_through_map_positions(self):
        if not save_editor.MAP_POSITIONS:
            self.skipTest("game_resources/Data/metadata.dat not extracted")
        # townmap.dat names only 27 landmarks; metadata entry 7 (MapPosition) is
        # what puts the routes between them on the town map.
        self.assertGreater(len(save_editor.MAP_POSITIONS), 50)
        self.assertEqual([2], save_editor.maps_at_town_cell(0, 24, 12))   # Telnor Town
        route = save_editor.maps_at_town_cell(0, 24, 9)
        self.assertIn(48, route)                                          # Route 1
        self.assertGreater(len(route), 1)                                 # shares its square
        self.assertEqual([], save_editor.maps_at_town_cell(0, 1, 1))      # open sea

    def test_an_unknown_map_id_still_renders_a_label(self):
        self.assertEqual("-", map_display_name(None))
        self.assertEqual("999999", map_display_name(999999))

    def test_crop_offsets_are_known_for_rendered_maps(self):
        if not save_editor.MAP_IMAGE_INDEX:
            self.skipTest("map images not rendered")
        # Renders are trimmed to the part of the map that has content, so a
        # click must add the offset back to reach the tile the game uses.
        for entry in save_editor.MAP_IMAGE_INDEX.values():
            self.assertGreaterEqual(entry["ox"], 0)
            self.assertGreaterEqual(entry["oy"], 0)
            self.assertLessEqual(entry["ox"] + entry["w"], entry["map_w"])
            self.assertLessEqual(entry["oy"] + entry["h"], entry["map_h"])

    def test_an_unrendered_map_reports_a_zero_offset(self):
        self.assertEqual((0, 0), save_editor.map_image_offset(999999))
        self.assertEqual((0, 0), save_editor.map_image_offset(None))

    def test_map_image_path_is_none_when_not_rendered(self):
        self.assertIsNone(map_image_path(999999))
        self.assertIsNone(map_image_path("nonsense"))

    def test_an_interior_resolves_to_its_parents_town_map_square(self):
        if not save_editor.MAP_PARENTS:
            self.skipTest("map_meta.txt not generated")
        # A Pokemon Center is not a square on the town map, so it has to borrow
        # the square of the town it stands in.  812 -> 130 -> 109 Metchi Town.
        self.assertEqual((0, 20, 15, 109, 2), save_editor.town_cell_for_map(812))
        # Depth 0 means standing on the square itself, which is what tells the
        # viewer to draw a box rather than an arrow.
        self.assertEqual((0, 20, 15, 109, 0), save_editor.town_cell_for_map(109))
        self.assertIsNone(save_editor.town_cell_for_map(None))

    def test_doors_lead_towards_a_map_and_know_which_way_you_walk(self):
        if not save_editor.MAP_DOORS:
            self.skipTest("map_meta.txt not generated")
        # Every transfer event in the game stores direction 0, "retain", so the
        # direction is derived from which neighbouring tile you can stand on.
        self.assertEqual([(11, 25, "up")], save_editor.doors_to(109, 812))
        self.assertEqual([(28, 32, "down")], save_editor.doors_to(812, 109))
        self.assertEqual([], save_editor.doors_to(109, 999999))

    def test_unused_maps_cover_the_essentials_sample_project(self):
        if not save_editor.UNUSED_MAPS:
            self.skipTest("map_meta.txt not generated")
        # Insurgence never deleted the Pokemon Essentials demo, so the map list
        # carries a second Route 1, Lerucean Town, Cedolan Dept and so on, all
        # drawn against tilesets that were repurposed or never shipped.
        for dead in (5, 21, 23, 28, 14, 36):
            self.assertIn(dead, save_editor.UNUSED_MAPS, map_display_name(dead))
        for live in (48, 80, 126, 421, 109, 812):
            self.assertNotIn(live, save_editor.UNUSED_MAPS, map_display_name(live))

    def test_every_unrenderable_map_is_flagged_unused(self):
        if not save_editor.MAP_SKIP_REASONS or not save_editor.UNUSED_MAPS:
            self.skipTest("map images not rendered, or map_meta.txt not generated")
        for map_id in save_editor.MAP_SKIP_REASONS:
            self.assertIn(map_id, save_editor.UNUSED_MAPS, map_display_name(map_id))

    def test_skip_reasons_explain_themselves(self):
        if not save_editor.MAP_SKIP_REASONS:
            self.skipTest("map images not rendered")
        # The viewer must not tell the user to run a renderer that cannot help.
        self.assertIn("does not ship a graphic", save_editor.map_skip_reason(14))
        self.assertIn("no tiles at all", save_editor.map_skip_reason(72))
        self.assertIsNone(save_editor.map_skip_reason(109))
        self.assertIsNone(save_editor.map_skip_reason(None))

    def test_arrow_points_the_way_it_is_asked_to(self):
        up = save_editor.Editor._arrow_points(0, 0, 32, "up")
        down = save_editor.Editor._arrow_points(0, 0, 32, "down")
        left = save_editor.Editor._arrow_points(0, 0, 32, "left")
        right = save_editor.Editor._arrow_points(0, 0, 32, "right")
        self.assertLess(up[1], up[3])       # apex above its base
        self.assertGreater(down[1], down[3])
        self.assertLess(left[0], left[2])   # apex left of its base
        self.assertGreater(right[0], right[2])


class PlayerLocationTests(unittest.TestCase):
    """Position edits write through; untouched saves must not."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _editor_with_save(self):
        source = os.path.join(os.path.expanduser("~"), "Saved Games",
                              "Pokemon Insurgence", "Game.rxdata")
        if not os.path.isfile(source):
            self.skipTest("no local Game.rxdata")
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        app = type(self)._app
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        copy = os.path.join(tmp, "Game.rxdata")
        shutil.copy2(source, copy)
        with mock.patch.object(save_editor, "messagebox"):
            app._do_load(copy)
            app.update()
        return app, copy

    @staticmethod
    def _saved_streams(path):
        with open(path, "rb") as handle:
            raw = handle.read()
        positions = split_streams(raw)
        player = meta = None
        for index, start in enumerate(positions):
            end = positions[index + 1] if index + 1 < len(positions) else len(raw)
            try:
                obj = loads(raw[start:end])
            except Exception:
                continue
            name = getattr(obj, "ruby_class_name", None)
            if name == "Game_Player":
                player = obj.attributes
            elif name == "PokemonGlobalMetadata":
                meta = obj.attributes
        return player, meta

    def test_loading_populates_the_position_fields(self):
        app, _copy = self._editor_with_save()
        self.assertTrue(app.var_player_x.get())
        self.assertTrue(app.var_player_y.get())
        self.assertIsNotNone(app._current_map_id())

    def test_moving_the_player_updates_the_pixel_position_too(self):
        app, copy = self._editor_with_save()
        with mock.patch.object(save_editor, "messagebox"):
            app.var_player_x.set("40")
            app.var_player_y.set("12")
            app._do_save()
            app.update()
        player, _meta = self._saved_streams(copy)
        self.assertEqual(40, player["@x"])
        self.assertEqual(12, player["@y"])
        # real_* is the pixel position the sprite draws at: 128 per tile.
        self.assertEqual(40 * 128, player["@real_x"])
        self.assertEqual(12 * 128, player["@real_y"])

    def test_the_map_id_is_never_touched(self):
        # Stream 9 cannot be rebuilt safely, so the map must stay put.
        app, copy = self._editor_with_save()
        before = app._current_map_id()
        with mock.patch.object(save_editor, "messagebox"):
            app.var_player_x.set("40")
            app._do_save()
            app.update()
        player, _meta = self._saved_streams(copy)
        self.assertEqual(before, player["@oldMap"])

    def test_respawn_and_teleport_points_are_written_separately(self):
        # Kernel.pbStartOver revives you at @pokecenter*; @healingSpot is only
        # where the Teleport move sends you.  Writing one must not disturb the
        # other, which is exactly what the editor used to do.
        app, copy = self._editor_with_save()
        _player, before = self._saved_streams(copy)
        original_healing = list(before["@healingSpot"])
        with mock.patch.object(save_editor, "messagebox"):
            app._respawn_spot = [178, 49, 82]
            app._do_save()
            app.update()
        _player, meta = self._saved_streams(copy)
        self.assertEqual(178, meta["@pokecenterMapId"])
        self.assertEqual(49, meta["@pokecenterX"])
        self.assertEqual(82, meta["@pokecenterY"])
        self.assertEqual(original_healing, list(meta["@healingSpot"]))

        with mock.patch.object(save_editor, "messagebox"):
            app._teleport_spot = [2, 26, 18]
            app._do_save()
            app.update()
        _player, meta = self._saved_streams(copy)
        self.assertEqual([2, 26, 18], list(meta["@healingSpot"]))
        self.assertEqual(178, meta["@pokecenterMapId"])

    def test_the_respawn_field_shown_is_the_one_the_game_revives_you_at(self):
        app, _copy = self._editor_with_save()
        _player, meta = self._saved_streams(_copy)
        self.assertEqual([meta["@pokecenterMapId"], meta["@pokecenterX"],
                          meta["@pokecenterY"]], app._respawn_spot)
        self.assertEqual(list(meta["@healingSpot"]), app._teleport_spot)

    def test_an_untouched_save_does_not_rewrite_the_player_stream(self):
        # Game_Player holds floats that do not re-serialise byte-for-byte, so
        # the stream must only be rewritten when the position actually changed.
        app, copy = self._editor_with_save()
        with open(copy, "rb") as handle:
            before = handle.read()
        with mock.patch.object(save_editor, "messagebox"):
            app._do_save()
            app.update()
        with open(copy, "rb") as handle:
            self.assertEqual(before, handle.read())


class MapViewerTests(unittest.TestCase):
    """The viewer must say three different things in three different ways."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _viewer(self):
        source = os.path.join(os.path.expanduser("~"), "Saved Games",
                              "Pokemon Insurgence", "Game.rxdata")
        if not os.path.isfile(source):
            self.skipTest("no local Game.rxdata")
        if not save_editor.MAP_DOORS:
            self.skipTest("map_meta.txt not generated")
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        app = type(self)._app
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        copy = os.path.join(tmp, "Game.rxdata")
        shutil.copy2(source, copy)
        with mock.patch.object(save_editor, "messagebox"):
            app._do_load(copy)
            app.update()
        app._open_map_viewer()
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.addCleanup(win.destroy)
        widgets = []

        def walk(widget):
            widgets.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(win)
        return app, win, widgets

    @staticmethod
    def _marks(canvas, tag="mark"):
        found = []
        for item in canvas.find_withtag(tag):
            kind = canvas.type(item)
            colour = (canvas.itemcget(item, "fill") if kind in ("polygon", "text")
                      else canvas.itemcget(item, "outline"))
            found.append((kind, colour, canvas.itemcget(item, "text") if kind == "text" else ""))
        return found

    def test_each_point_gets_its_own_colour_and_a_label(self):
        app, _win, widgets = self._viewer()
        region = [w for w in widgets if isinstance(w, tk.Canvas)][0]
        labels = {text: colour for kind, colour, text in self._marks(region) if kind == "text"}
        name = app.var_trainer_name.get().strip()
        self.assertEqual(save_editor.Editor.MARK_PLAYER, labels[name])
        self.assertEqual(save_editor.Editor.MARK_RESPAWN, labels["Respawn"])
        self.assertEqual(save_editor.Editor.MARK_TELEPORT, labels["Teleport"])

    def test_being_inside_a_place_draws_an_arrow_that_opens_it(self):
        app, _win, widgets = self._viewer()
        region = [w for w in widgets if isinstance(w, tk.Canvas)][0]
        # The save has the player inside Metchi Town's Pokemon Center, so the
        # town's square must carry an arrow rather than a box.
        arrows = [i for i in region.find_withtag("mark_player")
                  if region.type(i) == "polygon"]
        self.assertEqual(1, len(arrows))
        points = region.coords(arrows[0])
        self.assertLess(points[1], points[3])          # apex above its base

        # And on a map that merely contains the player, the door gets the arrow.
        tree = [w for w in widgets if isinstance(w, save_editor.ttk.Treeview)][0]
        tree.selection_set("109")
        app.update()
        canvas = [w for w in widgets if isinstance(w, tk.Canvas)][1]
        door = [i for i in canvas.find_withtag("mark_player")
                if canvas.type(i) == "polygon"]
        self.assertEqual(1, len(door))
        apex = canvas.coords(door[0])[:2]
        canvas.event_generate("<Button-1>", x=int(apex[0]), y=int(apex[1]), when="now")
        app.update()
        self.assertEqual(812, app._current_map_id())

    def test_a_selected_tile_is_not_dressed_up_as_the_player(self):
        app, _win, widgets = self._viewer()
        canvas = [w for w in widgets if isinstance(w, tk.Canvas)][1]
        colours = set()
        for item in canvas.find_withtag("marker"):
            option = "outline" if canvas.type(item) == "rectangle" else "fill"
            colours.add(canvas.itemcget(item, option))
        # The selection used to borrow the player's red box, which made every
        # town you clicked look like the one you were standing in.
        self.assertEqual({save_editor.Editor.MARK_SELECT}, colours)

    def test_each_destination_has_its_own_coloured_button(self):
        _app, _win, widgets = self._viewer()
        buttons = {w.cget("text"): w.cget("bg") for w in widgets if isinstance(w, tk.Button)}
        self.assertEqual(save_editor.Editor.MARK_SELECT, buttons["Move Player Here"])
        self.assertEqual(save_editor.Editor.MARK_RESPAWN, buttons["Set Respawn Point"])
        self.assertEqual(save_editor.Editor.MARK_TELEPORT, buttons["Set Teleport Point"])

    def test_unused_maps_stay_out_of_the_list_until_asked_for(self):
        app, _win, widgets = self._viewer()
        tree = [w for w in widgets if isinstance(w, save_editor.ttk.Treeview)][0]
        self.assertNotIn("5", tree.get_children())     # the demo Route 1
        self.assertIn("48", tree.get_children())       # the real one
        check = [w for w in widgets if isinstance(w, save_editor.ttk.Checkbutton)][0]
        check.invoke()
        app.update()
        self.assertIn("5", tree.get_children())
        self.assertIn("unused", tree.item("5", "tags"))

class BuildIdentityTests(unittest.TestCase):
    """A hidden Id is what lets a user build replace a bundled one."""

    def _library_in(self, blocks):
        """Reload the library with a throwaway user file holding these blocks."""
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "pokemon_builds.user.txt")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("\n---\n".join(blocks))
        patcher = mock.patch.object(save_editor, "user_builds_path", lambda: path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(save_editor.reload_build_library)
        save_editor.reload_build_library()
        return path

    def test_bundled_ids_are_derived_from_the_block_not_random(self):
        # tools/gen_builds.py rewrites pokemon_builds.txt wholesale, so the ids
        # have to fall out of the content or every override would be orphaned.
        self._library_in([])
        for text in save_editor.BUILD_LIBRARY:
            self.assertEqual(save_editor.build_content_id(text), save_editor.build_id(text))

    def test_a_user_block_replaces_the_bundled_one_with_the_same_id(self):
        self._library_in([])
        count = len(save_editor.BUILD_LIBRARY)
        target = save_editor.BUILD_LIBRARY[0]
        edited = save_editor.with_build_id(
            save_editor.strip_build_id(target) + "\nHappiness: 7", save_editor.build_id(target))
        self._library_in([edited])
        self.assertEqual(count, len(save_editor.BUILD_LIBRARY))
        self.assertEqual("user", save_editor.BUILD_SOURCES[0])
        self.assertIn("Happiness: 7", save_editor.BUILD_LIBRARY[0])

    def test_a_user_block_with_its_own_id_is_added_not_merged(self):
        self._library_in([])
        count = len(save_editor.BUILD_LIBRARY)
        self._library_in([save_editor.with_build_id(
            "Species: Bulbasaur\nLevel: 5\nNature: Hardy", save_editor.new_build_id())])
        self.assertEqual(count + 1, len(save_editor.BUILD_LIBRARY))
        self.assertEqual("user", save_editor.BUILD_SOURCES[-1])

    def test_the_id_never_reaches_the_user(self):
        block = save_editor.with_build_id("Species: Bulbasaur\nLevel: 5", "abc123")
        self.assertIn("Id: abc123", block)
        self.assertNotIn("Id:", save_editor.strip_build_id(block))
        # Round-tripping must not accumulate Id lines either.
        self.assertEqual(1, save_editor.with_build_id(block, "abc123").count("Id:"))

    def test_saving_replaces_an_entry_rather_than_appending_a_copy(self):
        path = self._library_in([])
        save_editor.save_user_builds([("keep-me", "Species: Bulbasaur\nLevel: 5")])
        save_editor.save_user_builds([("keep-me", "Species: Bulbasaur\nLevel: 9")])
        blocks = save_editor._read_build_blocks(path)
        self.assertEqual(1, len(blocks))
        self.assertIn("Level: 9", blocks[0])


class BuildValidationTests(unittest.TestCase):
    """Nothing is saved until the raw text passes, and errors name their line."""

    def _messages(self, block):
        return {line: message for line, message in save_editor.validate_build_block(block)}

    def test_a_bundled_build_is_valid(self):
        for text in save_editor.BUILD_LIBRARY[:20]:
            self.assertEqual([], save_editor.validate_build_block(save_editor.strip_build_id(text)))

    def test_trainer_and_description_may_be_blank_or_absent(self):
        self.assertEqual([], save_editor.validate_build_block(
            "Species: Bulbasaur\nLevel: 5\nNature: Hardy"))
        self.assertEqual([], save_editor.validate_build_block(
            "Trainer:\nDescription:\nSpecies: Bulbasaur\nLevel: 5"))

    def test_each_syntax_problem_points_at_its_own_line(self):
        block = ("Trainer: Ash\n"                        # 1
                 "Species: Pikachu\n"                    # 2
                 "no colon here\n"                       # 3
                 "Abilty: Static\n"                      # 4
                 "Level: 999\n"                          # 5
                 "EVs: 252 HP / 252 Atk / 252 Spe\n"     # 6
                 "- Stray Bullet\n"                      # 7
                 "Tier: Z")                              # 8
        found = self._messages(block)
        self.assertIn("Key: value", found[3])
        self.assertIn("Unknown field 'Abilty'", found[4])
        self.assertIn("Level", found[5])
        self.assertIn("510", found[6])
        self.assertIn("outside a Moves", found[7])
        self.assertIn("Tier", found[8])

    def test_more_than_four_moves_is_rejected(self):
        block = ("Species: Pikachu\nMoves:\n- Thunderbolt\n- Quick Attack\n"
                 "- Iron Tail\n- Agility\n- Thunder")
        self.assertTrue(any("four moves" in message
                            for _line, message in save_editor.validate_build_block(block)))

    def test_a_missing_species_is_rejected(self):
        self.assertTrue(any("Species is required" in message
                            for _line, message in save_editor.validate_build_block("Level: 5")))

    def test_a_duplicate_field_is_rejected(self):
        self.assertIn("Duplicate", self._messages("Species: Pikachu\nLevel: 5\nLevel: 6")[3])


class BuildDialogTests(unittest.TestCase):
    """The raw editor is the one source of truth, and only Apply commits it."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None
        save_editor.reload_build_library()

    def _dialog(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        path = os.path.join(tmp, "pokemon_builds.user.txt")
        patcher = mock.patch.object(save_editor, "user_builds_path", lambda: path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(save_editor.reload_build_library)
        save_editor.reload_build_library()

        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        app = type(self)._app
        app._open_build_dialog(None)
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.addCleanup(win.destroy)
        widgets = []

        def walk(widget):
            widgets.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(win)
        editor = [w for w in widgets if isinstance(w, tk.Text)][0]
        tree = [w for w in widgets if isinstance(w, save_editor.ttk.Treeview)][0]
        buttons = {w.cget("text"): w for w in widgets if isinstance(w, save_editor.ttk.Button)}
        return app, path, editor, tree, buttons

    def test_selecting_several_rows_loads_them_all_into_the_editor(self):
        app, _path, editor, tree, _buttons = self._dialog()
        tree.selection_set(tree.get_children()[:3])
        app.update()
        text = editor.get("1.0", "end")
        self.assertEqual(3, len(save_editor.split_build_blocks(text)))
        self.assertNotIn("Id:", text)

    def test_editing_reveals_apply_and_locks_the_actions_behind_it(self):
        app, _path, editor, tree, buttons = self._dialog()
        tree.selection_set(tree.get_children()[0])
        app.update()
        self.assertFalse(buttons["Apply RAW Changes"].winfo_manager())
        self.assertEqual("normal", str(buttons["Import to PC"].cget("state")))
        editor.insert("end", "\n# a note")
        app.update()
        self.assertTrue(buttons["Apply RAW Changes"].winfo_manager())
        self.assertEqual("disabled", str(buttons["Import to PC"].cget("state")))

    def test_new_empty_build_clears_the_selection_and_offers_the_field_names(self):
        app, _path, editor, tree, buttons = self._dialog()
        tree.selection_set(tree.get_children()[0])
        app.update()
        buttons["New Empty Build"].invoke()
        app.update()
        self.assertEqual((), tree.selection())
        self.assertEqual(["Trainer:", "Species:", "Form:", "Description:", "Nickname:",
                          "Level:", "Nature:", "Ability:", "IVs:", "EVs:", "Moves:",
                          "Item:", "Happiness:"],
                         editor.get("1.0", "end").strip().splitlines())

    def test_invalid_text_is_refused_and_nothing_is_written(self):
        app, path, editor, tree, buttons = self._dialog()
        tree.selection_set(tree.get_children()[0])
        app.update()
        editor.delete("1.0", "end")
        editor.insert("1.0", "Species: Pikachu\nAbilty: Static")
        app.update()
        with mock.patch.object(save_editor.messagebox, "showerror") as error, \
             mock.patch.object(save_editor.messagebox, "showinfo"):
            buttons["Apply RAW Changes"].invoke()
        self.assertTrue(error.called)
        self.assertIn("Block 1, line 2", error.call_args[0][1])
        self.assertFalse(os.path.exists(path))

    def test_editing_a_bundled_build_overrides_it_instead_of_copying_it(self):
        app, path, editor, tree, buttons = self._dialog()
        before = len(save_editor.BUILD_LIBRARY)
        row = tree.get_children()[0]
        tree.selection_set(row)
        app.update()
        identifier = save_editor.BUILD_IDS[int(row)]
        edited = re.sub(r"^Level: \d+$", "Level: 42",
                        editor.get("1.0", "end").strip(), flags=re.MULTILINE)
        editor.delete("1.0", "end")
        editor.insert("1.0", edited)
        app.update()
        with mock.patch.object(save_editor.messagebox, "showinfo"), \
             mock.patch.object(save_editor.messagebox, "showerror"):
            buttons["Apply RAW Changes"].invoke()
        app.update()
        self.assertEqual(before, len(save_editor.BUILD_LIBRARY))
        saved = save_editor._read_build_blocks(path)
        self.assertEqual(1, len(saved))
        self.assertEqual(identifier, save_editor.build_id(saved[0]))
        self.assertIn("Level: 42", save_editor.BUILD_LIBRARY[int(row)])
        self.assertFalse(buttons["Apply RAW Changes"].winfo_manager())

    def test_extra_blocks_in_an_existing_entry_ask_before_splitting(self):
        app, path, editor, tree, buttons = self._dialog()
        tree.selection_set(tree.get_children()[0])
        app.update()
        editor.insert("end", "\n---\nSpecies: Bulbasaur\nLevel: 5\nNature: Hardy")
        app.update()
        with mock.patch.object(save_editor.messagebox, "askokcancel", return_value=False) as ask, \
             mock.patch.object(save_editor.messagebox, "showinfo"), \
             mock.patch.object(save_editor.messagebox, "showerror"):
            buttons["Apply RAW Changes"].invoke()
        self.assertIn("already existing entry", ask.call_args[0][1])
        self.assertFalse(os.path.exists(path))          # cancelling writes nothing

        with mock.patch.object(save_editor.messagebox, "askokcancel", return_value=True), \
             mock.patch.object(save_editor.messagebox, "showinfo"), \
             mock.patch.object(save_editor.messagebox, "showerror"):
            buttons["Apply RAW Changes"].invoke()
        self.assertEqual(2, len(save_editor._read_build_blocks(path)))

    def test_a_fresh_multi_build_paste_asks_the_other_question(self):
        app, path, editor, tree, buttons = self._dialog()
        buttons["New Empty Build"].invoke()
        app.update()
        editor.delete("1.0", "end")
        editor.insert("1.0", "Species: Bulbasaur\nLevel: 5\nNature: Hardy\n---\n"
                             "Species: Squirtle\nLevel: 5\nNature: Hardy")
        app.update()
        with mock.patch.object(save_editor.messagebox, "askokcancel", return_value=True) as ask, \
             mock.patch.object(save_editor.messagebox, "showinfo"), \
             mock.patch.object(save_editor.messagebox, "showerror"):
            buttons["Apply RAW Changes"].invoke()
        self.assertIn("Multiple Builds detected", ask.call_args[0][1])
        blocks = save_editor._read_build_blocks(path)
        self.assertEqual(2, len(blocks))
        self.assertEqual(2, len({save_editor.build_id(b) for b in blocks}))

class SpeciesVariantTests(unittest.TestCase):
    """Insurgence reuses base names for its Deltas, so a name must say which."""

    def test_a_bare_name_never_means_a_delta(self):
        # id 4 is Fire with Blaze; id 730 is Ghost/Dragon with Spirit Call, and
        # both are called "Charmander" in the game's own species data.
        self.assertEqual(4, save_editor.species_id_from_text("Charmander"))
        self.assertEqual(730, save_editor.species_id_from_text("Delta Charmander"))

    def test_a_variant_is_recognised_however_it_is_written(self):
        for text in ("Delta Charmander", "delta charmander", "DELTACHARMANDER",
                     "Delta  Charmander", "730", "730 - Charmander"):
            self.assertEqual(730, save_editor.species_id_from_text(text), text)

    def test_names_that_mean_two_pokemon_report_both(self):
        # Delta Metagross exists twice, Ground/Bug and Grass/Rock.
        self.assertEqual([867, 870], save_editor.species_candidates("Delta Metagross"))
        self.assertEqual([867], save_editor.species_candidates("Delta Metagross (Ground)"))
        self.assertEqual([870], save_editor.species_candidates("Delta Metagross (Grass)"))

    def test_punctuated_names_still_resolve(self):
        self.assertEqual(83, save_editor.species_id_from_text("Farfetch'd"))
        self.assertEqual(83, save_editor.species_id_from_text("farfetchd"))

    def test_display_names_identify_a_species_on_their_own(self):
        self.assertEqual("Charmander", save_editor.species_display_name(4))
        self.assertEqual("Delta Charmander", save_editor.species_display_name(730))
        self.assertEqual("Delta Metagross (Ground)", save_editor.species_display_name(867))
        self.assertEqual("", save_editor.species_display_name(None))

    def test_every_variant_name_is_unique(self):
        if not save_editor.SPECIES_VARIANTS:
            self.skipTest("species_names.txt not generated")
        names = [display for display, _internal in save_editor.SPECIES_VARIANTS.values()]
        self.assertEqual(len(names), len(set(names)))

    def test_a_variant_round_trips_through_a_build_block(self):
        # The bug this guards: writing the bare name turned a Delta back into
        # its ordinary counterpart, ability and all, with no error anywhere.
        for species_id in (730, 867, 4, 25):
            block = f"Species: {save_editor.species_display_name(species_id)}\nLevel: 50"
            self.assertEqual(species_id, save_editor.species_id_from_text(
                save_editor._build_fields(block)["species"]))


class BundledBuildIntegrityTests(unittest.TestCase):
    """Every shipped build must actually apply, not just parse."""

    def test_no_build_names_an_ability_its_species_cannot_have(self):
        offenders = []
        for text in save_editor.BUILD_LIBRARY:
            fields = save_editor._build_fields(text)
            wanted = fields.get("ability", "").strip()
            if not wanted:
                continue
            species_id = save_editor.species_id_from_text(fields.get("species", ""))
            allowed = [label.split(" (")[0].casefold() for _slot, label
                       in save_editor.ability_choices_for_species(species_id)]
            if wanted.casefold() not in allowed:
                offenders.append(f"{fields.get('species')} / {wanted}")
        self.assertEqual([], offenders)

    def test_every_species_named_resolves_to_exactly_one_pokemon(self):
        for text in save_editor.BUILD_LIBRARY:
            name = save_editor._build_fields(text).get("species", "")
            self.assertEqual(1, len(save_editor.species_candidates(name)), name)

    def test_every_bundled_build_passes_validation(self):
        for text in save_editor.BUILD_LIBRARY:
            block = save_editor.strip_build_id(text)
            self.assertEqual([], save_editor.validate_build_block(block),
                             save_editor.build_title(text))

    def test_the_validator_catches_a_delta_ability_on_a_plain_species(self):
        found = save_editor.validate_build_block(
            "Species: Charmander\nAbility: Spirit Call\nLevel: 5")
        self.assertTrue(any("cannot have" in message for _line, message in found), found)

    def test_the_validator_rejects_an_ambiguous_species(self):
        found = save_editor.validate_build_block("Species: Delta Metagross\nLevel: 5")
        self.assertTrue(any("could mean" in message for _line, message in found), found)

class BoxOverflowTests(unittest.TestCase):
    """Filling a box during an import must remove it from the next question."""

    @staticmethod
    def _box(name, size, used):
        box = RubyObject()
        box.attributes = {
            "@name": name.encode(),
            "@pokemon": [RubyObject() if i < used else None for i in range(size)],
        }
        return box

    def _editor_with_boxes(self, sizes_and_used):
        editor = Editor.__new__(Editor)          # no Tk: only the planner is under test
        boxes = [self._box(f"Box {i + 1}", size, used)
                 for i, (size, used) in enumerate(sizes_and_used)]
        storage = RubyObject()
        storage.attributes = {"@boxes": boxes, "@currentBox": 0}
        editor.storage = storage
        return editor, boxes

    def test_a_filled_box_is_not_offered_again_and_counts_stay_true(self):
        # Box 1 has 3 free, Box 2 has 30. Importing 10 must overflow out of Box 1.
        editor, _boxes = self._editor_with_boxes([(30, 27), (30, 0)])
        asked = []

        def fake_ask(options, remaining, parent=None):
            asked.append([(label, len(slots)) for _idx, _box, label, slots in options])
            return options[0]

        editor._ask_target_box = fake_ask
        editor._ask_overflow = lambda label, fits, remaining, parent=None: "fill"
        placements = editor._plan_build_placements(10)

        self.assertEqual(10, len(placements))
        self.assertEqual(10, len({(id(slots), index) for slots, index in placements}))
        # First question offers both boxes with their real counts...
        self.assertEqual([("Box 1: Box 1", 3), ("Box 2: Box 2", 30)], asked[0])
        # ...the second must not mention Box 1 at all, and Box 2 is still 30.
        self.assertEqual([("Box 2: Box 2", 30)], asked[1])

    def test_a_partly_used_box_reports_what_is_left_not_what_it_started_with(self):
        # Two overflows in a row: each question must reflect the last one.
        editor, _boxes = self._editor_with_boxes([(30, 28), (30, 28), (30, 0)])
        asked = []

        def fake_ask(options, remaining, parent=None):
            asked.append([(label, len(slots)) for _idx, _box, label, slots in options])
            return options[0]

        editor._ask_target_box = fake_ask
        editor._ask_overflow = lambda label, fits, remaining, parent=None: "fill"
        placements = editor._plan_build_placements(10)

        self.assertEqual(10, len(placements))
        self.assertEqual([("Box 1: Box 1", 2), ("Box 2: Box 2", 2), ("Box 3: Box 3", 30)], asked[0])
        self.assertEqual([("Box 2: Box 2", 2), ("Box 3: Box 3", 30)], asked[1])
        self.assertEqual([("Box 3: Box 3", 30)], asked[2])

    def test_auto_never_reuses_a_slot_already_claimed(self):
        editor, _boxes = self._editor_with_boxes([(30, 28), (30, 25), (30, 29)])
        editor._ask_target_box = lambda options, remaining, parent=None: options[0]
        editor._ask_overflow = lambda label, fits, remaining, parent=None: "auto"
        placements = editor._plan_build_placements(7)
        self.assertEqual(7, len(placements))
        self.assertEqual(7, len({(id(slots), index) for slots, index in placements}))

    def test_cancelling_leaves_every_slot_untouched(self):
        editor, boxes = self._editor_with_boxes([(30, 28), (30, 0)])
        before = [list(b.attributes["@pokemon"]) for b in boxes]
        editor._ask_target_box = lambda options, remaining, parent=None: None
        self.assertIsNone(editor._plan_build_placements(5))
        self.assertEqual(before, [list(b.attributes["@pokemon"]) for b in boxes])

class FormNameTests(unittest.TestCase):
    """A form is part of what a Pokemon is, so its name has to resolve too."""

    def test_a_form_name_resolves_to_its_species_and_form(self):
        self.assertEqual([(151, 1)], save_editor.species_form_candidates("Space Mew"))
        self.assertEqual([(6, 1)], save_editor.species_form_candidates("Mega Charizard X"))
        self.assertEqual([(6, 2)], save_editor.species_form_candidates("Mega Charizard Y"))
        self.assertEqual([(151, 0)], save_editor.species_form_candidates("Mew"))

    def test_a_form_name_is_matched_however_it_is_written(self):
        for text in ("Space Mew", "space mew", "SPACEMEW", "Space  Mew"):
            self.assertEqual([(151, 1)], save_editor.species_form_candidates(text), text)

    def test_a_deltas_mega_carries_the_delta_in_its_name(self):
        # The game stores a Delta's Mega under the ordinary one's name, so the
        # qualifier is folded into it rather than bolted on the end.
        self.assertEqual("Mega Venusaur", save_editor.species_display_name(3, 1))
        self.assertEqual("Delta Mega Venusaur", save_editor.species_display_name(729, 1))
        self.assertEqual("Delta Mega Scizor", save_editor.species_display_name(747, 1))
        # A Delta whose own name is qualified keeps that qualifier too.
        self.assertEqual("Delta Mega Metagross (Ground)",
                         save_editor.species_display_name(867, 1))
        # With the Delta named apart, the plain Mega is no longer ambiguous.
        self.assertEqual([(3, 1)], save_editor.species_form_candidates("Mega Venusaur"))
        self.assertEqual([(729, 1)],
                         save_editor.species_form_candidates("Delta Mega Venusaur"))

    def test_a_form_name_without_the_species_in_it_still_needs_qualifying(self):
        # "Delta Summer Form" would mean nothing, so these keep the species.
        self.assertEqual([(585, 1), (586, 1), (776, 1)],
                         save_editor.species_form_candidates("Summer Form"))
        self.assertEqual("Deerling (Summer Form)", save_editor.species_display_name(585, 1))
        self.assertEqual("Delta Snorlax (Summer Form)",
                         save_editor.species_display_name(776, 1))
        # A unique form name needs no qualifying at all.
        self.assertEqual("Space Mew", save_editor.species_display_name(151, 1))

    def test_every_form_name_identifies_exactly_one_pokemon(self):
        folded = [save_editor._fold_species(name)
                  for name in save_editor.FORM_DISPLAY.values()]
        self.assertEqual(len(folded), len(set(folded)))
        # And none of them collides with a plain species name.
        species = {save_editor._fold_species(save_editor.species_display_name(sid))
                   for sid in save_editor.PKMN_DATA}
        self.assertEqual([], [name for name in folded if name in species])

    def test_a_qualified_name_resolves_back_to_exactly_one_pokemon(self):
        for species_id, form_id in ((3, 1), (729, 1), (585, 1), (586, 1), (151, 1), (6, 2)):
            name = save_editor.species_display_name(species_id, form_id)
            self.assertEqual([(species_id, form_id)],
                             save_editor.species_form_candidates(name), name)

    def test_every_named_form_round_trips_through_its_display_name(self):
        for species_id, forms in save_editor.FORM_DATA.items():
            for form_id, _name in forms:
                if not form_id:
                    continue
                shown = save_editor.species_display_name(species_id, form_id)
                self.assertEqual([(species_id, form_id)],
                                 save_editor.species_form_candidates(shown),
                                 f"{species_id}/{form_id} -> {shown!r}")


class FormBuildTests(unittest.TestCase):
    """Builds carry the form, or a Mega silently reverts to its base species."""

    def test_a_form_name_in_the_species_line_is_understood(self):
        self.assertEqual([], save_editor.validate_build_block(
            "Species: Space Mew\nLevel: 50"))
        self.assertEqual([], save_editor.validate_build_block(
            "Species: Mega Charizard X\nLevel: 50"))

    def test_an_explicit_form_line_is_allowed_and_wins(self):
        fields = save_editor._build_fields("Species: Mew\nForm: 1")
        self.assertEqual((151, 1), save_editor.build_species_form(fields))
        fields = save_editor._build_fields("Species: Space Mew\nForm: 0")
        self.assertEqual((151, 0), save_editor.build_species_form(fields))

    def test_an_unknown_species_is_reported_by_the_block_check_itself(self):
        found = save_editor.validate_build_block("Species: Nonsense\nLevel: 5")
        self.assertTrue(any("No Pokemon called" in message for _line, message in found), found)

    def test_a_shared_form_name_is_refused_with_the_options(self):
        found = save_editor.validate_build_block("Species: Summer Form\nLevel: 5")
        self.assertTrue(any("could mean" in message for _line, message in found), found)
        self.assertTrue(any("Delta Snorlax (Summer Form)" in message
                            for _line, message in found), found)

    def test_a_delta_mega_is_accepted_by_name(self):
        self.assertEqual([], save_editor.validate_build_block(
            "Species: Delta Mega Venusaur\nLevel: 50"))
        fields = save_editor._build_fields("Species: Delta Mega Venusaur")
        self.assertEqual((729, 1), save_editor.build_species_form(fields))

    def test_the_summary_describes_the_form_not_the_base_species(self):
        summary = save_editor.build_summary("Species: Space Mew\nLevel: 50\nNature: Hardy")
        self.assertEqual(151, summary["species_id"])
        self.assertEqual(1, summary["form_id"])
        self.assertEqual("Space Mew", summary["species_name"])

    def test_a_megas_base_stats_count_towards_its_tier(self):
        spread = "\nLevel: 100\nNature: Hardy\nIVs: 31/31/31/31/31/31\nEVs: 252 Atk / 252 Spe"
        self.assertGreater(save_editor.build_score("Species: Mega Charizard X" + spread),
                           save_editor.build_score("Species: Charizard" + spread))

class ClassicWidgetThemeTests(unittest.TestCase):
    """ttk styling never reaches tk.Text, tk.Listbox or tk.Canvas."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _editor(self, mode="dark"):
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        app = type(self)._app
        app._set_theme(mode)
        app.update()
        return app

    @staticmethod
    def _widgets(root):
        found = []

        def walk(widget):
            found.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(root)
        return found

    def test_the_raw_build_editor_follows_the_theme(self):
        app = self._editor("dark")
        app._open_build_dialog(None)
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.addCleanup(win.destroy)
        editor = [w for w in self._widgets(win) if isinstance(w, tk.Text)][0]
        self.assertEqual(app._palette["field"], editor.cget("bg"))
        self.assertEqual(app._palette["text"], str(editor.cget("fg")))
        # The caret has to be visible against the new background too.
        self.assertEqual(app._palette["text"], str(editor.cget("insertbackground")))

    def test_the_region_map_canvas_follows_the_theme(self):
        app = self._editor("dark")
        if not isinstance(app.game_player, save_editor.RubyObject):
            app.game_player = save_editor.RubyObject()
            app.game_player.attributes = {"@oldMap": 2, "@x": 0, "@y": 0}
        with mock.patch.object(save_editor, "messagebox"):
            app._open_map_viewer()
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.addCleanup(win.destroy)
        region = [w for w in self._widgets(win) if isinstance(w, tk.Canvas)][0]
        self.assertEqual(app._palette["bg"], region.cget("bg"))

    def test_switching_theme_repaints_widgets_that_are_already_open(self):
        app = self._editor("light")
        app._open_build_dialog(None)
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.addCleanup(win.destroy)
        editor = [w for w in self._widgets(win) if isinstance(w, tk.Text)][0]
        light = editor.cget("bg")
        app._set_theme("dark")
        app.update()
        self.assertNotEqual(light, editor.cget("bg"))
        self.assertEqual(app._palette["field"], editor.cget("bg"))

    def test_a_closed_widget_is_dropped_from_the_registry(self):
        app = self._editor("dark")
        app._open_build_dialog(None)
        app.update()
        win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
        self.assertTrue(app._field_widgets)
        win.destroy()
        app.update()
        app._set_theme("light")      # must not raise on the dead widget
        app.update()
        self.assertEqual(set(), {w for w in app._field_widgets if not w.winfo_exists()})


class ShowMapIconTests(unittest.TestCase):
    """The Show Map button carries the Old Sea Map sprite."""

    def test_the_item_the_icon_comes_from_is_the_old_sea_map(self):
        item = save_editor.ITEM_DATA.get(save_editor.OLD_SEA_MAP_ITEM_ID, {})
        self.assertEqual("Old Sea Map", item.get("name"))

    def test_the_button_shows_the_icon_beside_its_text(self):
        try:
            app = Editor()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update()
        found = []

        def walk(widget):
            found.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(app)
        buttons = [w for w in found
                   if isinstance(w, save_editor.ttk.Button) and w.cget("text") == "Show Map"]
        self.assertEqual(1, len(buttons))
        if not os.path.isdir(save_editor.resource_path(
                os.path.join("game_resources", "Graphics", "Icons"))):
            self.skipTest("item icons not extracted")
        self.assertTrue(str(buttons[0].cget("image")))
        self.assertEqual("left", str(buttons[0].cget("compound")))



class MarshalSymbolTableTests(unittest.TestCase):
    """The stream walker has to name ivars, not just count their bytes.

    Symbols are interned per stream and referred to by index afterwards, so a
    walker that skips the literals silently attributes every later ivar to the
    wrong name - which is how @map_id first came back as "no such field".
    """

    def _walk(self, obj):
        raw = writes(obj, cls=save_editor.Ruby18Writer)
        scanner = save_editor._MarshalScanner(raw, 2)
        scanner._value()
        return scanner

    def test_every_symbol_literal_is_recorded_in_order(self):
        obj = RubyObject("Thing")
        obj.attributes = {"@alpha": 1, "@beta": 2, "@gamma": 3}
        scanner = self._walk(obj)
        for name in ("Thing", "@alpha", "@beta", "@gamma"):
            self.assertIn(name, scanner.symbols)

    def test_a_back_linked_symbol_resolves_to_the_same_name(self):
        # Two objects of one class: the second class name is a ";" back-link.
        inner = RubyObject("Leaf"); inner.attributes = {"@value": 1}
        other = RubyObject("Leaf"); other.attributes = {"@value": 2}
        outer = RubyObject("Branch"); outer.attributes = {"@kids": [inner, other]}
        seen = []

        class Recorder(save_editor._MarshalScanner):
            def _ivar(self, owner, name, start, end):
                seen.append((owner, name))

        raw = writes(outer, cls=save_editor.Ruby18Writer)
        recorder = Recorder(raw, 2)
        recorder._value()
        # Reported innermost first: an ivar's byte range is only known once its
        # value has been walked.  Both Leaves must still be named "Leaf", which
        # is the point - the second one's class symbol is a ";" back-link.
        self.assertEqual([("Leaf", "@value"), ("Leaf", "@value"), ("Branch", "@kids")],
                         seen)

    def test_walking_still_measures_the_stream_exactly(self):
        obj = RubyObject("Thing")
        obj.attributes = {"@a": [1, 2, 3], "@b": {"k": "v"}, "@c": None}
        raw = writes(obj, cls=save_editor.Ruby18Writer)
        self.assertEqual(len(raw), save_editor.marshal_stream_end(raw, 0))


class MapIdSpanTests(unittest.TestCase):
    """Finding - and replacing - the map id inside the unparseable stream."""

    @staticmethod
    def _factory(map_id, map_index=0, maps=None):
        """A PokemonMapFactory shaped like the game's, small enough to read."""
        maps = maps if maps is not None else [map_id]
        built = []
        for index, mid in enumerate(maps):
            game_map = RubyObject("Game_Map")
            event = RubyObject("Game_Event")
            # Game_Event carries an @map_id too; it must not be mistaken for
            # the Game_Map's own.
            event.attributes = {"@map_id": mid, "@id": index}
            game_map.attributes = {"@events": {1: event}, "@map_id": mid,
                                   "@tileset_name": "whatever"}
            built.append(game_map)
        factory = RubyObject("PokemonMapFactory")
        factory.attributes = {"@fixup": False, "@maps": built, "@mapIndex": map_index}
        return writes(factory, cls=save_editor.Ruby18Writer)

    def test_it_finds_the_game_maps_own_id_not_an_events(self):
        raw = self._factory(812)
        found = save_editor.find_map_id_span(raw, 0, len(raw))
        self.assertIsNotNone(found)
        self.assertEqual(812, found[0])

    def test_it_follows_map_index_into_the_maps_array(self):
        raw = self._factory(0, map_index=1, maps=[400, 401, 402])
        self.assertEqual(401, save_editor.find_map_id_span(raw, 0, len(raw))[0])

    def test_a_stream_of_another_shape_is_refused(self):
        other = RubyObject("Game_Player")
        other.attributes = {"@x": 1, "@y": 2}
        raw = writes(other, cls=save_editor.Ruby18Writer)
        self.assertIsNone(save_editor.find_map_id_span(raw, 0, len(raw)))
        with self.assertRaises(ValueError):
            save_editor.relocate_map_id(raw, 0, len(raw), 5)

    def test_rewriting_to_the_same_id_changes_nothing(self):
        raw = self._factory(812)
        self.assertEqual(raw, save_editor.relocate_map_id(raw, 0, len(raw), 812))

    def test_the_rewrite_survives_the_fixnum_changing_length(self):
        # 122 is a one-byte Fixnum, 123 takes two and 812 takes three, so these
        # cover shrinking and growing the stream around the back-links.
        raw = self._factory(812)
        for target in (1, 122, 123, 812, 5000):
            with self.subTest(target=target):
                new = save_editor.relocate_map_id(raw, 0, len(raw), target)
                self.assertEqual(len(new), save_editor.marshal_stream_end(new, 0))
                self.assertEqual(target, save_editor.find_map_id_span(new, 0, len(new))[0])

    def test_only_the_map_id_bytes_move(self):
        raw = self._factory(812)
        _value, start, end = save_editor.find_map_id_span(raw, 0, len(raw))
        new = save_editor.relocate_map_id(raw, 0, len(raw), 7)
        self.assertEqual(raw[:start], new[:start])
        self.assertEqual(raw[end:], new[len(new) - (len(raw) - end):])


class RealSaveMapStreamTests(unittest.TestCase):
    """The same thing against the files the game actually wrote."""

    @staticmethod
    def _save_files():
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        if not os.path.isdir(base):
            return []
        return [os.path.join(base, f) for f in sorted(os.listdir(base))
                if f.lower().endswith(".rxdata")]

    def test_every_local_save_yields_a_map_the_game_knows(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        for path in files:
            with self.subTest(save=os.path.basename(path)):
                with open(path, "rb") as fd:
                    raw = fd.read()
                positions = save_editor.split_streams(raw)
                found = None
                for idx, start in enumerate(positions):
                    end = positions[idx+1] if idx+1 < len(positions) else len(raw)
                    found = save_editor.find_map_id_span(raw, start, end)
                    if found:
                        break
                self.assertIsNotNone(found, "no PokemonMapFactory stream")
                self.assertIn(found[0], MAP_NAMES)

    def test_relocating_a_real_save_leaves_every_other_stream_alone(self):
        files = self._save_files()
        if not files:
            self.skipTest("no local .rxdata save files")
        with open(files[0], "rb") as fd:
            raw = fd.read()
        positions = save_editor.split_streams(raw)
        factory = next(i for i, s in enumerate(positions)
                       if save_editor.find_map_id_span(
                           raw, s, positions[i+1] if i+1 < len(positions) else len(raw)))
        start = positions[factory]
        end = positions[factory+1] if factory+1 < len(positions) else len(raw)
        spliced = raw[:start] + save_editor.relocate_map_id(raw, start, end, 109) + raw[end:]
        after = save_editor.split_streams(spliced)
        self.assertEqual(len(positions), len(after))
        for idx in range(len(positions)):
            if idx == factory:
                continue
            with self.subTest(stream=idx):
                a = positions[idx], positions[idx+1] if idx+1 < len(positions) else len(raw)
                b = after[idx], after[idx+1] if idx+1 < len(after) else len(spliced)
                self.assertEqual(raw[a[0]:a[1]], spliced[b[0]:b[1]])
        self.assertEqual(109, save_editor.find_map_id_span(
            spliced, after[factory],
            after[factory+1] if factory+1 < len(after) else len(spliced))[0])


class MapPassabilityTests(unittest.TestCase):
    """The data that stops a relocation stranding the player inside a wall."""

    def test_maps_carry_a_size_and_a_bitmap(self):
        if not save_editor.MAP_PASSABLE:
            self.skipTest("map_meta.txt has no passability section")
        self.assertGreater(len(save_editor.MAP_PASSABLE), 700)
        for map_id, (width, height, bits) in list(save_editor.MAP_PASSABLE.items())[:20]:
            with self.subTest(map=map_id):
                self.assertGreater(width, 0)
                self.assertGreater(height, 0)
                self.assertTrue(bits)

    def test_a_tile_outside_the_map_is_never_standable(self):
        if not save_editor.MAP_PASSABLE:
            self.skipTest("map_meta.txt has no passability section")
        map_id = next(iter(sorted(save_editor.MAP_PASSABLE)))
        width, height = save_editor.map_size(map_id)
        self.assertFalse(save_editor.map_tile_is_standable(map_id, width, 0))
        self.assertFalse(save_editor.map_tile_is_standable(map_id, 0, height))
        self.assertFalse(save_editor.map_tile_is_standable(map_id, -1, 0))

    def test_an_unknown_map_is_allowed_rather_than_blocked(self):
        # Not being able to answer is not the same as answering no.
        self.assertIsNone(save_editor.map_size(999999))
        self.assertTrue(save_editor.map_tile_is_standable(999999, 5, 5))

    def test_every_place_on_the_town_map_has_somewhere_to_stand(self):
        """A handful of maps really are solid, so check the ones that count.

        Telnor Town Forest, Blacmap, Oscar Top, FLASH_ARCEUS and Space are
        cutscene backdrops, and map 51 "Dungeon" ships empty because the game
        generates its tiles at runtime in an onMapCreate handler.  Anywhere the
        player can genuinely walk to has to decode as walkable, or the check
        that guards a relocation would be rejecting real destinations.
        """
        if not save_editor.MAP_PASSABLE:
            self.skipTest("map_meta.txt has no passability section")
        empty = []
        for map_id in sorted(save_editor.MAP_CELL):
            if map_id in save_editor.UNUSED_MAPS:
                continue
            bits = save_editor._passable_bits(map_id)
            if bits is not None and not any(bits):
                empty.append(map_id)
        self.assertEqual([], empty, "these town-map places decode as solid rock")

    def test_the_maps_that_are_solid_throughout_are_the_known_few(self):
        if not save_editor.MAP_PASSABLE:
            self.skipTest("map_meta.txt has no passability section")
        empty = [m for m in sorted(save_editor.MAP_PASSABLE)
                 if save_editor._passable_bits(m) is not None
                 and not any(save_editor._passable_bits(m))]
        self.assertLess(len(empty), 12,
                        "a decoding change has made real maps look impassable")

    def test_bicycle_rules_follow_the_games_own_order(self):
        if not save_editor.MAP_METADATA:
            self.skipTest("metadata.dat not extracted")
        # pbCanUseBike?: BicycleAlways wins, then Bicycle, then Outdoor.
        with mock.patch.object(save_editor, "MAP_METADATA",
                               [None, [None, False, None, None, True],
                                [None, False, None, False, False],
                                [None, True, None, None, None]]):
            self.assertTrue(save_editor.map_allows_bicycle(1))   # BicycleAlways
            self.assertFalse(save_editor.map_allows_bicycle(2))  # explicit Bicycle
            self.assertTrue(save_editor.map_allows_bicycle(3))   # falls back to Outdoor


class CrossMapTeleportTests(unittest.TestCase):
    """Moving the player to another map, through the editor, end to end."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _editor(self):
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        return type(self)._app

    @staticmethod
    def _save_file():
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        if not os.path.isdir(base):
            return None
        found = [os.path.join(base, f) for f in sorted(os.listdir(base))
                 if f.lower().endswith(".rxdata")]
        return found[0] if found else None

    @staticmethod
    def _somewhere_else(app):
        """A map the player is not on, with a tile they could stand on."""
        for map_id in sorted(save_editor.MAP_PASSABLE):
            if map_id == app._loaded_map_id or map_id in save_editor.UNUSED_MAPS:
                continue
            width, height = save_editor.map_size(map_id)
            for y in range(height):
                for x in range(width):
                    if save_editor.map_tile_is_standable(map_id, x, y):
                        return map_id, x, y
        return None

    def _loaded(self, tmp):
        path = self._save_file()
        if path is None:
            self.skipTest("no local .rxdata save files")
        copy = os.path.join(tmp, os.path.basename(path))
        shutil.copy2(path, copy)
        app = self._editor()
        app._do_load(copy)
        app.update()
        return app, copy

    def test_a_save_reports_the_map_from_its_factory_stream(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                self.assertTrue(app._can_relocate())
                self.assertIsNotNone(app._loaded_map_id)
                self.assertIsNone(app._target_map_id)
                self.assertEqual(app._loaded_map_id, app._current_map_id())

    def test_moving_within_the_same_map_does_not_touch_the_map_stream(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                with open(copy, "rb") as fd:
                    before = fd.read()
                here = app._current_map_id()
                x, y = int(app.var_player_x.get()), int(app.var_player_y.get())
                self.assertTrue(app._move_player_to(here, x + 1, y))
                self.assertIsNone(app._target_map_id)
                app._do_save()
                app.update()
                with open(copy, "rb") as fd:
                    after = fd.read()
                positions, later = (save_editor.split_streams(before),
                                    save_editor.split_streams(after))
                factory = app.factory_idx
                self.assertEqual(before[positions[factory]:positions[factory+1]],
                                 after[later[factory]:later[factory+1]])

    def test_moving_to_another_map_rewrites_the_id_and_arms_the_rebuild(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                destination = self._somewhere_else(app)
                if destination is None:
                    self.skipTest("no other map with a standable tile")
                map_id, x, y = destination
                self.assertTrue(app._move_player_to(map_id, x, y))
                self.assertEqual(map_id, app._target_map_id)
                self.assertIn("(pending)", app.var_player_location.get())

                app._do_save()
                app.update()
                with open(copy, "rb") as fd:
                    after = fd.read()
                positions = save_editor.split_streams(after)

                def stream(idx):
                    end = positions[idx+1] if idx+1 < len(positions) else len(after)
                    return after[positions[idx]:end]

                found = save_editor.find_map_id_span(
                    after, positions[app.factory_idx],
                    positions[app.factory_idx+1] if app.factory_idx+1 < len(positions)
                    else len(after))
                self.assertEqual(map_id, found[0], "the map stream still names the old map")
                # Without safesave the game loads that id with the old tiles.
                meta = loads(stream(app.meta_idx)).attributes
                self.assertIs(True, meta["@safesave"])
                self.assertFalse(meta.get("@surfing"))
                self.assertFalse(meta.get("@diving"))
                player = loads(stream(app.player_idx)).attributes
                self.assertEqual((x, y), (player["@x"], player["@y"]))
                self.assertEqual((x * 128, y * 128), (player["@real_x"], player["@real_y"]))
                self.assertEqual(map_id, player["@oldMap"])
                if app.mapid_int_idx is not None:
                    self.assertEqual(map_id, loads(stream(app.mapid_int_idx)))

                # And the editor must read its own file back the same way.
                app._do_load(copy)
                app.update()
                self.assertEqual(map_id, app._loaded_map_id)
                self.assertIsNone(app._target_map_id)
                self.assertNotIn("(pending)", app.var_player_location.get())

    def test_going_back_to_the_starting_map_cancels_the_move(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                destination = self._somewhere_else(app)
                if destination is None:
                    self.skipTest("no other map with a standable tile")
                home = app._loaded_map_id
                x, y = int(app.var_player_x.get()), int(app.var_player_y.get())
                app._move_player_to(destination[0], destination[1], destination[2])
                self.assertIsNotNone(app._target_map_id)
                app._move_player_to(home, x, y)
                self.assertIsNone(app._target_map_id, "an undone move must write nothing")
                self.assertNotIn("(pending)", app.var_player_location.get())

    def test_a_map_with_no_file_is_refused(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                self.assertFalse(app._move_player_to(999999, 5, 5))
                self.assertIsNone(app._target_map_id)
                self.assertTrue(box.showerror.called)

    def test_a_solid_tile_needs_confirming(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                here = app._current_map_id()
                width, height = save_editor.map_size(here)
                solid = next(((x, y) for y in range(height) for x in range(width)
                              if not save_editor.map_tile_is_standable(here, x, y)), None)
                if solid is None:
                    self.skipTest("this map has no solid tile")
                box.askyesno.return_value = False
                self.assertFalse(app._move_player_to(here, *solid))
                box.askyesno.return_value = True
                self.assertTrue(app._move_player_to(here, *solid))

    def test_the_viewer_offers_move_player_here_on_a_different_map(self):
        """The button used to be grey on every map but the player's own."""
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                destination = self._somewhere_else(app)
                if destination is None:
                    self.skipTest("no other map with a standable tile")
                map_id, x, y = destination
                app._open_map_viewer()
                app.update()
                win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
                self.addCleanup(win.destroy)

                widgets = []

                def walk(widget):
                    widgets.append(widget)
                    for child in widget.winfo_children():
                        walk(child)

                walk(win)
                move = next(w for w in widgets if isinstance(w, tk.Button)
                            and w.cget("text") == "Move Player Here")
                tree = [w for w in widgets if isinstance(w, save_editor.ttk.Treeview)][0]
                # The viewer opens on the player's own tile, already selected.
                self.assertEqual("normal", str(move.cget("state")))

                # Changing map drops the selection, so the button goes grey.
                tree.selection_set(str(map_id))
                app.update()
                self.assertEqual("disabled", str(move.cget("state")))

                # And picking a tile there is accepted, which is the part that
                # used to be impossible: the rule for offering the move was
                # "the map the player is on" rather than "this save can be
                # relocated at all".
                self.assertTrue(app._can_relocate())
                self.assertTrue(app._move_player_to(map_id, x, y, parent=win))
                self.assertEqual(map_id, app._target_map_id)

    def test_relocation_is_refused_when_the_map_stream_is_unreadable(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                destination = self._somewhere_else(app)
                if destination is None:
                    self.skipTest("no other map with a standable tile")
                app._map_span = None            # as if the stream were unfamiliar
                self.assertFalse(app._can_relocate())
                self.assertFalse(app._move_player_to(*destination))
                self.assertIsNone(app._target_map_id)
                self.assertTrue(box.showerror.called)


class BackupNamingTests(unittest.TestCase):
    """Everything the Restore list needs is in the filename, so it must survive."""

    WHEN = datetime.datetime(2026, 9, 11, 21, 13, 37, 571865)

    def _round_trip(self, kind, label):
        path = save_editor.backup_path(os.path.join("C:", "saves", "Game.rxdata"),
                                       kind, label, now=self.WHEN)
        parsed = save_editor.parse_backup_name(path)
        self.assertIsNotNone(parsed, path)
        return parsed

    def test_an_automatic_backup_round_trips(self):
        parsed = self._round_trip("auto", "")
        self.assertEqual("Game.rxdata", parsed["save"])
        self.assertEqual("auto", parsed["kind"])
        self.assertEqual("", parsed["label"])
        self.assertEqual(self.WHEN, parsed["when"])

    def test_a_manual_backup_without_a_label_round_trips(self):
        parsed = self._round_trip("manual", "")
        self.assertEqual("manual", parsed["kind"])
        self.assertEqual("", parsed["label"])

    def test_a_label_round_trips_including_spaces_and_dots(self):
        for label in ("Before Elite Four", "v1.2 run", "gym_4 (hard)", "a.b.c"):
            with self.subTest(label=label):
                self.assertEqual(label, self._round_trip("manual", label)["label"])

    def test_the_backup_lands_in_its_own_folder(self):
        path = save_editor.backup_path(os.path.join("C:", "saves", "Game.rxdata"),
                                       "auto", now=self.WHEN)
        self.assertEqual(save_editor.BACKUP_DIR_NAME,
                         os.path.basename(os.path.dirname(path)))

    def test_backups_written_before_the_folder_existed_still_parse(self):
        # These have no kind token; they came from a save, so they read as auto.
        parsed = save_editor.parse_backup_name("Game.rxdata.20260909-131737-128033.bak")
        self.assertIsNotNone(parsed)
        self.assertEqual("Game.rxdata", parsed["save"])
        self.assertEqual("auto", parsed["kind"])
        self.assertEqual("", parsed["label"])

    def test_files_that_are_not_ours_are_ignored(self):
        for name in ("Game.rxdata", "Save_0_Backup_1.rxdata", "notes.bak",
                     "Game.rxdata.bak", "Game.rxdata.2026-09-09.bak"):
            with self.subTest(name=name):
                self.assertIsNone(save_editor.parse_backup_name(name))

    def test_an_unknown_kind_is_refused(self):
        with self.assertRaises(ValueError):
            save_editor.backup_path("Game.rxdata", "sideways")


class BackupLabelTests(unittest.TestCase):
    """A label goes straight into a filename, so Windows' rules apply."""

    def test_characters_windows_forbids_are_rejected(self):
        for bad in '<>:"/\\|?*':
            with self.subTest(char=bad):
                self.assertFalse(save_editor.backup_label_is_legal("run" + bad))

    def test_control_characters_are_rejected(self):
        self.assertFalse(save_editor.backup_label_is_legal("run\x01two"))
        self.assertFalse(save_editor.backup_label_is_legal("run\ttwo"))

    def test_ordinary_names_are_accepted(self):
        for good in ("Before Elite Four", "run-2 (hard)", "gym_4", "v1.2",
                     "x" * save_editor.BACKUP_LABEL_MAX, ""):
            with self.subTest(label=good):
                self.assertTrue(save_editor.backup_label_is_legal(good))

    def test_an_over_long_label_is_rejected_as_typed_and_capped_on_use(self):
        too_long = "x" * (save_editor.BACKUP_LABEL_MAX + 1)
        self.assertFalse(save_editor.backup_label_is_legal(too_long))
        self.assertEqual(save_editor.BACKUP_LABEL_MAX,
                         len(save_editor.clean_backup_label(too_long)))

    def test_trailing_dots_and_spaces_are_trimmed(self):
        # Windows drops these silently, which would make the name on disk differ
        # from the one the user typed.
        self.assertEqual("run", save_editor.clean_backup_label("  run.. "))
        self.assertEqual("", save_editor.clean_backup_label("   "))
        self.assertEqual("", save_editor.clean_backup_label("..."))

    def test_cleaning_collapses_runs_of_whitespace(self):
        self.assertEqual("a b", save_editor.clean_backup_label("a    b"))


class BackupFolderTests(unittest.TestCase):
    """Listing, pruning and migrating, all on a throwaway folder."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.folder = os.path.join(self.tmp, save_editor.BACKUP_DIR_NAME)
        os.makedirs(self.folder, exist_ok=True)

    def _write(self, save, index, kind, label="", where=None):
        when = datetime.datetime(2026, 1, 1) + datetime.timedelta(minutes=index)
        path = save_editor.backup_path(os.path.join(self.tmp, save), kind, label, now=when)
        if where is not None:
            path = os.path.join(where, os.path.basename(path))
        with open(path, "wb") as fd:
            fd.write(b"x" * (index + 1))
        return path

    def test_listing_is_newest_first_and_covers_every_save(self):
        self._write("Game.rxdata", 0, "auto")
        self._write("Game_1.rxdata", 5, "manual", "later")
        self._write("Game.rxdata", 2, "manual", "middle")
        found = save_editor.list_backups(self.tmp)
        self.assertEqual(3, len(found))
        self.assertEqual(["later", "middle", ""], [e["label"] for e in found])
        self.assertEqual({"Game.rxdata", "Game_1.rxdata"}, {e["save"] for e in found})
        self.assertTrue(all(e["size"] for e in found))

    def test_listing_a_folder_with_no_backups_is_empty_not_an_error(self):
        self.assertEqual([], save_editor.list_backups(os.path.join(self.tmp, "nope")))

    def test_pruning_keeps_the_newest_automatic_backups(self):
        written = [self._write("Game.rxdata", i, "auto") for i in range(13)]
        save_editor.prune_auto_backups(os.path.join(self.tmp, "Game.rxdata"))
        left = save_editor.list_backups(self.tmp)
        self.assertEqual(save_editor.AUTO_BACKUP_LIMIT, len(left))
        # _write stamps them in ascending order, so the survivors are the tail.
        survivors = {os.path.basename(e["path"]) for e in left}
        self.assertEqual({os.path.basename(p)
                          for p in written[-save_editor.AUTO_BACKUP_LIMIT:]}, survivors)

    def test_pruning_never_touches_a_named_backup(self):
        for i in range(13):
            self._write("Game.rxdata", i, "auto")
        for i in range(3):
            self._write("Game.rxdata", 100 + i, "manual", "keep %d" % i)
        save_editor.prune_auto_backups(os.path.join(self.tmp, "Game.rxdata"))
        left = save_editor.list_backups(self.tmp)
        self.assertEqual(3, len([e for e in left if e["kind"] == "manual"]))
        self.assertEqual(save_editor.AUTO_BACKUP_LIMIT,
                         len([e for e in left if e["kind"] == "auto"]))

    def test_pruning_one_save_leaves_another_saves_history_alone(self):
        for i in range(13):
            self._write("Game.rxdata", i, "auto")
        for i in range(4):
            self._write("Game_1.rxdata", i, "auto")
        save_editor.prune_auto_backups(os.path.join(self.tmp, "Game.rxdata"))
        left = save_editor.list_backups(self.tmp)
        self.assertEqual(4, len([e for e in left if e["save"] == "Game_1.rxdata"]))

    def test_backups_left_beside_the_save_are_moved_into_the_folder(self):
        legacy = os.path.join(self.tmp, "Game.rxdata.20260909-131737-128033.bak")
        with open(legacy, "wb") as fd:
            fd.write(b"old")
        with open(os.path.join(self.tmp, "Game.rxdata"), "wb") as fd:
            fd.write(b"save")
        moved = save_editor.migrate_legacy_backups(self.tmp)
        self.assertEqual(1, moved)
        self.assertFalse(os.path.exists(legacy))
        self.assertTrue(os.path.isfile(os.path.join(self.folder, os.path.basename(legacy))))
        # The save itself, and anything not ours, stays put.
        self.assertTrue(os.path.isfile(os.path.join(self.tmp, "Game.rxdata")))

    def test_migration_is_safe_to_repeat(self):
        with open(os.path.join(self.tmp, "Game.rxdata.20260909-131737-128033.bak"), "wb") as fd:
            fd.write(b"old")
        self.assertEqual(1, save_editor.migrate_legacy_backups(self.tmp))
        self.assertEqual(0, save_editor.migrate_legacy_backups(self.tmp))


class BackupRestoreTests(unittest.TestCase):
    """The two buttons, driven through the editor against a real save."""

    _app = None

    @classmethod
    def tearDownClass(cls):
        if cls._app is not None:
            cls._app.destroy()
            cls._app = None

    def _editor(self):
        if type(self)._app is None:
            try:
                app = Editor()
            except tk.TclError as exc:
                self.skipTest(f"Tk is unavailable: {exc}")
            app.withdraw()
            type(self)._app = app
        return type(self)._app

    def _loaded(self, tmp):
        base = os.path.join(os.path.expanduser("~"), "Saved Games", "Pokemon Insurgence")
        source = os.path.join(base, "Game.rxdata")
        if not os.path.isfile(source):
            self.skipTest("no local Game.rxdata")
        copy = os.path.join(tmp, "Game.rxdata")
        shutil.copy2(source, copy)
        app = self._editor()
        app._do_load(copy)
        app.update()
        return app, copy

    def test_the_backup_button_writes_one_named_copy(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                with mock.patch.object(Editor, "_ask_backup_label",
                                       return_value="Before Elite Four"):
                    app._do_backup()
                app.update()
                found = save_editor.list_backups(tmp)
                self.assertEqual(1, len(found))
                self.assertEqual("manual", found[0]["kind"])
                self.assertEqual("Before Elite Four", found[0]["label"])
                with open(found[0]["path"], "rb") as a, open(copy, "rb") as b:
                    self.assertEqual(b.read(), a.read())

    def test_cancelling_the_prompt_writes_nothing(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                with mock.patch.object(Editor, "_ask_backup_label", return_value=None):
                    app._do_backup()
                app.update()
                self.assertEqual([], save_editor.list_backups(tmp))

    def test_saving_repeatedly_prunes_automatic_backups_but_not_named_ones(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                with mock.patch.object(Editor, "_ask_backup_label", return_value="keep me"):
                    app._do_backup()
                for _ in range(save_editor.AUTO_BACKUP_LIMIT + 2):
                    app._do_save()
                    app.update()
                found = save_editor.list_backups(tmp)
                auto = [e for e in found if e["kind"] == "auto"]
                manual = [e for e in found if e["kind"] == "manual"]
                self.assertEqual(save_editor.AUTO_BACKUP_LIMIT, len(auto))
                self.assertEqual(["keep me"], [e["label"] for e in manual])

    def test_restoring_puts_the_bytes_back_and_keeps_the_backup(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                with open(copy, "rb") as fd:
                    original = fd.read()
                with mock.patch.object(Editor, "_ask_backup_label", return_value="checkpoint"):
                    app._do_backup()
                checkpoint = save_editor.list_backups(tmp)[0]

                app.var_money.set("12345")
                app._do_save()
                app.update()
                with open(copy, "rb") as fd:
                    self.assertNotEqual(original, fd.read())

                box.askyesno.return_value = True
                self.assertTrue(app._restore_backup(checkpoint))
                app.update()
                with open(copy, "rb") as fd:
                    self.assertEqual(original, fd.read(), "the save was not restored")
                self.assertTrue(os.path.isfile(checkpoint["path"]),
                                "restoring must copy, not consume, the backup")

    def test_the_save_being_replaced_is_backed_up_first(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                with mock.patch.object(Editor, "_ask_backup_label", return_value="checkpoint"):
                    app._do_backup()
                checkpoint = save_editor.list_backups(tmp)[0]
                app.var_money.set("4242")
                app._do_save()
                app.update()
                with open(copy, "rb") as fd:
                    about_to_be_replaced = fd.read()

                box.askyesno.return_value = True
                app._restore_backup(checkpoint)
                app.update()
                def contents(path):
                    with open(path, "rb") as fd:
                        return fd.read()

                rescued = [e for e in save_editor.list_backups(tmp)
                           if e["kind"] == "auto"
                           and contents(e["path"]) == about_to_be_replaced]
                self.assertTrue(rescued, "the replaced save was not preserved anywhere")

    def test_declining_the_confirmation_changes_nothing(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, copy = self._loaded(tmp)
                with mock.patch.object(Editor, "_ask_backup_label", return_value="checkpoint"):
                    app._do_backup()
                checkpoint = save_editor.list_backups(tmp)[0]
                app.var_money.set("777")
                app._do_save()
                app.update()
                with open(copy, "rb") as fd:
                    before = fd.read()

                box.askyesno.return_value = False
                self.assertFalse(app._restore_backup(checkpoint))
                with open(copy, "rb") as fd:
                    self.assertEqual(before, fd.read())

    def test_restoring_reloads_the_editor_from_the_restored_file(self):
        with mock.patch.object(save_editor, "messagebox") as box:
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                money = app.var_money.get()
                with mock.patch.object(Editor, "_ask_backup_label", return_value="checkpoint"):
                    app._do_backup()
                checkpoint = save_editor.list_backups(tmp)[0]
                app.var_money.set("31337")
                app._do_save()
                app.update()
                self.assertEqual("31337", app.var_money.get())

                box.askyesno.return_value = True
                app._restore_backup(checkpoint)
                app.update()
                self.assertEqual(money, app.var_money.get(),
                                 "the UI still shows the save it replaced")

    def test_the_restore_window_lists_every_backup(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                for label in ("one", "two"):
                    with mock.patch.object(Editor, "_ask_backup_label", return_value=label):
                        app._do_backup()
                app._do_save()
                app.update()
                expected = save_editor.list_backups(tmp)

                app._open_restore_dialog()
                app.update()
                win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
                self.addCleanup(win.destroy)
                widgets = []

                def walk(widget):
                    widgets.append(widget)
                    for child in widget.winfo_children():
                        walk(child)

                walk(win)
                tree = [w for w in widgets if isinstance(w, save_editor.ttk.Treeview)][0]
                rows = tree.get_children()
                self.assertEqual(len(expected), len(rows))
                # Newest first, and an unnamed backup reads as "Automatic".
                first = tree.item(rows[0], "values")
                self.assertEqual(expected[0]["label"] or "Automatic", first[0])
                self.assertEqual("Game.rxdata", first[1])

                restore = next(w for w in widgets
                               if isinstance(w, save_editor.ttk.Button)
                               and w.cget("text") == "Restore")
                self.assertEqual("disabled", str(restore.cget("state")))
                tree.selection_set(rows[0])
                app.update()
                self.assertEqual("normal", str(restore.cget("state")))

    def test_the_restore_window_says_so_when_there_is_nothing_to_restore(self):
        with mock.patch.object(save_editor, "messagebox"):
            with tempfile.TemporaryDirectory() as tmp:
                app, _copy = self._loaded(tmp)
                app._open_restore_dialog()
                app.update()
                win = [w for w in app.winfo_children() if isinstance(w, tk.Toplevel)][-1]
                self.addCleanup(win.destroy)
                widgets = []

                def walk(widget):
                    widgets.append(widget)
                    for child in widget.winfo_children():
                        walk(child)

                walk(win)
                self.assertEqual([], [w for w in widgets
                                      if isinstance(w, save_editor.ttk.Treeview)])
                text = " ".join(str(w.cget("text")) for w in widgets
                                if isinstance(w, save_editor.ttk.Label))
                self.assertIn("No backups yet", text)


class ToolbarIconTests(unittest.TestCase):
    """Every top-row button carries the item sprite it was assigned."""

    BUTTONS = (
        ("Load Save", save_editor.LOAD_SAVE_ITEM_ID, "TM117"),
        ("Save", save_editor.SAVE_ITEM_ID, "Magmarizer"),
        ("Backup Save File", save_editor.BACKUP_ITEM_ID, "EXP Share 2"),
        ("Restore Save File", save_editor.RESTORE_ITEM_ID, "Rare Bone"),
        ("Pokemon Build Library", save_editor.BUILD_LIBRARY_ITEM_ID, "Mysterious Scroll"),
    )

    def test_each_icon_id_is_the_item_it_claims_to_be(self):
        for text, item_id, name in self.BUTTONS:
            with self.subTest(button=text):
                self.assertEqual(name, ITEM_DATA.get(item_id, {}).get("name"))

    def test_the_save_button_no_longer_explains_itself(self):
        # The automatic backup is unchanged; only the label lost "(auto-backup)".
        try:
            app = Editor()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update()
        labels = {str(w.cget("text")) for w in self._walk(app)
                  if isinstance(w, save_editor.ttk.Button)}
        self.assertIn("Save", labels)
        self.assertNotIn("Save (auto-backup)", labels)

    def test_every_toolbar_button_shows_its_icon_beside_the_text(self):
        try:
            app = Editor()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        self.addCleanup(app.destroy)
        app.withdraw()
        app.update()
        if not os.path.isdir(save_editor.resource_path(
                os.path.join("game_resources", "Graphics", "Icons"))):
            self.skipTest("item icons not extracted")
        found = {str(w.cget("text")): w for w in self._walk(app)
                 if isinstance(w, save_editor.ttk.Button)}
        for text, _item_id, _name in self.BUTTONS:
            with self.subTest(button=text):
                button = found.get(text)
                self.assertIsNotNone(button, f"no {text} button")
                self.assertTrue(str(button.cget("image")))
                self.assertEqual("left", str(button.cget("compound")))

    @staticmethod
    def _walk(root):
        found = []

        def walk(widget):
            found.append(widget)
            for child in widget.winfo_children():
                walk(child)

        walk(root)
        return found

if __name__ == "__main__":
    unittest.main()
