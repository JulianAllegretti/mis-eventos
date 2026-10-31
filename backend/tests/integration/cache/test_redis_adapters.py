import asyncio
from uuid import uuid4

from app.adapters.outbound.cache.redis_cache import RedisCache
from app.adapters.outbound.cache.redis_client import create_redis
from app.adapters.outbound.cache.redis_slot_counter import RedisSlotCounter
from app.application.ports.outbound.slot_counter import SlotResult


class TestRedisSlotCounter:
    async def test_lifecycle_missing_initialize_acquire_full_release(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()

        assert await counter.try_acquire(event_id) is SlotResult.MISSING
        await counter.initialize(event_id, 2)
        assert await counter.try_acquire(event_id) is SlotResult.ALLOWED
        assert await counter.try_acquire(event_id) is SlotResult.ALLOWED
        assert await counter.try_acquire(event_id) is SlotResult.FULL

        await counter.release(event_id)
        assert await counter.try_acquire(event_id) is SlotResult.ALLOWED

    async def test_initialize_does_not_overwrite_an_existing_counter(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()
        await counter.initialize(event_id, 1)
        await counter.try_acquire(event_id)  # ahora es 0

        await counter.initialize(event_id, 99)  # otro proceso llega tarde

        assert await counter.try_acquire(event_id) is SlotResult.FULL

    async def test_release_and_reconcile_never_create_a_counter(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()

        await counter.release(event_id)
        await counter.reconcile(event_id, 5)

        assert await counter.try_acquire(event_id) is SlotResult.MISSING

    async def test_reconcile_fixes_drift_and_keeps_the_ttl(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()
        await counter.initialize(event_id, 10)
        key = f"slots:event:{event_id}"
        ttl_before = await redis_client.ttl(key)

        await counter.reconcile(event_id, 3)

        assert int(await redis_client.get(key)) == 3
        assert 0 < await redis_client.ttl(key) <= ttl_before

    async def test_negative_availability_is_clamped_to_zero(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()
        await counter.initialize(event_id, -4)
        assert await counter.try_acquire(event_id) is SlotResult.FULL

    async def test_invalidate_forces_a_rebuild(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()
        await counter.initialize(event_id, 1)
        await counter.invalidate(event_id)
        assert await counter.try_acquire(event_id) is SlotResult.MISSING

    async def test_concurrent_acquires_never_exceed_the_counter(self, redis_client):
        counter, event_id = RedisSlotCounter(redis_client), uuid4()
        await counter.initialize(event_id, 10)

        results = await asyncio.gather(*(counter.try_acquire(event_id) for _ in range(100)))

        assert results.count(SlotResult.ALLOWED) == 10
        assert results.count(SlotResult.FULL) == 90
        assert int(await redis_client.get(f"slots:event:{event_id}")) == 0

    async def test_claim_admits_one_attempt_per_user_and_event(self, redis_client):
        counter, event_id, user_id = RedisSlotCounter(redis_client), uuid4(), uuid4()

        assert await counter.claim(event_id, user_id) is True
        assert await counter.claim(event_id, user_id) is False
        assert await counter.claim(event_id, uuid4()) is True  # otro usuario
        assert await counter.claim(uuid4(), user_id) is True  # otro evento

        await counter.unclaim(event_id, user_id)
        assert await counter.claim(event_id, user_id) is True

    async def test_claim_expires_on_its_own(self, redis_client):
        counter, event_id, user_id = RedisSlotCounter(redis_client), uuid4(), uuid4()
        await counter.claim(event_id, user_id)
        assert 0 < await redis_client.ttl(f"claim:event:{event_id}:user:{user_id}") <= 10

    async def test_concurrent_claims_have_exactly_one_winner(self, redis_client):
        counter, event_id, user_id = RedisSlotCounter(redis_client), uuid4(), uuid4()

        results = await asyncio.gather(*(counter.claim(event_id, user_id) for _ in range(50)))

        assert results.count(True) == 1

    async def test_unreachable_redis_degrades_to_bypass(self):
        dead = RedisSlotCounter(create_redis("redis://127.0.0.1:1/0"))
        event_id = uuid4()

        assert await dead.try_acquire(event_id) is SlotResult.BYPASSED
        # el resto de operaciones no lanzan excepciones
        assert await dead.claim(event_id, uuid4()) is True  # sin Redis no se bloquea a nadie
        await dead.unclaim(event_id, uuid4())
        await dead.initialize(event_id, 1)
        await dead.release(event_id)
        await dead.reconcile(event_id, 1)
        await dead.invalidate(event_id)


class TestRedisCache:
    async def test_set_get_and_group_invalidation(self, redis_client):
        cache = RedisCache(redis_client)

        miss = await cache.get("events", "k")
        assert miss.value is None
        await cache.set("events", "k", miss.version, "valor", 60)
        assert (await cache.get("events", "k")).value == "valor"

        await cache.invalidate_group("events")

        assert (await cache.get("events", "k")).value is None

    async def test_groups_are_independent(self, redis_client):
        cache = RedisCache(redis_client)
        a, b = await cache.get("a", "k"), await cache.get("b", "k")
        await cache.set("a", "k", a.version, "A", 60)
        await cache.set("b", "k", b.version, "B", 60)

        await cache.invalidate_group("a")

        assert (await cache.get("a", "k")).value is None
        assert (await cache.get("b", "k")).value == "B"

    async def test_stale_write_after_invalidation_is_never_served(self, redis_client):
        cache = RedisCache(redis_client)
        stale = await cache.get("events", "k")
        await cache.invalidate_group("events")

        await cache.set(
            "events", "k", stale.version, "viejo", 60
        )  # escribe bajo la versión anterior

        assert (await cache.get("events", "k")).value is None

    async def test_values_expire(self, redis_client):
        cache = RedisCache(redis_client)
        lookup = await cache.get("events", "k")
        await cache.set("events", "k", lookup.version, "v", 1)
        await asyncio.sleep(1.2)
        assert (await cache.get("events", "k")).value is None

    async def test_unreachable_redis_behaves_like_an_empty_cache(self):
        dead = RedisCache(create_redis("redis://127.0.0.1:1/0"))

        lookup = await dead.get("events", "k")
        await dead.set("events", "k", lookup.version, "v", 60)
        await dead.invalidate_group("events")

        assert lookup.value is None
