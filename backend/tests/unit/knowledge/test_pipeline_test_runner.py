from __future__ import annotations

from pathlib import Path

from run_test import PipelineTestCase, default_output_path, parse_cases


def test_parse_cases_reads_multiple_train_query_blocks() -> None:
    cases = parse_cases(
        '''
TEST_CASE: London office basic

TRAIN:
"""
The London office is currently inactive.
"""

QUERY:
"""
What is the status of London office?
"""

TEST_CASE: London conflict

TRAIN:
"""
The London office is currently active.
"""

QUERY:
"""
What is the status of London office?
"""
'''
    )

    assert cases == [
        PipelineTestCase(
            name="London office basic",
            train="The London office is currently inactive.",
            query="What is the status of London office?",
        ),
        PipelineTestCase(
            name="London conflict",
            train="The London office is currently active.",
            query="What is the status of London office?",
        ),
    ]


def test_parse_cases_reads_rendered_test_case_banners() -> None:
    cases = parse_cases(
        '''
=== TEST CASE: relation direct ===

TRAIN:
"""
The support service uses Freshdesk for customer tickets.
"""

QUERY:
"""
What does the support service use?
"""

EXPECTED:
"""
The support service uses Freshdesk for customer tickets.
"""
'''
    )

    assert cases == [
        PipelineTestCase(
            name="relation direct",
            train="The support service uses Freshdesk for customer tickets.",
            query="What does the support service use?",
            expected={"answer_contains": ["The support service uses Freshdesk for customer tickets."], "answer_not_contains": [], "retrieval_chunk_contains": []},
        )
    ]


def test_default_output_path_uses_test_results_with_input_name() -> None:
    assert default_output_path(Path("tests/london_test.txt")) == Path("test_results/london_test.txt")
