import unittest
import tkinter as tk

from save_editor import (
    Editor,
    NATURES,
    _sanitize_evs,
    ability_choices_for_species,
    ability_slot_from_value,
    apply_pokemon_identity,
    gender_choices_for_species,
    pokemon_gender,
    pokemon_is_shiny,
    pokemon_nature,
)


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


if __name__ == "__main__":
    unittest.main()
