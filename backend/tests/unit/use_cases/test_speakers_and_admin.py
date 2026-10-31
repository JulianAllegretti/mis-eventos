import pytest

from app.application.dto.commands import (
    CreateSpeakerCommand,
    SpeakerActionCommand,
    UpdateSpeakerCommand,
    UpdateUserCommand,
)
from app.application.dto.queries import GetSpeakerQuery, ListSpeakersQuery, ListUsersQuery
from app.application.use_cases.admin.manage_users import ListUsersUseCase, UpdateUserUseCase
from app.application.use_cases.speakers.manage_speakers import (
    CreateSpeakerUseCase,
    DeleteSpeakerUseCase,
    GetSpeakerUseCase,
    ListSpeakersUseCase,
    UpdateSpeakerUseCase,
)
from app.domain.errors import Forbidden, NotFound, ValidationFailed
from app.domain.models.user import Role
from tests.factories import make_speaker, make_user
from tests.fakes.in_memory import FixedClock, make_uow_factory


@pytest.fixture
def users():
    return {}


@pytest.fixture
def speakers():
    return {}


@pytest.fixture
def uow_factory(users, speakers):
    return make_uow_factory(users, None, speakers)


class TestSpeakers:
    async def test_organizer_creates_a_speaker_without_user_account(self, uow_factory, speakers):
        organizer = make_user(Role.ORGANIZER)

        speaker = await CreateSpeakerUseCase(uow_factory, FixedClock()).execute(
            CreateSpeakerCommand(organizer, " Ana Pérez ", "ANA@Ponentes.co", " Bio ")
        )

        assert (speaker.name, speaker.email, speaker.bio) == ("Ana Pérez", "ana@ponentes.co", "Bio")
        assert speakers[speaker.id] is speaker

    async def test_attendee_cannot_manage_speakers(self, uow_factory):
        attendee = make_user()
        with pytest.raises(Forbidden):
            await CreateSpeakerUseCase(uow_factory, FixedClock()).execute(
                CreateSpeakerCommand(attendee, "Ana", None, None)
            )
        with pytest.raises(Forbidden):
            await ListSpeakersUseCase(uow_factory).execute(ListSpeakersQuery(attendee))

    async def test_invalid_email_and_empty_name_are_reported_together(self, uow_factory):
        with pytest.raises(ValidationFailed) as exc:
            await CreateSpeakerUseCase(uow_factory, FixedClock()).execute(
                CreateSpeakerCommand(make_user(Role.ORGANIZER), "  ", "no-es-correo", None)
            )
        assert len(exc.value.details) == 2

    async def test_update_applies_partial_changes(self, uow_factory, speakers):
        organizer = make_user(Role.ORGANIZER)
        speaker = make_speaker(organizer.id)
        speakers[speaker.id] = speaker

        updated = await UpdateSpeakerUseCase(uow_factory).execute(
            UpdateSpeakerCommand(organizer, speaker.id, {"bio": None, "name": "Ana M."})
        )

        assert (updated.name, updated.bio, updated.email) == ("Ana M.", None, "ana@ponentes.co")

    async def test_missing_speaker_is_not_found(self, uow_factory):
        organizer = make_user(Role.ORGANIZER)
        other = make_speaker(organizer.id)
        for use_case, cmd in (
            (GetSpeakerUseCase(uow_factory), GetSpeakerQuery(organizer, other.id)),
            (DeleteSpeakerUseCase(uow_factory), SpeakerActionCommand(organizer, other.id)),
        ):
            with pytest.raises(NotFound):
                await use_case.execute(cmd)

    async def test_delete_and_search_by_name(self, uow_factory, speakers):
        organizer = make_user(Role.ADMIN)
        ana, luis = make_speaker(organizer.id, "Ana"), make_speaker(organizer.id, "Luis")
        speakers.update({ana.id: ana, luis.id: luis})

        page = await ListSpeakersUseCase(uow_factory).execute(ListSpeakersQuery(organizer, q="an"))
        assert [s.name for s in page.items] == ["Ana"]

        await DeleteSpeakerUseCase(uow_factory).execute(SpeakerActionCommand(organizer, ana.id))
        assert list(speakers) == [luis.id]


class TestAdminUsers:
    async def test_admin_changes_role_and_deactivates(self, uow_factory, users):
        admin, user = make_user(Role.ADMIN), make_user()
        users.update({admin.id: admin, user.id: user})
        use_case = UpdateUserUseCase(uow_factory)

        promoted = await use_case.execute(UpdateUserCommand(admin, user.id, {"role": "organizer"}))
        assert promoted.role is Role.ORGANIZER
        disabled = await use_case.execute(UpdateUserCommand(admin, user.id, {"is_active": False}))
        assert disabled.is_active is False

    async def test_non_admin_is_forbidden(self, uow_factory, users):
        organizer, user = make_user(Role.ORGANIZER), make_user()
        users.update({organizer.id: organizer, user.id: user})
        with pytest.raises(Forbidden):
            await UpdateUserUseCase(uow_factory).execute(
                UpdateUserCommand(organizer, user.id, {"role": "admin"})
            )
        with pytest.raises(Forbidden):
            await ListUsersUseCase(uow_factory).execute(ListUsersQuery(organizer))

    async def test_admin_cannot_change_their_own_role_or_status(self, uow_factory, users):
        admin = make_user(Role.ADMIN)
        users[admin.id] = admin
        with pytest.raises(Forbidden):
            await UpdateUserUseCase(uow_factory).execute(
                UpdateUserCommand(admin, admin.id, {"role": "attendee"})
            )
        assert admin.role is Role.ADMIN

    @pytest.mark.parametrize(
        "changes", [{}, {"email": "x@y.co"}, {"role": "superuser"}, {"is_active": "no"}]
    )
    async def test_invalid_changes_are_rejected(self, uow_factory, users, changes):
        admin, user = make_user(Role.ADMIN), make_user()
        users.update({admin.id: admin, user.id: user})
        with pytest.raises(ValidationFailed):
            await UpdateUserUseCase(uow_factory).execute(UpdateUserCommand(admin, user.id, changes))

    async def test_unknown_user_is_not_found_and_list_filters(self, uow_factory, users):
        admin, ana = make_user(Role.ADMIN), make_user(email="ana@example.com")
        users.update({admin.id: admin, ana.id: ana})
        with pytest.raises(NotFound):
            await UpdateUserUseCase(uow_factory).execute(
                UpdateUserCommand(admin, make_user().id, {"is_active": False})
            )
        page = await ListUsersUseCase(uow_factory).execute(ListUsersQuery(admin, q="ANA"))
        assert [u.email for u in page.items] == ["ana@example.com"]
