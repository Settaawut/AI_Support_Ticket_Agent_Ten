"""Safe holding replies used whenever a draft cannot be trusted. No promises, no facts."""

from __future__ import annotations

from triage.models import Language

HOLDING_REPLY: dict[Language, str] = {
    Language.EN: (
        "Thank you for contacting us, and we're sorry for the trouble. We have received your "
        "request and passed it to the right specialist team, who will follow up with you "
        "directly."
    ),
    Language.TH: (
        "ขอบคุณที่ติดต่อเรา และขออภัยในความไม่สะดวกครับ เราได้รับเรื่องของคุณแล้ว "
        "และได้ส่งต่อให้ทีมผู้เชี่ยวชาญที่เกี่ยวข้องตรวจสอบ ทีมงานจะติดต่อกลับหาคุณโดยตรงครับ"
    ),
}


def holding_reply(language: Language) -> str:
    return HOLDING_REPLY.get(language, HOLDING_REPLY[Language.EN])
