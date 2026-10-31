import pytest
from sqlalchemy import text

from app.domain.errors import EmailAlreadyRegistered
from app.domain.models.user import Role, User
from tests.fakes.in_memory import FIXED_NOW


def _user(email="ana@example.com", role=Role.ATTENDEE) -> User:
    return User.new(email=email, password_hash="hash", full_name="Ana", now=FIXED_NOW, role=role)


async def test_add_and_read_back_by_id_and_email(uow_factory):
    user = _user(role=Role.ORGANIZER)
    async with uow_factory() as uow:
        await uow.users.add(user)
        await uow.commit()

    async with uow_factory() as uow:
        by_id = await uow.users.get_by_id(user.id)
        by_email = await uow.users.get_by_email("ana@example.com")

    assert by_id == user
    assert by_email == user
    assert by_id.role is Role.ORGANIZER
    assert by_id.created_at == FIXED_NOW


async def test_unknown_user_returns_none(uow_factory):
    async with uow_factory() as uow:
        assert await uow.users.get_by_email("nadie@example.com") is None


async def test_duplicate_email_raises_domain_error(uow_factory):
    async with uow_factory() as uow:
        await uow.users.add(_user())
        await uow.commit()

    with pytest.raises(EmailAlreadyRegistered):
        async with uow_factory() as uow:
            await uow.users.add(_user())
            await uow.commit()


async def test_changes_are_rolled_back_without_commit(uow_factory):
    async with uow_factory() as uow:
        await uow.users.add(_user())

    async with uow_factory() as uow:
        assert await uow.users.get_by_email("ana@example.com") is None


async def test_database_rejects_invalid_role_and_uppercase_email(engine):
    async with engine.connect() as connection:
        for sql in (
            "INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
            "VALUES (gen_random_uuid(), 'a@b.co', 'h', 'n', 'superuser', now())",
            "INSERT INTO users (id, email, password_hash, full_name, role, created_at) "
            "VALUES (gen_random_uuid(), 'A@B.CO', 'h', 'n', 'attendee', now())",
        ):
            with pytest.raises(Exception, match="violates check constraint"):
                await connection.execute(text(sql))
            await connection.rollback()
