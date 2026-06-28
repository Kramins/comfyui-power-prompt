"""
Unit tests for PowerPromptNode.

Run with: pytest tests/ -v
"""

import json
import pathlib
import pytest

from nodes.power_prompt import PowerPromptNode
from nodes.power_prompt_partial import PowerPromptPartial
from nodes.power_prompt_file_partial import PowerPromptFilePartial
from nodes.utils import (
    _evaluate_when,
    _merge_include_variables,
    _merge_include_fragments,
    _strip_prompt_comments,
    _merge_tags,
    _normalize_prompt,
    _parse_count,
    _weighted_sample,
)

import random as _random


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate(yaml_input: str, var_state: dict | None = None, seed: int = 0):
    """Convenience wrapper that accepts a dict for var_state."""
    node = PowerPromptNode()
    return node.generate(
        yaml_input=yaml_input,
        var_state=json.dumps(var_state or {}),
        seed=seed,
    )


def make_yaml(variables: str, prompt: str = "{{ x }}") -> str:
    return f"variables:\n{variables}\nprompt: |\n  {prompt}\n"


# ---------------------------------------------------------------------------
# _parse_count
# ---------------------------------------------------------------------------


class TestParseCount:
    def test_integer_one(self):
        assert _parse_count(1, 10) == (1, 1)

    def test_integer_three(self):
        assert _parse_count(3, 10) == (3, 3)

    def test_string_integer(self):
        assert _parse_count("2", 10) == (2, 2)

    def test_range_string(self):
        assert _parse_count("1-3", 10) == (1, 3)

    def test_range_clamps_to_option_count(self):
        assert _parse_count("1-20", 5) == (1, 5)

    def test_none_is_any(self):
        assert _parse_count(None, 7) == (0, 7)

    def test_string_any(self):
        assert _parse_count("any", 7) == (0, 7)

    def test_invalid_falls_back_to_any(self):
        assert _parse_count("bogus", 4) == (0, 4)


# ---------------------------------------------------------------------------
# _weighted_sample
# ---------------------------------------------------------------------------


class TestWeightedSample:
    def _rng(self, seed=42):
        return _random.Random(seed)

    def test_correct_count(self):
        result = _weighted_sample(["a", "b", "c", "d"], [1, 1, 1, 1], 2, self._rng())
        assert len(result) == 2

    def test_no_duplicates(self):
        result = _weighted_sample(list("abcdefgh"), [1] * 8, 5, self._rng())
        assert len(result) == len(set(result))

    def test_k_larger_than_pool_returns_all(self):
        items = ["x", "y"]
        result = _weighted_sample(items, [1, 1], 10, self._rng())
        assert set(result) == {"x", "y"}
        assert len(result) == 2

    def test_k_zero_returns_empty(self):
        assert _weighted_sample(["a", "b"], [1, 1], 0, self._rng()) == []

    def test_weight_zero_item_excluded(self):
        # "b" has weight 0, so it should never be picked
        results = set()
        for seed in range(200):
            r = _weighted_sample(["a", "b", "c"], [1, 0, 1], 1, _random.Random(seed))
            results.update(r)
        assert "b" not in results

    def test_heavy_weight_item_picked_more_often(self):
        counts = {"a": 0, "b": 0}
        for seed in range(500):
            [item] = _weighted_sample(["a", "b"], [10, 1], 1, _random.Random(seed))
            counts[item] += 1
        # "a" should win the vast majority of the time
        assert counts["a"] > counts["b"] * 5

    def test_result_items_are_from_options(self):
        options = ["red", "green", "blue"]
        result = _weighted_sample(options, [1, 1, 1], 3, self._rng())
        assert all(r in options for r in result)


# ---------------------------------------------------------------------------
# _normalize_prompt
# ---------------------------------------------------------------------------


class TestNormalizePrompt:
    def test_removes_newlines(self):
        assert "\n" not in _normalize_prompt("hello\nworld")

    def test_collapses_spaces(self):
        assert "  " not in _normalize_prompt("hello   world")

    def test_removes_consecutive_commas(self):
        result = _normalize_prompt("a,,b")
        assert ",," not in result

    def test_removes_empty_value_comma(self):
        result = _normalize_prompt("a, , b")
        assert result == "a, b"

    def test_strips_leading_trailing_commas(self):
        result = _normalize_prompt(", hello, world,")
        assert not result.startswith(",")
        assert not result.endswith(",")

    def test_single_space_after_comma(self):
        result = _normalize_prompt("a,b,c")
        assert result == "a, b, c"

    def test_multiline_prompt_flattened(self):
        prompt = "1girl,\nhappy,\nblonde hair,\nmasterpiece"
        result = _normalize_prompt(prompt)
        assert result == "1girl, happy, blonde hair, masterpiece"

    def test_empty_tag_removed(self):
        result = _normalize_prompt("1girl,\n,\nmasterpiece")
        assert result == "1girl, masterpiece"

    def test_already_clean_is_unchanged(self):
        clean = "1girl, happy, masterpiece"
        assert _normalize_prompt(clean) == clean


# ---------------------------------------------------------------------------
# generate — type: select, count: 1  (single pick)
# ---------------------------------------------------------------------------


SINGLE_YAML = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy
      - sad
      - angry
prompt: |
  {{ mood }}
"""


class TestSelectSinglePick:
    def test_returns_tuple_of_two_strings(self):
        result = generate(SINGLE_YAML)
        assert isinstance(result, tuple) and len(result) == 2
        assert all(isinstance(s, str) for s in result)

    def test_random_result_is_valid_option(self):
        prompt, _ = generate(SINGLE_YAML, seed=0)
        assert prompt in ("happy", "sad", "angry")

    def test_seed_is_deterministic(self):
        a, _ = generate(SINGLE_YAML, seed=7)
        b, _ = generate(SINGLE_YAML, seed=7)
        assert a == b

    def test_different_seeds_can_produce_different_results(self):
        results = {generate(SINGLE_YAML, seed=s)[0] for s in range(30)}
        assert len(results) > 1

    def test_user_override_respected(self):
        prompt, _ = generate(SINGLE_YAML, {"mood": "sad"})
        assert prompt == "sad"

    def test_user_override_random_string_uses_seed(self):
        prompt, _ = generate(SINGLE_YAML, {"mood": "random"})
        assert prompt in ("happy", "sad", "angry")

    def test_user_override_invalid_option_still_passes_through(self):
        # Python doesn't validate user-provided option values
        prompt, _ = generate(SINGLE_YAML, {"mood": "ecstatic"})
        assert prompt == "ecstatic"

    def test_count_defaults_to_one_when_missing(self):
        yaml = """\
variables:
  x:
    type: select
    options:
      - a
      - b
      - c
prompt: |
  {{ x }}
"""
        for seed in range(20):
            prompt, _ = generate(yaml, seed=seed)
            assert prompt in ("a", "b", "c")

    def test_missing_options_raises(self):
        yaml = make_yaml("  x:\n    type: select\n    count: 1\n    options: []\n")
        with pytest.raises(ValueError, match="no options"):
            generate(yaml)


# ---------------------------------------------------------------------------
# generate — type: select, count: any  (manual multi-pick)
# ---------------------------------------------------------------------------


ANY_YAML = """\
variables:
  tags:
    type: select
    count: any
    options:
      - smile
      - blush
      - wind
prompt: |
  {{ tags }}
"""


class TestSelectAny:
    def test_empty_selection_renders_empty_string(self):
        prompt, _ = generate(ANY_YAML, {"tags": []})
        assert prompt == ""

    def test_absent_key_also_empty(self):
        prompt, _ = generate(ANY_YAML, {})
        assert prompt == ""

    def test_single_selection(self):
        prompt, _ = generate(ANY_YAML, {"tags": ["smile"]})
        assert prompt == "smile"

    def test_multiple_selections_comma_joined(self):
        prompt, _ = generate(ANY_YAML, {"tags": ["smile", "blush"]})
        assert prompt == "smile, blush"

    def test_order_matches_user_selection(self):
        prompt, _ = generate(ANY_YAML, {"tags": ["wind", "smile"]})
        assert prompt == "wind, smile"

    def test_seed_has_no_effect_on_any(self):
        # count:any is fully manual — seed must not change the result
        a, _ = generate(ANY_YAML, {"tags": ["blush"]}, seed=0)
        b, _ = generate(ANY_YAML, {"tags": ["blush"]}, seed=999)
        assert a == b


# ---------------------------------------------------------------------------
# generate — type: select, count: N  (fixed multi-pick, seed-driven)
# ---------------------------------------------------------------------------


FIXED_YAML = """\
variables:
  style:
    type: select
    count: 2
    options:
      - anime
      - watercolor
      - oil painting
      - sketch
prompt: |
  {{ style }}
"""


class TestSelectFixedCount:
    def test_random_pick_produces_exactly_n_items(self):
        prompt, _ = generate(FIXED_YAML, seed=0)
        parts = [p.strip() for p in prompt.split(",")]
        assert len(parts) == 2

    def test_random_items_are_from_options(self):
        options = {"anime", "watercolor", "oil painting", "sketch"}
        for seed in range(20):
            prompt, _ = generate(FIXED_YAML, seed=seed)
            for part in prompt.split(","):
                assert part.strip() in options

    def test_no_duplicate_random_picks(self):
        for seed in range(50):
            prompt, _ = generate(FIXED_YAML, seed=seed)
            parts = [p.strip() for p in prompt.split(",")]
            assert len(parts) == len(set(parts))

    def test_user_override_used_when_present(self):
        prompt, _ = generate(FIXED_YAML, {"style": ["anime", "sketch"]})
        assert "anime" in prompt and "sketch" in prompt

    def test_empty_user_list_falls_back_to_seed(self):
        prompt, _ = generate(FIXED_YAML, {"style": []}, seed=5)
        parts = [p.strip() for p in prompt.split(",")]
        assert len(parts) == 2

    def test_seed_is_deterministic(self):
        a, _ = generate(FIXED_YAML, seed=42)
        b, _ = generate(FIXED_YAML, seed=42)
        assert a == b


# ---------------------------------------------------------------------------
# generate — type: select, count: M-N  (range pick)
# ---------------------------------------------------------------------------


RANGE_YAML = """\
variables:
  effects:
    type: select
    count: 1-3
    options:
      - fire
      - water
      - earth
      - air
      - lightning
prompt: |
  {{ effects }}
"""


class TestSelectRange:
    def test_random_pick_within_range(self):
        options = {"fire", "water", "earth", "air", "lightning"}
        counts = set()
        for seed in range(100):
            prompt, _ = generate(RANGE_YAML, seed=seed)
            parts = [p.strip() for p in prompt.split(",")]
            counts.add(len(parts))
            assert all(p in options for p in parts)
        # Should have seen different counts within 1-3
        assert counts <= {1, 2, 3}
        assert len(counts) > 1

    def test_range_count_never_zero_when_min_is_one(self):
        for seed in range(50):
            prompt, _ = generate(RANGE_YAML, seed=seed)
            assert prompt.strip() != ""

    def test_user_override_bypasses_range(self):
        # User can pick any number; range only applies to random
        prompt, _ = generate(RANGE_YAML, {"effects": ["fire", "water", "earth", "air"]})
        parts = [p.strip() for p in prompt.split(",")]
        assert len(parts) == 4


# ---------------------------------------------------------------------------
# generate — type: select, weighted options
# ---------------------------------------------------------------------------


WEIGHTED_YAML = """\
variables:
  color:
    type: select
    count: 1
    options:
      - value: red
        weight: 100
      - value: blue
        weight: 1
prompt: |
  {{ color }}
"""


class TestWeightedOptions:
    def test_heavy_option_dominates(self):
        counts = {"red": 0, "blue": 0}
        for seed in range(200):
            prompt, _ = generate(WEIGHTED_YAML, seed=seed)
            counts[prompt] += 1
        assert counts["red"] > counts["blue"] * 10


# ---------------------------------------------------------------------------
# generate — type: text
# ---------------------------------------------------------------------------


TEXT_YAML = """\
variables:
  clothing:
    type: text
prompt: |
  wearing {{ clothing }}
"""


class TestTextType:
    def test_user_value_passed_through(self):
        prompt, _ = generate(TEXT_YAML, {"clothing": "a red dress"})
        assert "a red dress" in prompt

    def test_missing_value_is_empty_string(self):
        prompt, _ = generate(TEXT_YAML, {})
        assert prompt == "wearing"

    def test_numeric_value_stringified(self):
        # var_state JSON could theoretically send a number
        node = PowerPromptNode()
        prompt, _ = node.generate(TEXT_YAML, json.dumps({"clothing": 42}), seed=0)
        assert "42" in prompt


# ---------------------------------------------------------------------------
# generate — backward compatibility (legacy types)
# ---------------------------------------------------------------------------


class TestLegacyTypes:
    def test_choice_acts_as_count_one(self):
        yaml = """\
variables:
  x:
    type: choice
    options:
      - a
      - b
      - c
prompt: |
  {{ x }}
"""
        prompt, _ = generate(yaml)
        assert prompt in ("a", "b", "c")

    def test_choice_user_override(self):
        yaml = """\
variables:
  x:
    type: choice
    options:
      - a
      - b
prompt: |
  {{ x }}
"""
        prompt, _ = generate(yaml, {"x": "b"})
        assert prompt == "b"

    def test_multiselect_acts_as_count_any(self):
        yaml = """\
variables:
  x:
    type: multiselect
    options:
      - p
      - q
      - r
prompt: |
  {{ x }}
"""
        # empty = empty string (not random)
        prompt, _ = generate(yaml, {})
        assert prompt == ""

        prompt, _ = generate(yaml, {"x": ["p", "r"]})
        assert prompt == "p, r"


# ---------------------------------------------------------------------------
# generate — Jinja2 template
# ---------------------------------------------------------------------------


class TestJinjaTemplate:
    def test_undefined_variable_raises(self):
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options: [a]
prompt: |
  {{ x }} {{ undefined_var }}
"""
        with pytest.raises(ValueError, match="undefined variable"):
            generate(yaml)

    def test_invalid_template_syntax_raises(self):
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options: [a]
prompt: |
  {{ x } broken
"""
        with pytest.raises(ValueError, match="[Ii]nvalid Jinja"):
            generate(yaml)

    def test_template_uses_all_variables(self):
        yaml = """\
variables:
  a:
    type: select
    count: 1
    options: [hello]
  b:
    type: text
prompt: |
  {{ a }} {{ b }}
"""
        prompt, _ = generate(yaml, {"a": "hello", "b": "world"})
        assert prompt == "hello world"


# ---------------------------------------------------------------------------
# generate — YAML validation errors
# ---------------------------------------------------------------------------


class TestYAMLErrors:
    def test_bad_yaml_raises(self):
        with pytest.raises(ValueError, match="[Ii]nvalid YAML"):
            generate("variables: [\nbad")

    def test_yaml_not_mapping_raises(self):
        with pytest.raises(ValueError, match="mapping"):
            generate("- a\n- b\n")

    def test_missing_prompt_raises(self):
        yaml = "variables:\n  x:\n    type: text\n"
        with pytest.raises(ValueError, match="prompt"):
            generate(yaml)

    def test_unknown_type_raises(self):
        yaml = """\
variables:
  x:
    type: unknown_type
    options: [a]
prompt: |
  {{ x }}
"""
        with pytest.raises(ValueError, match="Unknown variable type"):
            generate(yaml)

    def test_non_mapping_variable_def_raises(self):
        yaml = """\
variables:
  x: not_a_mapping
prompt: |
  {{ x }}
"""
        with pytest.raises(ValueError, match="mapping"):
            generate(yaml)


# ---------------------------------------------------------------------------
# generate — normalized output
# ---------------------------------------------------------------------------


class TestNormalizedOutput:
    def test_second_output_is_normalized(self):
        yaml = """\
variables:
  a:
    type: select
    count: 1
    options: [hello]
  b:
    type: select
    count: any
    options: [x]
prompt: |
  {{ a }},
  {{ b }},
  world
"""
        norm, _ = generate(yaml, {"a": "hello", "b": []})
        assert "\n" not in norm
        assert ",," not in norm
        assert not norm.startswith(",")
        assert not norm.endswith(",")

    def test_both_outputs_populated(self):
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options: [hi]
prompt: |
  {{ x }}
"""
        norm, raw = generate(yaml, {"x": "hi"})
        assert norm == "hi"
        assert raw == "hi"

    def test_normalized_removes_empty_tag_lines(self):
        yaml = """\
variables:
  tags:
    type: select
    count: any
    options: [smile]
prompt: |
  1girl,
  {{ tags }},
  masterpiece
"""
        norm, _ = generate(yaml, {"tags": []})
        assert norm == "1girl, masterpiece"


# ---------------------------------------------------------------------------
# generate — seed independence across variables
# ---------------------------------------------------------------------------


class TestSeedIndependence:
    def test_each_variable_independently_seeded(self):
        """Adding a new variable must not change existing variables' random picks."""
        base_yaml = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy
      - sad
      - angry
prompt: |
  {{ mood }}
"""
        extended_yaml = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy
      - sad
      - angry
  hair:
    type: select
    count: 1
    options:
      - blonde
      - black
prompt: |
  {{ mood }}, {{ hair }}
"""
        for seed in range(20):
            base_mood, _ = generate(base_yaml, seed=seed)
            ext_prompt, _ = generate(extended_yaml, seed=seed)
            ext_mood = ext_prompt.split(",")[0].strip()
            assert base_mood == ext_mood, (
                f"seed={seed}: mood changed when hair was added ({base_mood!r} vs {ext_mood!r})"
            )


# ---------------------------------------------------------------------------
# _evaluate_when
# ---------------------------------------------------------------------------


class TestEvaluateWhen:
    def test_empty_expr_returns_true(self):
        assert _evaluate_when("", {}) is True

    def test_none_expr_returns_true(self):
        assert _evaluate_when(None, {}) is True

    def test_true_literal(self):
        assert _evaluate_when("True", {}) is True

    def test_false_literal(self):
        assert _evaluate_when("False", {}) is False

    def test_equality_match(self):
        assert _evaluate_when("style == 'anime'", {"style": "anime"}) is True

    def test_equality_no_match(self):
        assert _evaluate_when("style == 'anime'", {"style": "watercolor"}) is False

    def test_in_list_literal(self):
        assert _evaluate_when("style in ['anime', 'watercolor']", {"style": "anime"}) is True

    def test_not_in_list_literal(self):
        assert _evaluate_when("style in ['anime', 'watercolor']", {"style": "sketch"}) is False

    def test_item_in_list_context(self):
        # multi-pick variable stored as list
        assert _evaluate_when("'anime' in style", {"style": ["anime", "watercolor"]}) is True

    def test_item_not_in_list_context(self):
        assert _evaluate_when("'anime' in style", {"style": ["watercolor"]}) is False

    def test_and_both_true(self):
        ctx = {"style": "anime", "mood": "happy"}
        assert _evaluate_when("style == 'anime' and mood == 'happy'", ctx) is True

    def test_and_one_false(self):
        ctx = {"style": "anime", "mood": "happy"}
        assert _evaluate_when("style == 'anime' and mood == 'sad'", ctx) is False

    def test_or_first_true(self):
        assert _evaluate_when("style == 'anime' or style == 'sketch'", {"style": "anime"}) is True

    def test_or_second_true(self):
        assert _evaluate_when("style == 'anime' or style == 'sketch'", {"style": "sketch"}) is True

    def test_or_both_false(self):
        assert _evaluate_when("style == 'anime' or style == 'sketch'", {"style": "watercolor"}) is False

    def test_not_equal(self):
        assert _evaluate_when("style != 'oil painting'", {"style": "anime"}) is True
        assert _evaluate_when("style != 'oil painting'", {"style": "oil painting"}) is False

    def test_undefined_variable_raises(self):
        with pytest.raises(ValueError):
            _evaluate_when("undefined_var == 'x'", {})

    def test_syntax_error_raises(self):
        with pytest.raises(ValueError):
            _evaluate_when("this is !!!! not valid python", {})

    def test_safe_builtins_available(self):
        assert _evaluate_when("len(tags) > 1", {"tags": ["a", "b"]}) is True
        # Jinja2 does not support generator expressions — use list membership instead
        assert _evaluate_when("'smile' in tags", {"tags": ["smile", "blush"]}) is True
        assert _evaluate_when("min([3, 1, 2]) == 1", {}) is True

    def test_complex_expression(self):
        ctx = {"style": ["anime", "watercolor"]}
        assert _evaluate_when("'anime' in style or 'digital art' in style", ctx) is True
        assert _evaluate_when("'sketch' in style and 'watercolor' in style", ctx) is False


# ---------------------------------------------------------------------------
# generate — when filtering
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# generate — multi-value options (value: [a, b, ...])
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# generate — when expression errors
# ---------------------------------------------------------------------------


class TestWhenErrors:
    def test_syntax_error_in_when_raises(self):
        yaml = """\
variables:
  x:
    type: select
    options:
      - value: a
        when: "this is !!!! invalid"
prompt: |
  {{ x }}
"""
        with pytest.raises(ValueError, match="when"):
            generate(yaml)

    def test_undefined_variable_in_when_raises(self):
        yaml = """\
variables:
  x:
    type: select
    options:
      - value: a
        when: "nonexistent == 'something'"
prompt: |
  {{ x }}
"""
        with pytest.raises(ValueError, match="when"):
            generate(yaml)

    def test_error_message_names_the_option_and_variable(self):
        yaml = """\
variables:
  mood:
    type: select
    options:
      - value: happy
        when: "BOGUS *** EXPR"
prompt: |
  {{ mood }}
"""
        with pytest.raises(ValueError) as exc_info:
            generate(yaml)
        msg = str(exc_info.value)
        assert "happy" in msg
        assert "mood" in msg

    def test_out_of_order_dependency_raises(self):
        # artist declared before style — 'style' not in eval_context yet → NameError
        yaml = """\
variables:
  artist:
    type: select
    options:
      - value: Makoto Shinkai
        when: "'anime' in style"
  style:
    type: select
    options:
      - anime
      - watercolor
prompt: |
  {{ style }}, by {{ artist }}
"""
        with pytest.raises(ValueError, match="when"):
            generate(yaml)


MULTI_VALUE_YAML = """\
variables:
  style:
    type: select
    count: 1
    options:
      - anime
      - watercolor

  artist:
    type: select
    count: 1
    options:
      - value:
          - Makoto Shinkai
          - Ilya Kuvshinov
        when: "style == 'anime'"
      - value:
          - Monet
          - Turner
        when: "style == 'watercolor'"
prompt: |
  {{ style }}, by {{ artist }}
"""


class TestMultiValueOptions:
    def test_all_values_in_group_are_reachable(self):
        anime_artists = set()
        for seed in range(100):
            prompt, _ = generate(MULTI_VALUE_YAML, {"style": "anime"}, seed=seed)
            for name in ["Makoto Shinkai", "Ilya Kuvshinov"]:
                if name in prompt:
                    anime_artists.add(name)
        assert anime_artists == {"Makoto Shinkai", "Ilya Kuvshinov"}

    def test_when_still_filters_grouped_values(self):
        for seed in range(20):
            prompt, _ = generate(MULTI_VALUE_YAML, {"style": "watercolor"}, seed=seed)
            assert "Makoto Shinkai" not in prompt
            assert "Ilya Kuvshinov" not in prompt

    def test_multi_value_and_single_value_coexist(self):
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options:
      - value:
          - a
          - b
      - value: c
prompt: |
  {{ x }}
"""
        results = {generate(yaml, seed=s)[0] for s in range(60)}
        assert results == {"a", "b", "c"}

    def test_multi_value_shares_weight(self):
        # Group of 2 with weight=10 vs single with weight=1 — group items dominate
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options:
      - value:
          - heavy1
          - heavy2
        weight: 10
      - value: light
        weight: 1
prompt: |
  {{ x }}
"""
        counts = {"heavy1": 0, "heavy2": 0, "light": 0}
        for seed in range(300):
            prompt, _ = generate(yaml, seed=seed)
            counts[prompt] += 1
        assert counts["heavy1"] + counts["heavy2"] > counts["light"] * 5

    def test_mixed_single_and_multi_value_with_no_when(self):
        yaml = """\
variables:
  x:
    type: select
    count: 1
    options:
      - plain string
      - value: single dict
      - value:
          - multi a
          - multi b
prompt: |
  {{ x }}
"""
        results = {generate(yaml, seed=s)[0] for s in range(100)}
        assert results == {"plain string", "single dict", "multi a", "multi b"}


WHEN_YAML = """\
variables:
  style:
    type: select
    count: 1
    options:
      - anime
      - watercolor

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "style == 'anime'"
      - value: Monet
        when: "style == 'watercolor'"
prompt: |
  {{ style }}, by {{ artist }}
"""


class TestWhenFiltering:
    def test_when_narrows_random_pool_anime(self):
        for seed in range(20):
            prompt, _ = generate(WHEN_YAML, {"style": "anime"}, seed=seed)
            assert "Makoto Shinkai" in prompt

    def test_when_narrows_random_pool_watercolor(self):
        for seed in range(20):
            prompt, _ = generate(WHEN_YAML, {"style": "watercolor"}, seed=seed)
            assert "Monet" in prompt

    def test_user_selected_artist_bypasses_when(self):
        # User picks Makoto Shinkai even though style=watercolor — passes through unchecked.
        prompt, _ = generate(WHEN_YAML, {"style": "watercolor", "artist": "Makoto Shinkai"})
        assert "Makoto Shinkai" in prompt

    def test_all_filtered_produces_empty_variable(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1
    options:
      - sketch

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "style == 'anime'"
      - value: Monet
        when: "style == 'watercolor'"
prompt: |
  {{ artist }}
"""
        # style=sketch matches no artist when — variable is empty, no crash.
        prompt, _ = generate(yaml, {"style": "sketch"}, seed=0)
        assert prompt == ""

    def test_option_without_when_always_included(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1
    options:
      - watercolor

  artist:
    type: select
    count: 1
    options:
      - value: Universal Artist
      - value: Makoto Shinkai
        when: "style == 'anime'"
prompt: |
  {{ artist }}
"""
        # Only Universal Artist passes when style=watercolor
        for seed in range(20):
            prompt, _ = generate(yaml, seed=seed)
            assert prompt == "Universal Artist"

    def test_when_uses_list_eval_context_for_multi_pick(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1-3
    options:
      - anime
      - watercolor
      - sketch

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "'anime' in style"
      - value: Monet
        when: "'watercolor' in style"
prompt: |
  {{ artist }}
"""
        # style is a list in eval_context; membership test should work.
        prompt, _ = generate(yaml, {"style": ["anime", "sketch"]}, seed=0)
        assert "Makoto Shinkai" in prompt

    def test_when_seed_independence_preserved(self):
        """Adding a when-filtered variable must not shift unrelated variables' picks."""
        base_yaml = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy
      - sad
      - angry
prompt: |
  {{ mood }}
"""
        extended_yaml = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy
      - sad
      - angry
  style:
    type: select
    count: 1
    options:
      - anime
      - watercolor
  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "style == 'anime'"
      - value: Monet
        when: "style == 'watercolor'"
prompt: |
  {{ mood }}, {{ style }}, by {{ artist }}
"""
        for seed in range(20):
            base_mood, _ = generate(base_yaml, seed=seed)
            ext_prompt, _ = generate(extended_yaml, seed=seed)
            ext_mood = ext_prompt.split(",")[0].strip()
            assert base_mood == ext_mood


# ---------------------------------------------------------------------------
# _merge_tags
# ---------------------------------------------------------------------------


class TestMergeTags:
    def test_single_value(self):
        by_val = {"anime": ["japanese", "illustration"]}
        assert _merge_tags(["anime"], by_val) == ["japanese", "illustration"]

    def test_union_deduplicates(self):
        by_val = {"anime": ["japanese", "illustration"], "watercolor": ["traditional", "illustration"]}
        assert _merge_tags(["anime", "watercolor"], by_val) == ["japanese", "illustration", "traditional"]

    def test_empty_list(self):
        assert _merge_tags([], {}) == []

    def test_missing_value_ignored(self):
        assert _merge_tags(["unknown"], {}) == []


# ---------------------------------------------------------------------------
# generate — option tags
# ---------------------------------------------------------------------------


_TAGS_YAML = """\
variables:
  style:
    type: select
    count: 1
    options:
      - value: anime
        tags: [japanese, illustration]
      - value: watercolor
        tags: [traditional, painterly]

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "'japanese' in style_tags"
      - value: Monet
        when: "'traditional' in style_tags"
prompt: |
  {{ style }}, by {{ artist }}
"""


class TestOptionTags:
    def test_tags_filter_single_pick_anime(self):
        for seed in range(20):
            prompt, _ = generate(_TAGS_YAML, {"style": "anime"}, seed=seed)
            assert "Makoto Shinkai" in prompt

    def test_tags_filter_single_pick_watercolor(self):
        for seed in range(20):
            prompt, _ = generate(_TAGS_YAML, {"style": "watercolor"}, seed=seed)
            assert "Monet" in prompt

    def test_tags_multi_pick_union(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1-2
    options:
      - value: anime
        tags: [japanese, illustration]
      - value: watercolor
        tags: [traditional, painterly]

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "'japanese' in style_tags"
      - value: Monet
        when: "'traditional' in style_tags"
prompt: |
  {{ artist }}
"""
        # Both styles selected → tags merged → both artists available across seeds
        results = {generate(yaml, {"style": ["anime", "watercolor"]}, seed=s)[0] for s in range(50)}
        assert "Makoto Shinkai" in results
        assert "Monet" in results

    def test_missing_tags_defaults_to_empty(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1
    options:
      - value: anime
      - value: watercolor
        tags: [traditional]

  artist:
    type: select
    count: 1
    options:
      - value: Monet
        when: "'traditional' in style_tags"
      - value: Generic
prompt: |
  {{ artist }}
"""
        # anime has no tags → style_tags=[] → Monet excluded → only Generic
        for seed in range(20):
            prompt, _ = generate(yaml, {"style": "anime"}, seed=seed)
            assert prompt == "Generic"

    def test_scalar_tags_normalized_to_list(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1
    options:
      - value: anime
        tags: japanese

  artist:
    type: select
    count: 1
    options:
      - value: Makoto Shinkai
        when: "'japanese' in style_tags"
prompt: |
  {{ artist }}
"""
        for seed in range(20):
            prompt, _ = generate(yaml, {"style": "anime"}, seed=seed)
            assert prompt == "Makoto Shinkai"

    def test_multi_value_options_share_tags(self):
        yaml = """\
variables:
  style:
    type: select
    count: 1
    options:
      - value:
          - anime
          - manga
        tags: [japanese, illustration]

  note:
    type: select
    count: 1
    options:
      - value: ok
        when: "'japanese' in style_tags"
      - value: fail
        when: "'japanese' not in style_tags"
prompt: |
  {{ style }}, {{ note }}
"""
        # Both anime and manga share the same tags — both yield "ok"
        for seed in range(20):
            for style_val in ("anime", "manga"):
                prompt, _ = generate(yaml, {"style": style_val}, seed=seed)
                assert ", ok" in prompt, f"style={style_val}, seed={seed}: {prompt}"


# ---------------------------------------------------------------------------
# _strip_prompt_comments
# ---------------------------------------------------------------------------


class TestStripPromptComments:
    def test_full_line_comment_removed(self):
        assert _strip_prompt_comments("# comment\nhello") == "hello"

    def test_indented_comment_removed(self):
        assert _strip_prompt_comments("  # indented\nhello") == "hello"

    def test_inline_hash_preserved(self):
        assert _strip_prompt_comments("hello,  # note") == "hello,  # note"

    def test_empty_string(self):
        assert _strip_prompt_comments("") == ""

    def test_multiple_comments_removed(self):
        result = _strip_prompt_comments("# a\n# b\nhello\n# c")
        assert result == "hello"

    def test_no_comments_unchanged(self):
        assert _strip_prompt_comments("hello\nworld") == "hello\nworld"


# ---------------------------------------------------------------------------
# generate — prompt comments
# ---------------------------------------------------------------------------


class TestPromptComments:
    def _yaml(self, prompt_block):
        return f"""\
variables:
  x:
    type: select
    count: 1
    options:
      - hello
prompt: |
{prompt_block}
"""

    def test_full_line_comment_not_in_output(self):
        yaml = self._yaml("  # section header\n  {{ x }}")
        prompt, _ = generate(yaml, {"x": "hello"}, seed=0)
        assert "#" not in prompt
        assert "hello" in prompt

    def test_indented_comment_not_in_output(self):
        yaml = self._yaml("  # indented comment\n  {{ x }}")
        prompt, _ = generate(yaml, {"x": "hello"}, seed=0)
        assert "#" not in prompt

    def test_inline_hash_preserved_in_output(self):
        yaml = self._yaml("  {{ x }},  # note")
        prompt, _ = generate(yaml, {"x": "hello"}, seed=0)
        assert "# note" in prompt

    def test_multiple_comment_lines_stripped(self):
        yaml = self._yaml("  # line 1\n  # line 2\n  {{ x }}\n  # line 3")
        prompt, _ = generate(yaml, {"x": "hello"}, seed=0)
        assert "#" not in prompt
        assert "hello" in prompt

    def test_section_headers_example(self):
        yaml = """\
variables:
  character:
    type: select
    count: 1
    options:
      - shrine maiden
  setting:
    type: select
    count: 1
    options:
      - riverside
prompt: |
  # ── Character ───────────────
  1girl, {{ character }},

  # ── Scene ───────────────────
  {{ setting }},

  # Quality
  masterpiece
"""
        prompt, _ = generate(yaml, {"character": "shrine maiden", "setting": "riverside"}, seed=0)
        assert "#" not in prompt
        assert "shrine maiden" in prompt
        assert "riverside" in prompt
        assert "masterpiece" in prompt


class TestMergeIncludeVariables:
    HAIR_PARTIAL = """\
variables:
  hair_color:
    type: select
    count: 1
    options:
      - black
      - blonde
      - silver
"""
    STYLE_PARTIAL = """\
variables:
  art_style:
    type: select
    count: 1
    options:
      - anime
      - watercolor
"""

    def test_empty_list_returns_empty(self):
        assert _merge_include_variables([]) == {}

    def test_none_entries_ignored(self):
        assert _merge_include_variables([None, "", "  "]) == {}

    def test_single_include(self):
        result = _merge_include_variables([self.HAIR_PARTIAL])
        assert "hair_color" in result
        assert result["hair_color"]["type"] == "select"

    def test_two_includes_merge(self):
        result = _merge_include_variables([self.HAIR_PARTIAL, self.STYLE_PARTIAL])
        assert "hair_color" in result
        assert "art_style" in result

    def test_later_include_overrides_earlier(self):
        override = """\
variables:
  hair_color:
    type: select
    count: 1
    options:
      - red
      - blue
"""
        result = _merge_include_variables([self.HAIR_PARTIAL, override])
        options = [o if isinstance(o, str) else o.get("value", o)
                   for o in result["hair_color"]["options"]]
        assert "red" in options
        assert "black" not in options

    def test_invalid_yaml_silently_skipped(self):
        result = _merge_include_variables([":::invalid:::", self.STYLE_PARTIAL])
        assert "art_style" in result

    def test_main_variables_override_includes(self):
        main_yaml = """\
variables:
  hair_color:
    type: select
    count: 1
    options:
      - pink
prompt: |
  {{ hair_color }}
"""
        inc = _merge_include_variables([self.HAIR_PARTIAL])
        inc.update({"hair_color": {"type": "select", "count": 1, "options": ["pink"]}})
        # pink should win
        options = inc["hair_color"]["options"]
        assert options == ["pink"]


class TestUnless:
    """Tests for the `unless:` field — the inverse of `when:`."""

    def _make_yaml(self, options_yaml: str, seed: int = 0) -> str:
        return f"""\
variables:
  season:
    type: select
    count: 1
    options:
      - winter
      - summer

  item:
    type: select
    count: 1
    options:
{options_yaml}

prompt: |
  {{{{ season }}}}, {{{{ item }}}}
"""

    def test_unless_excludes_when_true(self):
        """Option excluded when unless condition is true."""
        yaml_text = self._make_yaml("""\
      - value: warm coat
        unless: "season == 'summer'"
      - value: t-shirt
""")
        # With season fixed to summer, warm coat should be excluded
        prompt, _ = generate(yaml_text, {"season": "summer"}, seed=0)
        assert "t-shirt" in prompt
        assert "warm coat" not in prompt

    def test_unless_includes_when_false(self):
        """Option included when unless condition is false."""
        yaml_text = self._make_yaml("""\
      - value: warm coat
        unless: "season == 'summer'"
      - value: t-shirt
        unless: "season == 'winter'"
""")
        prompt, _ = generate(yaml_text, {"season": "winter"}, seed=0)
        assert "warm coat" in prompt

    def test_unless_without_when(self):
        """unless alone (no when field) acts as an exclusion-only filter."""
        yaml_text = self._make_yaml("""\
      - value: snowflakes
        unless: "season == 'summer'"
      - value: sunshine
        unless: "season == 'winter'"
""")
        winter_prompt, _ = generate(yaml_text, {"season": "winter"}, seed=0)
        summer_prompt, _ = generate(yaml_text, {"season": "summer"}, seed=0)
        assert "snowflakes" in winter_prompt
        assert "sunshine" in summer_prompt

    def test_when_and_unless_combined(self):
        """Option included only when `when` passes AND `unless` fails."""
        yaml_text = self._make_yaml("""\
      - value: beach umbrella
        when: "season == 'summer'"
        unless: "season == 'winter'"
      - value: blanket
        when: "season == 'winter'"
""")
        # summer → when passes, unless fails → included
        summer_prompt, _ = generate(yaml_text, {"season": "summer"}, seed=0)
        assert "beach umbrella" in summer_prompt

        # winter → when fails → excluded (unless not even checked)
        winter_prompt, _ = generate(yaml_text, {"season": "winter"}, seed=0)
        assert "blanket" in winter_prompt

    def test_unless_invalid_expression_raises(self):
        """Invalid unless expression raises ValueError."""
        yaml_text = self._make_yaml("""\
      - value: oops
        unless: "undefined_var =="
""")
        with pytest.raises(ValueError, match="unless"):
            generate(yaml_text, {}, seed=0)

    def test_unless_on_all_options_gives_empty_variable(self):
        """When unless excludes all options, the variable is empty — no crash, no fallback."""
        yaml_text = self._make_yaml("""\
      - value: option a
        unless: "True"
      - value: option b
        unless: "True"
""")
        prompt, _ = generate(yaml_text, {"season": "summer"}, seed=0)
        # item is empty; template is "{{ season }}, {{ item }}" so result is just the season
        assert "option" not in prompt
        assert "summer" in prompt


# ---------------------------------------------------------------------------
# TestPromptFragments
# ---------------------------------------------------------------------------

def _gen(yaml_input, var_state=None, seed=0, **kwargs):
    """Wrapper that passes include_N kwargs through to node.generate()."""
    node = PowerPromptNode()
    return node.generate(
        yaml_input=yaml_input,
        var_state=json.dumps(var_state or {}),
        seed=seed,
        **kwargs,
    )


class TestPromptFragments:
    """Tests for the fragments: feature (rendered partials via {{ fragment.name }})."""

    def test_fragment_from_main_yaml(self):
        """Main YAML can define its own fragments: section."""
        yaml_text = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - happy

fragments:
  mood_desc: "feeling {{ mood }}"

prompt: |
  {{ fragment.mood_desc }}
"""
        prompt, _ = _gen(yaml_text, {"mood": "happy"})
        assert "feeling happy" in prompt

    def test_fragment_from_partial_available_in_main(self):
        """Fragment defined in a partial is available as {{ fragment.name }} in main prompt."""
        partial = """\
variables:
  city:
    type: select
    count: 1
    options:
      - Tokyo

fragments:
  location: "{{ city }}, vibrant streets"
"""
        yaml_text = """\
variables:
  character:
    type: select
    count: 1
    options:
      - 1girl

prompt: |
  {{ character }}, {{ fragment.location }}
"""
        prompt, _ = _gen(yaml_text, {"character": "1girl", "city": "Tokyo"}, include_1=partial)
        assert "1girl" in prompt
        assert "Tokyo, vibrant streets" in prompt

    def test_multiple_fragments_from_one_partial(self):
        """A single partial can export multiple named fragments."""
        partial = """\
variables:
  city:
    type: select
    count: 1
    options:
      - Paris
  style:
    type: select
    count: 1
    options:
      - watercolor

fragments:
  location: "{{ city }}"
  art_style: "{{ style }} painting"
"""
        yaml_text = """\
prompt: |
  {{ fragment.location }}, {{ fragment.art_style }}
"""
        prompt, _ = _gen(yaml_text, {"city": "Paris", "style": "watercolor"}, include_1=partial)
        assert "Paris" in prompt
        assert "watercolor painting" in prompt

    def test_main_fragments_override_partial_fragments(self):
        """Main YAML fragments override same-named partial fragments."""
        partial = """\
fragments:
  desc: "from partial"
"""
        yaml_text = """\
variables:
  x:
    type: select
    count: 1
    options:
      - a

fragments:
  desc: "from main"

prompt: |
  {{ fragment.desc }}
"""
        prompt, _ = _gen(yaml_text, {"x": "a"}, include_1=partial)
        assert "from main" in prompt
        assert "from partial" not in prompt

    def test_fragment_references_earlier_fragment(self):
        """A later fragment can reference an earlier fragment via {{ fragment.name }}."""
        yaml_text = """\
variables:
  city:
    type: select
    count: 1
    options:
      - Tokyo

fragments:
  location: "{{ city }}"
  full_scene: "{{ fragment.location }}, night scene"

prompt: |
  {{ fragment.full_scene }}
"""
        prompt, _ = _gen(yaml_text, {"city": "Tokyo"})
        assert "Tokyo, night scene" in prompt

    def test_fragments_across_two_partials(self):
        """Fragments from two partials are both available in the main prompt."""
        partial1 = """\
variables:
  city:
    type: select
    count: 1
    options:
      - Kyoto

fragments:
  location: "{{ city }}"
"""
        partial2 = """\
variables:
  mood:
    type: select
    count: 1
    options:
      - serene

fragments:
  atmosphere: "{{ mood }} atmosphere"
"""
        yaml_text = """\
prompt: |
  {{ fragment.location }}, {{ fragment.atmosphere }}
"""
        prompt, _ = _gen(
            yaml_text,
            {"city": "Kyoto", "mood": "serene"},
            include_1=partial1,
            include_2=partial2,
        )
        assert "Kyoto" in prompt
        assert "serene atmosphere" in prompt

    def test_partial_without_fragments_backward_compatible(self):
        """A partial with no fragments: key still works exactly as before."""
        partial = """\
variables:
  hair:
    type: select
    count: 1
    options:
      - silver
"""
        yaml_text = """\
variables:
  character:
    type: select
    count: 1
    options:
      - 1girl

prompt: |
  {{ character }}, {{ hair }} hair
"""
        prompt, _ = _gen(yaml_text, {"character": "1girl", "hair": "silver"}, include_1=partial)
        assert "1girl" in prompt
        assert "silver hair" in prompt

    def test_empty_fragment_dict_when_no_fragments_defined(self):
        """fragment context key is always present; accessing undefined name raises UndefinedError."""
        yaml_text = """\
variables:
  x:
    type: select
    count: 1
    options:
      - a

prompt: |
  {{ x }}, {{ fragment.missing }}
"""
        with pytest.raises(ValueError):
            _gen(yaml_text, {"x": "a"})

    def test_fragment_undefined_variable_raises(self):
        """A fragment template referencing an undefined variable raises ValueError."""
        yaml_text = """\
fragments:
  bad: "{{ no_such_var }}"

variables:
  x:
    type: select
    count: 1
    options:
      - a

prompt: |
  {{ fragment.bad }}
"""
        with pytest.raises(ValueError, match="Fragment 'bad'"):
            _gen(yaml_text, {"x": "a"})

    def test_partial_fragment_invalid_template_raises_on_partial_generate(self):
        """PowerPromptPartial.generate() catches invalid Jinja2 syntax in fragments."""
        partial_yaml = """\
fragments:
  broken: "{{ unclosed"
"""
        partial_node = PowerPromptPartial()
        with pytest.raises(ValueError, match="Fragment 'broken'"):
            partial_node.generate(partial_yaml)

    def test_merge_include_fragments_helper(self):
        """_merge_include_fragments merges dicts from multiple partials, last wins."""
        inc1 = "fragments:\n  a: alpha\n  b: beta\n"
        inc2 = "fragments:\n  b: BETA\n  c: gamma\n"
        result = _merge_include_fragments([inc1, inc2])
        assert result == {"a": "alpha", "b": "BETA", "c": "gamma"}

    def test_merge_include_fragments_ignores_invalid_yaml(self):
        """_merge_include_fragments silently skips unparseable partial strings."""
        result = _merge_include_fragments(["fragments:\n  a: ok\n", ": bad yaml ["])
        assert result == {"a": "ok"}


# ---------------------------------------------------------------------------
# TestCodeReviewFixes
# ---------------------------------------------------------------------------

class TestCodeReviewFixes:
    """Tests covering the bugs found in the code review."""

    def test_seed_is_reproducible_across_calls(self):
        """Same seed + YAML always produces the same output (deterministic hashing)."""
        yaml_text = """\
variables:
  x:
    type: select
    count: 1
    options: [a, b, c, d, e]
prompt: |
  {{ x }}
"""
        result1, _ = generate(yaml_text, seed=42)
        result2, _ = generate(yaml_text, seed=42)
        assert result1 == result2

    def test_null_option_value_not_stringified(self):
        """option value: null is skipped — does not produce the string 'None'."""
        yaml_text = """\
variables:
  x:
    type: select
    count: 1
    options:
      - value: null
      - real_value
prompt: |
  {{ x }}
"""
        prompt, _ = generate(yaml_text, seed=0)
        assert prompt != "None"
        assert "real_value" in prompt

    def test_weight_parsing_error_includes_variable_name(self):
        """Non-numeric weight raises ValueError that names the variable."""
        yaml_text = """\
variables:
  x:
    type: select
    count: 1
    options:
      - value: a
        weight: "not_a_number"
prompt: |
  {{ x }}
"""
        with pytest.raises(ValueError, match="variable 'x'"):
            generate(yaml_text, seed=0)

    def test_partial_validates_variables_is_mapping(self):
        """PowerPromptPartial.generate() rejects variables: that is not a dict."""
        partial_node = PowerPromptPartial()
        with pytest.raises(ValueError, match="'variables' must be a mapping"):
            partial_node.generate("variables: not a dict\n")

    def test_partial_validates_fragments_is_mapping(self):
        """PowerPromptPartial.generate() rejects fragments: that is not a dict."""
        partial_node = PowerPromptPartial()
        with pytest.raises(ValueError, match="'fragments' must be a mapping"):
            partial_node.generate("fragments: 42\n")

    def test_partial_accepts_empty_yaml(self):
        """PowerPromptPartial.generate() does not raise on empty input."""
        partial_node = PowerPromptPartial()
        result = partial_node.generate("")
        assert result == ("",)


# ---------------------------------------------------------------------------
# TestPowerPromptFilePartial
# ---------------------------------------------------------------------------

class TestPowerPromptFilePartial:

    VALID_YAML = """\
variables:
  city:
    type: select
    count: 1
    options:
      - Tokyo
      - Paris

fragments:
  location: "{{ city }}, vibrant streets"
"""

    def test_happy_path(self, tmp_path):
        """Loads a valid partial YAML file and returns its content."""
        f = tmp_path / "partial.yaml"
        f.write_text(self.VALID_YAML, encoding="utf-8")
        node = PowerPromptFilePartial()
        result = node.generate(partial_file=str(f), yaml_input="")
        assert result == (self.VALID_YAML,)

    def test_content_feeds_into_main_node(self, tmp_path):
        """Content from the file partial can be used by PowerPromptNode as an include."""
        f = tmp_path / "partial.yaml"
        f.write_text(self.VALID_YAML, encoding="utf-8")
        node = PowerPromptFilePartial()
        (content,) = node.generate(partial_file=str(f), yaml_input="")

        main = PowerPromptNode()
        prompt, _ = main.generate(
            yaml_input="prompt: |\n  {{ fragment.location }}\n",
            var_state=json.dumps({"city": "Tokyo"}),
            seed=0,
            include_1=content,
        )
        assert prompt == "Tokyo, vibrant streets"

    def test_file_not_found(self, tmp_path):
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="file not found"):
            node.generate(partial_file=str(tmp_path / "missing.yaml"), yaml_input="")

    def test_empty_path_raises(self):
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="no file path provided"):
            node.generate(partial_file="", yaml_input="")

    def test_invalid_yaml_raises(self, tmp_path):
        f = tmp_path / "bad.yaml"
        f.write_text(": this is not valid yaml [", encoding="utf-8")
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="invalid YAML"):
            node.generate(partial_file=str(f), yaml_input="")

    def test_non_mapping_yaml_raises(self, tmp_path):
        f = tmp_path / "list.yaml"
        f.write_text("- a\n- b\n", encoding="utf-8")
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="must be a YAML mapping"):
            node.generate(partial_file=str(f), yaml_input="")

    def test_validates_variables_is_mapping(self, tmp_path):
        f = tmp_path / "bad_vars.yaml"
        f.write_text("variables: not a dict\n", encoding="utf-8")
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="'variables'.*must be a mapping"):
            node.generate(partial_file=str(f), yaml_input="")

    def test_validates_fragment_jinja2(self, tmp_path):
        f = tmp_path / "bad_frag.yaml"
        f.write_text('fragments:\n  broken: "{{ unclosed"\n', encoding="utf-8")
        node = PowerPromptFilePartial()
        with pytest.raises(ValueError, match="fragment 'broken'"):
            node.generate(partial_file=str(f), yaml_input="")

    def test_yaml_input_arg_is_ignored(self, tmp_path):
        """yaml_input kwarg (the JS cache) has no effect — file content wins."""
        f = tmp_path / "real.yaml"
        f.write_text(self.VALID_YAML, encoding="utf-8")
        node = PowerPromptFilePartial()
        result = node.generate(partial_file=str(f), yaml_input="variables: {}\n")
        assert result == (self.VALID_YAML,)
