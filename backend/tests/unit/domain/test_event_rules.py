from datetime import timedelta
from uuid import uuid4

import pytest

from app.domain.errors import Forbidden, InvalidTransition, ValidationFailed
from app.domain.models.event import ClosedSource, EventStatus
from app.domain.models.user import Role
from app.domain.services import event_lifecycle
from app.domain.services.event_rules import EventData, validate_event_data
from app.domain.services.permissions import can_view_event, ensure_can_manage_event
from tests.factories import make_event, make_user
from tests.fakes.in_memory import FIXED_NOW

NOW = FIXED_NOW


def _data(**overrides) -> EventData:
    base = {
        "name": "Congreso",
        "description": None,
        "location": "Bogotá",
        "start_at": NOW + timedelta(days=1),
        "end_at": NOW + timedelta(days=1, hours=2),
        "capacity": 50,
    }
    return EventData(**{**base, **overrides})


class TestValidateEventData:
    def test_cleans_whitespace_and_empty_description(self):
        result = validate_event_data(
            _data(name="  Congreso ", description="   "), now=NOW, require_future_start=True
        )
        assert result.name == "Congreso"
        assert result.description is None

    def test_collects_every_problem_at_once(self):
        with pytest.raises(ValidationFailed) as exc:
            validate_event_data(
                _data(name=" ", capacity=0, end_at=NOW), now=NOW, require_future_start=True
            )
        assert len(exc.value.details) >= 3

    def test_end_must_be_after_start(self):
        with pytest.raises(ValidationFailed, match="inválidos"):
            validate_event_data(
                _data(end_at=NOW + timedelta(days=1)), now=NOW, require_future_start=True
            )

    def test_future_start_only_required_when_asked(self):
        past = _data(start_at=NOW - timedelta(hours=2), end_at=NOW + timedelta(hours=1))
        validate_event_data(past, now=NOW, require_future_start=False)
        with pytest.raises(ValidationFailed):
            validate_event_data(past, now=NOW, require_future_start=True)

    def test_naive_datetimes_are_rejected(self):
        naive = _data(start_at=NOW.replace(tzinfo=None) + timedelta(days=1))
        with pytest.raises(ValidationFailed):
            validate_event_data(naive, now=NOW, require_future_start=True)

    def test_capacity_cannot_drop_below_registered(self):
        with pytest.raises(ValidationFailed, match="inválidos") as exc:
            validate_event_data(
                _data(capacity=5), now=NOW, require_future_start=False, min_capacity=10
            )
        assert "inscritos" in exc.value.details[0]
        validate_event_data(
            _data(capacity=10), now=NOW, require_future_start=False, min_capacity=10
        )

    @pytest.mark.parametrize("capacity", [0, -1, 100_001])
    def test_capacity_bounds(self, capacity):
        with pytest.raises(ValidationFailed):
            validate_event_data(_data(capacity=capacity), now=NOW, require_future_start=True)


class TestEffectiveStatus:
    def test_published_event_in_the_past_counts_as_finished(self):
        event = make_event(uuid4(), status=EventStatus.PUBLISHED, starts_in=-timedelta(days=2))
        assert event.effective_status(NOW) is EventStatus.FINISHED
        assert event.status is EventStatus.PUBLISHED  # lo persistido no cambia
        assert event.with_effective_status(NOW).status is EventStatus.FINISHED

    def test_ongoing_event_is_still_published(self):
        event = make_event(
            uuid4(),
            status=EventStatus.PUBLISHED,
            starts_in=-timedelta(hours=1),
            lasts=timedelta(hours=3),
        )
        assert event.effective_status(NOW) is EventStatus.PUBLISHED

    @pytest.mark.parametrize("status", [EventStatus.DRAFT, EventStatus.CANCELLED])
    def test_other_statuses_never_change(self, status):
        event = make_event(uuid4(), status=status, starts_in=-timedelta(days=2))
        assert event.effective_status(NOW) is status


class TestLifecycle:
    def test_publish_draft(self):
        event = make_event(uuid4())
        event_lifecycle.publish(event, NOW)
        assert event.status is EventStatus.PUBLISHED

    def test_cannot_publish_twice_or_a_past_draft(self):
        published = make_event(uuid4(), status=EventStatus.PUBLISHED)
        with pytest.raises(InvalidTransition):
            event_lifecycle.publish(published, NOW)
        past = make_event(uuid4(), starts_in=-timedelta(days=1))
        with pytest.raises(ValidationFailed):
            event_lifecycle.publish(past, NOW)

    def test_finish_records_who_and_how(self):
        event = make_event(uuid4(), status=EventStatus.PUBLISHED)
        actor = uuid4()
        event_lifecycle.finish(event, actor, NOW)
        assert event.status is EventStatus.FINISHED
        assert (event.closed_at, event.closed_by_id, event.closed_source) == (
            NOW,
            actor,
            ClosedSource.MANUAL,
        )

    def test_cannot_finish_a_draft(self):
        with pytest.raises(InvalidTransition):
            event_lifecycle.finish(make_event(uuid4()), uuid4(), NOW)

    @pytest.mark.parametrize("status", [EventStatus.DRAFT, EventStatus.PUBLISHED])
    def test_cancel_from_open_states(self, status):
        event = make_event(uuid4(), status=status)
        event_lifecycle.cancel(event, uuid4(), NOW)
        assert event.status is EventStatus.CANCELLED
        assert event.closed_source is ClosedSource.MANUAL

    @pytest.mark.parametrize("status", [EventStatus.FINISHED, EventStatus.CANCELLED])
    def test_closed_events_cannot_be_cancelled_or_edited(self, status):
        event = make_event(uuid4(), status=status)
        with pytest.raises(InvalidTransition):
            event_lifecycle.cancel(event, uuid4(), NOW)
        with pytest.raises(InvalidTransition):
            event_lifecycle.ensure_editable(event, NOW)

    def test_expired_published_event_cannot_be_edited_or_cancelled(self):
        event = make_event(uuid4(), status=EventStatus.PUBLISHED, starts_in=-timedelta(days=2))
        with pytest.raises(InvalidTransition):
            event_lifecycle.ensure_editable(event, NOW)
        with pytest.raises(InvalidTransition):
            event_lifecycle.cancel(event, uuid4(), NOW)


class TestPermissions:
    def test_owner_organizer_can_manage(self):
        owner = make_user(Role.ORGANIZER)
        ensure_can_manage_event(owner, make_event(owner.id))

    def test_other_organizer_cannot_manage(self):
        with pytest.raises(Forbidden):
            ensure_can_manage_event(make_user(Role.ORGANIZER), make_event(uuid4()))

    def test_admin_can_manage_any_event(self):
        ensure_can_manage_event(make_user(Role.ADMIN), make_event(uuid4()))

    def test_demoted_owner_loses_access(self):
        former_organizer = make_user(Role.ATTENDEE)
        with pytest.raises(Forbidden):
            ensure_can_manage_event(former_organizer, make_event(former_organizer.id))

    def test_drafts_are_visible_only_to_owner_and_admin(self):
        owner, other, admin = (
            make_user(Role.ORGANIZER),
            make_user(Role.ORGANIZER),
            make_user(Role.ADMIN),
        )
        draft = make_event(owner.id)
        assert can_view_event(owner, draft) and can_view_event(admin, draft)
        assert not can_view_event(other, draft) and not can_view_event(None, draft)
        assert can_view_event(None, make_event(owner.id, status=EventStatus.PUBLISHED))
