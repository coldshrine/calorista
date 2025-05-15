from dataclasses import dataclass
from typing import Any


@dataclass
class UserProfile:
    goal_weight_kg: float
    height_cm: float
    height_measure: str
    last_weight_kg: float
    weight_measure: str
    last_weight_date_int: str | None = None
    last_weight_comment: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UserProfile":
        return cls(
            goal_weight_kg=float(data["goal_weight_kg"]),
            height_cm=float(data["height_cm"]),
            height_measure=data["height_measure"],
            last_weight_kg=float(data["last_weight_kg"]),
            weight_measure=data["weight_measure"],
            last_weight_date_int=data.get("last_weight_date_int"),
            last_weight_comment=data.get("last_weight_comment"),
        )
