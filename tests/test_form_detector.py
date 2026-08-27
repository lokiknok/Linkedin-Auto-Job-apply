import pytest
from application.form_detector import classify_field_label
from application.form_filler import form_filler
from config import UserProfile


def test_classify_standard_fields():
    # Email
    assert classify_field_label("Email Address") == "email"
    assert classify_field_label("Your work email") == "email"

    # Phone
    assert classify_field_label("Phone number") == "phone"
    assert classify_field_label("Mobile phone") == "phone"

    # First & Last Name
    assert classify_field_label("First name") == "first_name"
    assert classify_field_label("Last name") == "last_name"
    assert classify_field_label("Full name") == "full_name"

    # Location
    assert classify_field_label("City") == "city"
    assert classify_field_label("Country") == "country"

    # URLs
    assert classify_field_label("LinkedIn Profile URL") == "linkedin_url"
    assert classify_field_label("Website / Portfolio") == "portfolio_url"


def test_unmapped_custom_questions():
    # Questions that should NOT be classified as standard fields
    assert classify_field_label("Why do you want to work for our team?") is None
    assert classify_field_label("Describe your experience with PyTorch models") is None
    assert classify_field_label("What is your expected salary?") is None


def test_form_filler_value_mapping():
    profile = UserProfile(
        first_name="Jane",
        last_name="Doe",
        email="jane.doe@example.com",
        phone="+91 9998887776",
        linkedin_url="https://linkedin.com/in/janedoe",
        location_city="Chennai"
    )

    mapping = form_filler.get_field_value_mapping(profile)
    assert mapping["first_name"] == "Jane"
    assert mapping["last_name"] == "Doe"
    assert mapping["full_name"] == "Jane Doe"
    assert mapping["email"] == "jane.doe@example.com"
    assert mapping["phone"] == "+91 9998887776"
    assert mapping["city"] == "Chennai"

