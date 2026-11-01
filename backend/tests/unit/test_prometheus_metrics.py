from prometheus_client import generate_latest

from app.adapters.outbound.observability.prometheus_metrics import (
    PrometheusMetrics,
    create_registry,
)
from app.adapters.outbound.persistence.database import create_engine


def make():
    registry = create_registry()
    return PrometheusMetrics(registry), registry


def sample(registry, name, **labels):
    return registry.get_sample_value(name, labels)


def test_registrations_are_counted_by_result():
    metrics, registry = make()
    metrics.registration_attempt("ok")
    metrics.registration_attempt("ok")
    metrics.registration_attempt("full")

    assert sample(registry, "miseventos_registrations_total", result="ok") == 2
    assert sample(registry, "miseventos_registrations_total", result="full") == 1
    assert sample(registry, "miseventos_registrations_total", result="duplicate") is None


def test_slot_filter_and_compensations():
    metrics, registry = make()
    metrics.slot_filter("allowed")
    metrics.slot_filter("rejected")
    metrics.slot_compensation()

    assert sample(registry, "miseventos_slot_filter_total", result="allowed") == 1
    assert sample(registry, "miseventos_slot_filter_total", result="rejected") == 1
    assert sample(registry, "miseventos_slot_compensations_total") == 1


def test_events_closed_adds_the_given_count_per_source():
    metrics, registry = make()
    metrics.event_closed("scheduler", 3)
    metrics.event_closed("manual")

    assert sample(registry, "miseventos_events_closed_total", source="scheduler") == 3
    assert sample(registry, "miseventos_events_closed_total", source="manual") == 1


def test_last_success_timestamp_only_moves_on_success():
    metrics, registry = make()
    metrics.maintenance_run("finish_expired", ok=False)
    assert (
        sample(
            registry, "miseventos_maintenance_last_success_timestamp_seconds", task="finish_expired"
        )
        is None
    )

    metrics.maintenance_run("finish_expired", ok=True)

    assert (
        sample(registry, "miseventos_maintenance_runs_total", task="finish_expired", result="error")
        == 1
    )
    assert (
        sample(registry, "miseventos_maintenance_runs_total", task="finish_expired", result="ok")
        == 1
    )
    assert (
        sample(
            registry, "miseventos_maintenance_last_success_timestamp_seconds", task="finish_expired"
        )
        > 1_700_000_000
    )


def test_login_and_cache_metrics():
    metrics, registry = make()
    metrics.login_attempt("rate_limited")
    metrics.cache_lookup("event", hit=True)
    metrics.cache_lookup("event", hit=False)

    assert sample(registry, "miseventos_login_attempts_total", result="rate_limited") == 1
    assert sample(registry, "miseventos_cache_lookups_total", kind="event", result="hit") == 1
    assert sample(registry, "miseventos_cache_lookups_total", kind="event", result="miss") == 1


def test_each_registry_is_independent():
    first, first_registry = make()
    _, second_registry = make()
    first.registration_attempt("ok")

    assert sample(second_registry, "miseventos_registrations_total", result="ok") is None
    assert sample(first_registry, "miseventos_registrations_total", result="ok") == 1


def test_exposition_includes_process_metrics_and_help_text():
    _, registry = make()
    text = generate_latest(registry).decode()
    assert "process_cpu_seconds_total" in text or "python_info" in text


def test_sql_error_messages_hide_parameter_values():
    """Evita que correos o hashes aparezcan en los logs cuando una sentencia falla."""
    engine = create_engine("postgresql+psycopg://u:p@localhost/db")
    assert engine.sync_engine.hide_parameters is True
