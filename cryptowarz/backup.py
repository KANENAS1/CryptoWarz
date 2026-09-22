"""Taking your progress with you.

The save and the profile live in whatever browser or home directory you
happened to play in. That is fine until it isn't: a new phone, a cleared
cache, a different laptop, a copy of the page saved to disk - and the gear you
spent twenty runs earning is simply gone. Nothing in the game can rebuild it,
because the whole point of the anti-savescum design is that the game does not
trust anything it did not write itself.

So the game hands you the bytes. A backup is one line of text you can paste
anywhere: into a note, an email to yourself, another device, the terminal
version, the phone version. Both front ends read and write the same line, so a
run started in a browser can be finished in a terminal and the other way
round.

Three small decisions:

**It is text, not a file.** A file download is blocked or awkward in half the
places this game runs - a sandboxed frame, a page opened from disk, a phone
browser. A line you can select and copy works everywhere, and a file is still
offered where files work.

**It carries a checksum.** A half-copied paste that silently loaded would
overwrite a good profile with a broken one, which is the exact failure a backup
exists to prevent. A corrupted line is refused by name instead.

**It is not a cheat guard.** Anyone can decode and edit it - it is base64, not
a lock, and pretending otherwise would be theatre. What it protects is the
*leaderboard*, and that is protected where it always was: a run is ranked on
what the board can verify, and an imported profile brings its gear and its
history, not a score.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, Optional

#: Bumped only if the envelope changes. The payload inside carries its own
#: versions (save_version, the profile's version), which are checked by the
#: readers that already existed.
BACKUP_VERSION = 1
PREFIX = "CW1"


def fnv1a(text: str) -> int:
    """A 32-bit FNV-1a over the encoded payload.

    Chosen because it is four lines in every language, so the browser and the
    terminal cannot drift on it. It catches truncation and transcription, which
    is all a checksum here is for.
    """
    h = 0x811C9DC5
    for ch in text:
        h ^= ord(ch) & 0xFF
        h = (h * 0x01000193) & 0xFFFFFFFF
    return h


def encode(payload: Dict[str, Any]) -> str:
    """Wrap a payload as one pasteable line."""
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    body = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    return f"{PREFIX}.{fnv1a(body):08x}.{body}"


def decode(text: str) -> Dict[str, Any]:
    """Read a line back, or say exactly what is wrong with it."""
    cleaned = "".join(str(text).split())
    parts = cleaned.split(".")
    if len(parts) != 3 or parts[0] != PREFIX:
        raise ValueError("that doesn't look like a CryptoWarz backup line")
    _, checksum, body = parts
    if f"{fnv1a(body):08x}" != checksum.lower():
        raise ValueError("that backup is damaged or was only half copied - "
                         "copy the whole line, including the CW1 at the front")
    try:
        payload = json.loads(base64.b64decode(body.encode("ascii")).decode("utf-8"))
    except Exception as exc:                      # noqa: BLE001 - any failure is the same failure
        raise ValueError(f"that backup could not be read ({exc})")
    if not isinstance(payload, dict):
        raise ValueError("that backup is not a backup")
    return payload


def make(profile, save: Optional[Dict[str, Any]] = None,
         scores: Optional[list] = None) -> str:
    """A backup line for a profile, optionally with a run in progress."""
    payload: Dict[str, Any] = {
        "v": BACKUP_VERSION,
        "profile": profile.to_dict() if hasattr(profile, "to_dict") else dict(profile or {}),
    }
    if save:
        payload["save"] = save
    if scores:
        payload["scores"] = scores
    return encode(payload)


def read(text: str) -> Dict[str, Any]:
    """{profile, save, scores} from a backup line. Missing parts come back None.

    The profile is rebuilt through the normal reader, so a backup written by an
    older build migrates exactly the way a stored profile would - there is no
    second, more trusting path into the profile.
    """
    from .progress import Profile

    payload = decode(text)
    version = int(payload.get("v", 0))
    if version > BACKUP_VERSION:
        raise ValueError(f"that backup was written by a newer build "
                         f"(version {version}; this one reads {BACKUP_VERSION})")
    profile_data = payload.get("profile")
    profile = Profile.from_dict(profile_data) if profile_data else None
    return {"profile": profile, "save": payload.get("save"),
            "scores": payload.get("scores")}
