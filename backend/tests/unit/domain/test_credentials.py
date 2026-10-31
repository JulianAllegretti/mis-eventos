import pytest

from app.domain.errors import ValidationFailed
from app.domain.models.user import Role, User
from app.domain.services.credentials import (
    normalize_email,
    validate_full_name,
    validate_password,
)
from tests.fakes.in_memory import FIXED_NOW


def test_normalize_email_lowercases_and_strips():
    assert normalize_email("  Ana@Example.COM ") == "ana@example.com"


@pytest.mark.parametrize("value", ["", "sin-arroba", "@example.com", "ana@", "ana@localhost"])
def test_normalize_email_rejects_invalid(value):
    with pytest.raises(ValidationFailed):
        normalize_email(value)


@pytest.mark.parametrize("password", ["corta", "x" * 129])
def test_validate_password_rejects_out_of_range(password):
    with pytest.raises(ValidationFailed):
        validate_password(password)


@pytest.mark.parametrize("password", ["x" * 8, "x" * 128])
def test_validate_password_accepts_boundaries(password):
    validate_password(password)


def test_validate_full_name_strips_and_rejects_empty():
    assert validate_full_name("  Ana Pérez ") == "Ana Pérez"
    with pytest.raises(ValidationFailed):
        validate_full_name("   ")
    with pytest.raises(ValidationFailed):
        validate_full_name("x" * 121)


def test_new_user_defaults_to_attendee_and_normalizes_email():
    user = User.new(email="ANA@example.com", password_hash="h", full_name=" Ana ", now=FIXED_NOW)
    assert user.role is Role.ATTENDEE
    assert user.email == "ana@example.com"
    assert user.full_name == "Ana"
    assert user.is_active is True
