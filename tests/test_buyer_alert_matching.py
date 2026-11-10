"""Focused regression tests for saved-search matching."""
from types import SimpleNamespace
from buyer_alert_models import SavedVehicleSearch

def test_saved_search_matches_case_insensitively():
    search = SavedVehicleSearch(user_id=1, name="Nairobi Toyota", brand="toyota",
                                location="nairobi", max_price=2000000, min_year=2015)
    car = SimpleNamespace(brand="Toyota", location="Nairobi", price=1800000, year=2018)
    assert search.matches(car)

def test_saved_search_rejects_over_budget_and_old_cars():
    search = SavedVehicleSearch(user_id=1, name="Budget", max_price=1000000, min_year=2020)
    assert not search.matches(SimpleNamespace(brand="BMW", location="Nairobi", price=1500000, year=2022))
    assert not search.matches(SimpleNamespace(brand="BMW", location="Nairobi", price=900000, year=2018))

def test_saved_search_without_filters_matches_any_car():
    search = SavedVehicleSearch(user_id=1, name="Everything")
    assert search.matches(SimpleNamespace(brand="Audi", location="Mombasa", price=5000000, year=2010))
