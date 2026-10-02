"""
api/repositories/scan_repository.py — Database access for AudioScan records.

Design decisions
----------------
* ``create_scan`` does NOT call ``session.commit()``.  The transaction is
  owned by the ``get_db()`` context manager in ``api/core/database.py``,
  which commits on clean exit and rolls back on exception.  A second
  ``commit()`` here would cause an extra Postgres round-trip and could
  surface confusing "session already committed" state on error.

* Cursor pagination encodes ``(scanned_at_iso, id_str)`` as a URL-safe
  base64 JSON string.  This eliminates the extra ``SELECT * WHERE id = $1``
  lookup that the previous implementation required on every paginated page.
  Old UUID-format cursors are no longer valid; callers restart from page 1.

* ``next_cursor`` is ``None`` when the returned page is smaller than
  ``limit`` — indicating that this is the last page and no further request
  is needed.  Previously it was always set to the last item's ID, which
  caused the UI to display a "Load More" button that returned an empty page.
"""

from __future__ import annotations

import base64
import json
from typing import List, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.models import AudioScan, Verdict


class ScanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    # ── Write ─────────────────────────────────────────────────────────────

    async def create_scan(
        self,
        impersonation_risk_score: float,
        verdict: Verdict,
        language: Optional[str] = None,
        audio_sha256: Optional[str] = None,
        spectral_features: dict = None,
        session_id=None,
    ) -> AudioScan:
        """
        Persist a new scan record.

        Does NOT commit — the ``get_db()`` dependency owns the transaction.
        Calling ``commit()`` here would result in two Postgres round-trips
        per request (one here, one in ``get_db``'s finally block).
        """
        scan = AudioScan(
            session_id=session_id,
            language=language,
            impersonation_risk_score=impersonation_risk_score,
            verdict=verdict,
            audio_sha256=audio_sha256,
            spectral_features=spectral_features or {},
        )
        self.session.add(scan)
        # flush() makes the new row visible within the current session so that
        # refresh() can populate server-generated fields (e.g. scanned_at).
        # The actual COMMIT is deferred to get_db().
        await self.session.flush()
        await self.session.refresh(scan)
        return scan

    # ── Read ──────────────────────────────────────────────────────────────

    async def get_history(
        self,
        limit: int = 20,
        cursor: Optional[str] = None,
        verdict: Optional[Verdict] = None,
        language: Optional[str] = None,
    ) -> Tuple[List[AudioScan], Optional[str]]:
        """
        Return a cursor-paginated list of scans (newest first).

        Cursor format
        -------------
        The cursor is a URL-safe base64-encoded JSON string encoding
        ``[scanned_at_isoformat, id_str]`` from the last seen item.
        This avoids a separate ``SELECT`` to resolve the cursor's position —
        all information needed for the WHERE clause is in the cursor itself.

        Returns
        -------
        (scans, next_cursor)
            ``next_cursor`` is ``None`` when this is the last page
            (i.e. fewer than ``limit`` rows were returned).
        """
        query = select(AudioScan).order_by(
            AudioScan.scanned_at.desc(), AudioScan.id
        )

        if verdict:
            query = query.where(AudioScan.verdict == verdict)
        if language:
            query = query.where(AudioScan.language == language)

        if cursor:
            try:
                scanned_at_str, id_str = json.loads(
                    base64.urlsafe_b64decode(cursor.encode()).decode()
                )
                # Include rows that are strictly older, OR same timestamp
                # but with a larger ID (tie-break for rows inserted in the
                # same second).
                from datetime import datetime, timezone
                cursor_time = datetime.fromisoformat(scanned_at_str)
                from uuid import UUID
                cursor_id = UUID(id_str)
                query = query.where(
                    (AudioScan.scanned_at < cursor_time)
                    | (
                        (AudioScan.scanned_at == cursor_time)
                        & (AudioScan.id > cursor_id)
                    )
                )
            except Exception:
                # Malformed or stale cursor — silently start from page 1.
                pass

        query = query.limit(limit)
        result = await self.session.execute(query)
        scans = list(result.scalars().all())

        # Only provide next_cursor when a full page was returned.
        # A partial page means we are on the last page — no more data follows.
        next_cursor: Optional[str] = None
        if len(scans) == limit:
            last = scans[-1]
            payload = json.dumps(
                [last.scanned_at.isoformat(), str(last.id)]
            ).encode()
            next_cursor = base64.urlsafe_b64encode(payload).decode()

        return scans, next_cursor
