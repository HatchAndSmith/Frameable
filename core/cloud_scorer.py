import base64
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import cv2
import requests


_LIKELIHOOD = {
    "UNKNOWN": 0.0, "VERY_UNLIKELY": 0.05, "UNLIKELY": 0.2,
    "POSSIBLE": 0.5, "LIKELY": 0.8, "VERY_LIKELY": 1.0,
}
GOOGLE_MONTHLY_LIMIT = 1000


class UsageTracker:
    def __init__(self, config_dir: Path):
        self._path = config_dir / "api_usage.json"
        self._data = self._load()

    def _load(self) -> dict:
        month = datetime.now().strftime("%Y-%m")
        if self._path.exists():
            try:
                d = json.loads(self._path.read_text())
                if d.get("month") == month:
                    return d
            except Exception:
                pass
        return {"month": month, "google": 0}

    def _save(self):
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data))

    @property
    def google_used(self) -> int:
        return self._data.get("google", 0)

    @property
    def google_remaining(self) -> int:
        return max(0, GOOGLE_MONTHLY_LIMIT - self.google_used)

    def increment_google(self, n: int = 1):
        self._data["google"] = self.google_used + n
        self._save()

    def reset_google(self):
        self._data["google"] = 0
        self._save()


class CloudScorer:
    def __init__(self, config_dir: Path,
                 google_key: Optional[str] = None,
                 replicate_token: Optional[str] = None):
        self.tracker = UsageTracker(config_dir)
        self._google_key = google_key
        self._replicate_token = replicate_token

    @property
    def google_available(self) -> bool:
        return bool(self._google_key) and self.tracker.google_remaining > 0

    @property
    def replicate_available(self) -> bool:
        return bool(self._replicate_token)

    @property
    def any_available(self) -> bool:
        return self.google_available or self.replicate_available

    def active_service(self) -> str:
        if self.google_available:
            return "google"
        if self.replicate_available:
            return "replicate"
        return "offline"

    def score_frame(self, frame_bgr) -> dict:
        if self.google_available:
            return self._score_google(frame_bgr)
        if self.replicate_available:
            return self._score_replicate(frame_bgr)
        return {}

    def _score_google(self, frame_bgr) -> dict:
        _, buf = cv2.imencode(".jpg", frame_bgr, [cv2.IMWRITE_JPEG_QUALITY, 80])
        content = base64.b64encode(buf.tobytes()).decode()
        payload = {"requests": [{
            "image": {"content": content},
            "features": [{"type": "FACE_DETECTION", "maxResults": 10}],
        }]}
        url = f"https://vision.googleapis.com/v1/images:annotate?key={self._google_key}"
        try:
            resp = requests.post(url, json=payload, timeout=15)
            resp.raise_for_status()
            self.tracker.increment_google()
            return self._parse_google(resp.json())
        except Exception:
            return {}

    def _parse_google(self, data: dict) -> dict:
        faces = data.get("responses", [{}])[0].get("faceAnnotations", [])
        if not faces:
            return {"cloud_face_count": 0}
        dom = sorted(faces, key=lambda f: f.get("detectionConfidence", 0), reverse=True)[0]
        return {
            "cloud_face_count": len(faces),
            "cloud_joy": _LIKELIHOOD.get(dom.get("joyLikelihood", "UNKNOWN"), 0.0),
            "cloud_sorrow": _LIKELIHOOD.get(dom.get("sorrowLikelihood", "UNKNOWN"), 0.0),
            "cloud_surprise": _LIKELIHOOD.get(dom.get("surpriseLikelihood", "UNKNOWN"), 0.0),
            "cloud_blurred": _LIKELIHOOD.get(dom.get("blurredLikelihood", "UNKNOWN"), 0.0),
            "cloud_under_exposed": _LIKELIHOOD.get(dom.get("underExposedLikelihood", "UNKNOWN"), 0.0),
            "cloud_confidence": dom.get("detectionConfidence", 0.5),
        }

    def _score_replicate(self, frame_bgr) -> dict:
        try:
            import replicate
            import io
            from PIL import Image
            img_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(img_rgb)
            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=85)
            buf.seek(0)
            client = replicate.Client(api_token=self._replicate_token)
            output = client.run(
                "google-research/nima:pytorch-aesthetic-predictor",
                input={"image": buf},
            )
            score = float(output.get("mean_score", 5.0)) / 10.0
            return {"cloud_aesthetic": score}
        except Exception:
            return {}
