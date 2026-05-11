# Multilingual Lexicon Guide

## Purpose

The backend uses a shared multilingual lexicon registry at `shared/text/language_lexicon.py`.
This file centralizes language-specific lexical terms used by:

- chat query parsing (`chat_service`)
- query resolution (`query_resolver_v0`)
- space/time extraction (`space_time_extractor_v1`)
- search keyword filtering (`search_profile_builder_v1`)

The default fallback chain is:

`requested_language -> en -> generic`

Use `include_fallback=False` when a module needs strict language-only terms.

## Supported languages

- `hu`
- `en`
- `es`

## Required keys per language

Each language entry must provide at least:

- `question_words`
- `helper_verbs`
- `entity_stopwords`
- `question_stopwords`
- `descriptor_terms`
- `entity_suffixes`
- `name_suffixes`
- `place_suffixes`
- `time_months`
- `time_weekdays`
- `time_relative_current`
- `time_relative_open`
- `time_relative_bounded`
- `time_event_markers`

Validation helper:

- `validate_language_lexicon()`

## Adding a new language

1. Add a new language code entry in `_LEXICON_DATA`.
2. Fill all required keys listed above.
3. (Optional) Add month index mappings to `_MONTH_INDEX_BY_LANGUAGE` for `get_month_number`.
4. Add/extend tests:
   - `backend/tests/unit/knowledge/test_language_lexicon.py`
   - relevant parser/extractor tests for the new language.

## Notes

- Keep terms lowercase where possible.
- Include both accented and accent-less variants only when needed.
- Prefer lexicon updates over new hardcoded constants in service modules.
