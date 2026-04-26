from shared.utils import sanitize_log_data


def test_masks_email_with_first_two_local_and_last_five_domain_chars():
    data = sanitize_log_data({"email": "teszt@example.com"})

    assert data == {"email": "te***@******e.com"}


def test_redacts_short_local_part_email_fully():
    data = sanitize_log_data({"email": "abc@xy.com"})

    assert data == {"email": "[REDACTED]"}


def test_keeps_short_domain_visible_while_masking_local_part():
    data = sanitize_log_data({"email": "teszt@abc"})

    assert data == {"email": "te***@abc"}


def test_masks_numeric_two_factor_code_but_keeps_last_two_digits():
    data = sanitize_log_data({"two_factor_code": "123456"})

    assert data == {"two_factor_code": "****56"}


def test_redacts_non_numeric_two_factor_code_fully():
    data = sanitize_log_data({"two_factor_code": "AB1234"})

    assert data == {"two_factor_code": "[REDACTED]"}


def test_sanitizes_nested_data_recursively():
    data = sanitize_log_data(
        {
            "nested": {
                "email": "teszt@example.com",
                "two_factor_code": "987654",
            }
        }
    )

    assert data == {"nested": {"email": "te***@******e.com", "two_factor_code": "****54"}}
