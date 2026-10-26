from __future__ import annotations

from backend.models.schemas import CountryIn
from backend.repositories import countries_repo
from backend.textutil import clip, norm_key


def list_countries(user_id: str) -> list[dict]:
    return countries_repo.list_for_user(user_id)


def _clean(body: CountryIn) -> tuple[str, str, str]:
    label = clip(body.label, 80)
    if not label:
        raise ValueError("Enter a country or market name.")
    return label, clip(body.location_line, 120), clip(body.phone, 40)


def _reject_duplicate(user_id: str, label: str, ignore_id: str = "") -> None:
    key = norm_key(label)
    for country in countries_repo.list_for_user(user_id):
        if country["id"] != ignore_id and norm_key(country["label"]) == key:
            raise ValueError("You already added that country.")


def create(user_id: str, body: CountryIn) -> dict:
    label, location_line, phone = _clean(body)
    _reject_duplicate(user_id, label)
    return countries_repo.create(user_id, label, location_line, phone)


def update(user_id: str, country_id: str, body: CountryIn) -> dict:
    if not countries_repo.get(user_id, country_id):
        raise ValueError("That country is not on your account.")
    label, location_line, phone = _clean(body)
    _reject_duplicate(user_id, label, ignore_id=country_id)
    countries_repo.update(user_id, country_id, label, location_line, phone)
    return {"id": country_id, "label": label, "location_line": location_line, "phone": phone}


def delete(user_id: str, country_id: str) -> None:
    from backend.services import resume_library_service

    if not countries_repo.get(user_id, country_id):
        raise ValueError("That country is not on your account.")
    resume_library_service.delete_for_country(user_id, country_id)
    countries_repo.delete(user_id, country_id)


def require(user_id: str, country_id: str) -> dict:
    country = countries_repo.get(user_id, country_id)
    if not country:
        raise ValueError("Choose a target country you have saved.")
    return country
