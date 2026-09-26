from typing import List, Optional, Tuple
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from api.models.models import AudioScan, Verdict

class ScanRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_scan(
        self,
        impersonation_risk_score: float,
        verdict: Verdict,
        language: Optional[str] = None,
        audio_sha256: Optional[str] = None,
        spectral_features: dict = None,
        session_id: Optional[UUID] = None,
    ) -> AudioScan:
        scan = AudioScan(
            session_id=session_id,
            language=language,
            impersonation_risk_score=impersonation_risk_score,
            verdict=verdict,
            audio_sha256=audio_sha256,
            spectral_features=spectral_features or {},
        )
        self.session.add(scan)
        await self.session.commit()
        await self.session.refresh(scan)
        return scan

    async def get_history(
        self,
        limit: int = 20,
        cursor: Optional[UUID] = None,
        verdict: Optional[Verdict] = None,
        language: Optional[str] = None
    ) -> Tuple[List[AudioScan], Optional[UUID]]:
        query = select(AudioScan).order_by(AudioScan.scanned_at.desc(), AudioScan.id)
        
        if verdict:
            query = query.where(AudioScan.verdict == verdict)
        if language:
            query = query.where(AudioScan.language == language)
            
        if cursor:
            # Simple cursor implementation using scanned_at would be better, but UUID requires a subquery or join for accurate cursor pagination.
            # Assuming cursor is the ID of the last seen scan.
            # To do cursor pagination correctly, we need the scanned_at of the cursor.
            cursor_scan = await self.session.get(AudioScan, cursor)
            if cursor_scan:
                query = query.where(
                    (AudioScan.scanned_at < cursor_scan.scanned_at) |
                    ((AudioScan.scanned_at == cursor_scan.scanned_at) & (AudioScan.id > cursor_scan.id))
                )
                
        query = query.limit(limit)
        result = await self.session.execute(query)
        scans = result.scalars().all()
        
        next_cursor = scans[-1].id if scans else None
        return list(scans), next_cursor
