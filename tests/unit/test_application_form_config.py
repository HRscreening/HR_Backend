"""
Unit tests for the DEFAULT_QUESTIONS constant and ApplicationFormConfig model defaults.

Validates the structure and business rules of the default question set
without any DB connection.
"""

import pytest

from src.models.application_form_config_model import (
    ALLOWED_QUESTION_TYPES,
    DEFAULT_QUESTIONS,
)


# ── Structure tests ────────────────────────────────────────────────────────────

class TestDefaultQuestionsStructure:
    REQUIRED_KEYS = {"id", "key", "label", "type", "required", "removable", "placeholder"}
    CORE_FIELD_KEYS = {"full_name", "email", "resume"}

    def test_default_questions_not_empty(self):
        assert len(DEFAULT_QUESTIONS) > 0

    def test_every_question_has_required_fields(self):
        for q in DEFAULT_QUESTIONS:
            missing = self.REQUIRED_KEYS - set(q.keys())
            assert not missing, f"Question '{q.get('id')}' missing fields: {missing}"

    def test_all_types_are_allowed(self):
        for q in DEFAULT_QUESTIONS:
            assert q["type"] in ALLOWED_QUESTION_TYPES, (
                f"Question '{q['id']}' has unknown type '{q['type']}'"
            )

    def test_all_ids_are_unique(self):
        ids = [q["id"] for q in DEFAULT_QUESTIONS]
        assert len(ids) == len(set(ids)), "Duplicate question IDs found in DEFAULT_QUESTIONS"

    def test_all_keys_are_unique(self):
        keys = [q["key"] for q in DEFAULT_QUESTIONS]
        assert len(keys) == len(set(keys)), "Duplicate question keys found in DEFAULT_QUESTIONS"

    def test_core_fields_are_present(self):
        keys = {q["key"] for q in DEFAULT_QUESTIONS}
        missing = self.CORE_FIELD_KEYS - keys
        assert not missing, f"Core fields missing from DEFAULT_QUESTIONS: {missing}"

    def test_core_fields_are_not_removable(self):
        core_questions = [q for q in DEFAULT_QUESTIONS if q["key"] in self.CORE_FIELD_KEYS]
        for q in core_questions:
            assert q["removable"] is False, (
                f"Core field '{q['key']}' must have removable=False"
            )

    def test_core_fields_are_required(self):
        core_questions = [q for q in DEFAULT_QUESTIONS if q["key"] in self.CORE_FIELD_KEYS]
        for q in core_questions:
            assert q["required"] is True, (
                f"Core field '{q['key']}' must have required=True"
            )

    def test_non_core_fields_are_removable(self):
        optional_questions = [q for q in DEFAULT_QUESTIONS if q["key"] not in self.CORE_FIELD_KEYS]
        for q in optional_questions:
            assert q["removable"] is True, (
                f"Optional field '{q['key']}' must have removable=True"
            )

    def test_core_fields_appear_first(self):
        """full_name, email, resume should be the first three questions."""
        first_three_keys = [q["key"] for q in DEFAULT_QUESTIONS[:3]]
        for key in self.CORE_FIELD_KEYS:
            assert key in first_three_keys, (
                f"Core field '{key}' must be in the first 3 questions"
            )

    def test_all_placeholders_are_strings(self):
        for q in DEFAULT_QUESTIONS:
            assert isinstance(q["placeholder"], str), (
                f"Question '{q['id']}' placeholder must be a string"
            )
            assert len(q["placeholder"]) > 0, (
                f"Question '{q['id']}' placeholder must not be empty"
            )


# ── Immutability: default callable returns a fresh copy ───────────────────────

class TestDefaultQuestionsImmutability:
    def test_default_is_a_new_list_each_time(self):
        """list(DEFAULT_QUESTIONS) must return a new list, not the same object."""
        copy1 = list(DEFAULT_QUESTIONS)
        copy2 = list(DEFAULT_QUESTIONS)
        assert copy1 is not copy2, "Each copy must be a distinct list object"
        assert copy1 == copy2, "Copies must have equal contents"

    def test_mutating_copy_does_not_affect_original(self):
        copy = list(DEFAULT_QUESTIONS)
        original_len = len(DEFAULT_QUESTIONS)

        copy.append({"id": "q_test", "key": "test_field", "label": "Test", "type": "text",
                     "required": False, "removable": True, "placeholder": "Test"})
        assert len(DEFAULT_QUESTIONS) == original_len, (
            "Mutating a copy must not affect the original DEFAULT_QUESTIONS list"
        )

    def test_orm_column_default_is_callable(self):
        """The ORM column default must be a callable (not a bare list) to avoid shared state."""
        from src.models.application_form_config_model import ApplicationFormConfig
        default = ApplicationFormConfig.questions.property.columns[0].default
        assert default is not None, "questions column must have a default"
        assert callable(default.arg), (
            "questions column default must be a callable so each row gets its own list"
        )


# ── ALLOWED_QUESTION_TYPES ────────────────────────────────────────────────────

class TestAllowedQuestionTypes:
    def test_contains_essential_types(self):
        essential = {"text", "email", "number", "url", "file", "textarea", "select", "boolean"}
        assert essential == ALLOWED_QUESTION_TYPES
