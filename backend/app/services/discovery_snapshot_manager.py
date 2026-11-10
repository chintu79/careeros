import json
import logging
import time
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Tuple
from sqlalchemy import text
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert as pg_insert

from backend.app.models.discovery_ranking_snapshot import DiscoveryRankingSnapshot
from backend.app.services.intelligence_cache import ranking_snapshot_cache

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DistributedRankingSnapshotManager:
    """
    Two-tier distributed ranking snapshot manager:
    - Tier 1 (L1): Local in-memory LRU cache (ranking_snapshot_cache) for ultra-fast single-worker hits.
    - Tier 2 (L2): Shared PostgreSQL table (discovery_ranking_snapshots) for cross-worker sharing across independent processes.
    """
    def __init__(self, l1_cache=ranking_snapshot_cache, default_ttl_seconds: int = 120):
        self.l1_cache = l1_cache
        self.default_ttl = default_ttl_seconds

    def get_snapshot(
        self,
        snapshot_key: str,
        db: Session
    ) -> Optional[Tuple[List[int], int]]:
        if not snapshot_key:
            return None

        # 1. Check L1 in-memory cache
        l1_val = self.l1_cache.get(snapshot_key)
        if l1_val:
            return l1_val

        # 2. Check L2 PostgreSQL shared cache
        now = utc_now()
        row = (
            db.query(DiscoveryRankingSnapshot)
            .filter(
                DiscoveryRankingSnapshot.snapshot_key == snapshot_key,
                DiscoveryRankingSnapshot.expires_at > now
            )
            .first()
        )
        if row:
            snapshot_ids = row.snapshot_ids
            total_count = row.total_count
            res = (snapshot_ids, total_count)
            # Populate L1 cache for subsequent lookups on this worker
            ttl_remaining = max(1, int((row.expires_at - now).total_seconds()))
            self.l1_cache.set(snapshot_key, res, ttl=ttl_remaining)
            if row.snapshot_id:
                self.l1_cache.set(f"snap_id:{row.snapshot_id}", res, ttl=ttl_remaining)
            return res

        return None

    def get_snapshot_by_id(
        self,
        snapshot_id: str,
        db: Session,
        user_id: Optional[int] = None
    ) -> Optional[Tuple[List[int], int]]:
        """
        Retrieve an immutable pagination session snapshot directly by snapshot_id.
        Enforces candidate ownership and strict expiration even if present in L1 cache.
        """
        if not snapshot_id:
            return None

        now_ts = time.time()
        now = utc_now()

        # 1. Check L1 cache
        l1_val = self.l1_cache.get(f"snap_id:{snapshot_id}")
        if l1_val:
            if isinstance(l1_val, tuple) and len(l1_val) >= 4:
                snapshot_ids, total_count, owner_uid, exp_ts = l1_val[:4]
                # Enforce candidate isolation & ownership
                if user_id is not None and owner_uid is not None and owner_uid != user_id:
                    return None
                # Enforce expiration even if present in L1
                if now_ts > exp_ts:
                    self.l1_cache.delete(f"snap_id:{snapshot_id}")
                    return None
                return (snapshot_ids, total_count)
            elif isinstance(l1_val, tuple) and len(l1_val) == 2:
                return l1_val

        # 2. Check L2 PostgreSQL
        query = db.query(DiscoveryRankingSnapshot).filter(
            DiscoveryRankingSnapshot.snapshot_id == snapshot_id,
            DiscoveryRankingSnapshot.expires_at > now
        )
        if user_id is not None:
            query = query.filter(DiscoveryRankingSnapshot.user_id == user_id)

        row = query.first()
        if row:
            snapshot_ids = row.snapshot_ids
            total_count = row.total_count
            res = (snapshot_ids, total_count)
            ttl_remaining = max(1, int((row.expires_at - now).total_seconds()))
            meta = (snapshot_ids, total_count, row.user_id, time.time() + ttl_remaining)
            self.l1_cache.set(f"snap_id:{snapshot_id}", meta, ttl=ttl_remaining)
            if row.snapshot_key:
                self.l1_cache.set(row.snapshot_key, res, ttl=ttl_remaining)
            return res

        return None

    def set_snapshot(
        self,
        snapshot_key: str,
        user_id: int,
        signature: str,
        candidate_evidence_version: str,
        snapshot_ids: List[int],
        total_count: int,
        db: Session,
        snapshot_id: Optional[str] = None,
        ttl_seconds: Optional[int] = None
    ) -> str:
        """
        Persists a distributed ranking snapshot with session ID across L1 and L2 PostgreSQL.
        Enforces transactional cache coherence: L1 is updated ONLY AFTER L2 database commit succeeds.
        """
        if not snapshot_key:
            return ""

        resolved_snap_id = snapshot_id or f"snap_session_{uuid.uuid4().hex}"
        ttl = ttl_seconds or self.default_ttl
        now = utc_now()
        expires_at = now + timedelta(seconds=ttl)

        # 1. Store in L2 PostgreSQL shared cache via atomic upsert
        stmt = pg_insert(DiscoveryRankingSnapshot).values(
            snapshot_key=snapshot_key,
            snapshot_id=resolved_snap_id,
            user_id=user_id,
            signature=signature,
            candidate_evidence_version=candidate_evidence_version,
            total_count=total_count,
            snapshot_ids=snapshot_ids,
            created_at=now,
            expires_at=expires_at
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["snapshot_key"],
            set_={
                "snapshot_id": stmt.excluded.snapshot_id,
                "snapshot_ids": stmt.excluded.snapshot_ids,
                "total_count": stmt.excluded.total_count,
                "candidate_evidence_version": stmt.excluded.candidate_evidence_version,
                "created_at": stmt.excluded.created_at,
                "expires_at": stmt.excluded.expires_at
            }
        )
        try:
            db.execute(stmt)
            db.commit()
        except Exception as e:
            logger.warning(f"Failed to persist distributed ranking snapshot to L2 PostgreSQL: {e}")
            db.rollback()
            return resolved_snap_id

        # 2. Store in L1 cache ONLY after successful DB transaction commit
        self.l1_cache.set(snapshot_key, (snapshot_ids, total_count), ttl=ttl)
        meta = (snapshot_ids, total_count, user_id, time.time() + ttl)
        self.l1_cache.set(f"snap_id:{resolved_snap_id}", meta, ttl=ttl)

        return resolved_snap_id

    def invalidate_candidate_snapshots(self, user_id: int, db: Session, preserve_active_sessions: bool = True) -> int:
        """
        Advances the current candidate ranking generation when their profile changes.
        Preserves active pagination sessions (immutable, TTL-bound) so in-flight user browsing
        is not aborted, while invalidating current ranking generation for new searches.
        """
        if not user_id:
            return 0

        deleted_count = 0
        if not preserve_active_sessions:
            try:
                deleted_count = (
                    db.query(DiscoveryRankingSnapshot)
                    .filter(DiscoveryRankingSnapshot.user_id == user_id)
                    .delete(synchronize_session=False)
                )
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to delete L2 snapshots for user {user_id}: {e}")
                db.rollback()
                return 0
        else:
            try:
                # Invalidate search signatures in L2 so new searches compute fresh ranking generation,
                # while preserving active pagination sessions (accessible via snapshot_id).
                updated = db.execute(text("""
                    UPDATE discovery_ranking_snapshots
                    SET snapshot_key = 'session_only:' || snapshot_id
                    WHERE user_id = :uid AND snapshot_key LIKE 'snap:' || :uid || ':%';
                """), {"uid": user_id})
                db.commit()
                deleted_count = updated.rowcount
            except Exception as e:
                logger.warning(f"Failed to update L2 snapshot keys for user {user_id}: {e}")
                db.rollback()
                return 0

        # Invalidate L1 process-local entries for this candidate's search signatures
        prefix = f"snap:{user_id}:"
        with self.l1_cache._lock:
            keys_to_del = [k for k in self.l1_cache._cache.keys() if k.startswith(prefix)]
            for k in keys_to_del:
                del self.l1_cache._cache[k]

        return deleted_count

    def invalidate_opportunity_snapshots(self, opportunity_id: int, db: Session) -> int:
        """
        Invalidates ranking snapshots containing opportunity_id when the opportunity is modified.
        Uses PostgreSQL GIN index on snapshot_ids for fast array containment lookup.
        Transactional coherence: L1 cache cleared only upon successful DB commit.
        """
        if not opportunity_id:
            return 0
        deleted_count = 0
        try:
            deleted = db.execute(text("""
                DELETE FROM discovery_ranking_snapshots 
                WHERE CAST(snapshot_ids AS jsonb) @> CAST(:opp_json AS jsonb)
            """), {"opp_json": json.dumps([opportunity_id])}).rowcount
            db.commit()
            deleted_count = deleted
        except Exception as e:
            logger.warning(f"Failed to delete L2 snapshots for opp {opportunity_id}: {e}")
            db.rollback()
            return 0

        # Invalidate L1 cache entries only after successful DB commit
        self.l1_cache.clear()
        return deleted_count

    def cleanup_expired_snapshots(self, db: Session, batch_size: int = 500) -> int:
        """
        Prunes expired ranking snapshots from PostgreSQL in bounded non-blocking batches.
        Also purges expired entries from the L1 process-local cache.
        """
        now = utc_now()
        deleted_count = 0
        try:
            deleted = db.execute(text("""
                DELETE FROM discovery_ranking_snapshots
                WHERE snapshot_key IN (
                    SELECT snapshot_key FROM discovery_ranking_snapshots
                    WHERE expires_at <= :now
                    LIMIT :batch_size
                )
            """), {"now": now, "batch_size": batch_size}).rowcount
            db.commit()
            deleted_count = deleted
        except Exception as e:
            logger.warning(f"Failed to cleanup expired snapshots: {e}")
            db.rollback()

        # Prune expired entries from L1
        now_ts = time.time()
        with self.l1_cache._lock:
            expired_keys = [
                k for k, v in self.l1_cache._cache.items()
                if isinstance(v, tuple) and len(v) >= 4 and v[3] <= now_ts
            ]
            for k in expired_keys:
                del self.l1_cache._cache[k]

        return deleted_count

    def clear_all(self, db: Session) -> None:
        """Clear all snapshots across L1 and L2 (used in test setup)."""
        self.l1_cache.clear()
        try:
            db.query(DiscoveryRankingSnapshot).delete(synchronize_session=False)
            db.commit()
        except Exception:
            db.rollback()


snapshot_manager = DistributedRankingSnapshotManager()

