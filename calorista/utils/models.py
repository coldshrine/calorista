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

@dataclass
class FoodEntry:
    date_int: str
    meal: str
    food_entry_name: str
    food_entry_description: str
    calories: float
    carbohydrate: float
    fat: float
    protein: float
    fiber: float | None = 0
    sugar: float | None = 0
    sodium: float | None = 0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FoodEntry":
        return cls(
            date_int=data["date_int"],
            meal=data["meal"],
            food_entry_name=data["food_entry_name"],
            food_entry_description=data["food_entry_description"],
            calories=float(data["calories"]),
            carbohydrate=float(data["carbohydrate"]),
            fat=float(data["fat"]),
            protein=float(data["protein"]),
            fiber=float(data.get("fiber") or 0),
            sugar=float(data.get("sugar") or 0),
            sodium=float(data.get("sodium") or 0),
        )
