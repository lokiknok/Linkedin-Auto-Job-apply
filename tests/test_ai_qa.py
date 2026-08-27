import pytest
from ai.question_answerer import AIQuestionAnswerer, AnswerSuggestion
from config import UserProfile


@pytest.mark.asyncio
async def test_exact_custom_qa_matching():
    answerer = AIQuestionAnswerer()
    profile = UserProfile(
        custom_qa={
            "What is your expected salary?": "12 LPA",
            "Are you willing to relocate?": "Yes, absolutely."
        }
    )

    resp = await answerer.answer_question("What is your expected salary?", profile=profile)
    assert resp.suggested_answer == "12 LPA"
    assert resp.confidence >= 0.95


@pytest.mark.asyncio
async def test_heuristic_work_authorization():
    answerer = AIQuestionAnswerer()
    profile = UserProfile(years_of_experience=3)

    resp = await answerer.answer_question("Are you legally authorized to work in this country?", profile=profile)
    assert resp.suggested_answer == "Yes"
    assert resp.confidence >= 0.90

    resp_sponsorship = await answerer.answer_question("Will you require visa sponsorship?", profile=profile)
    assert resp_sponsorship.suggested_answer == "No"
    assert resp_sponsorship.confidence >= 0.90


@pytest.mark.asyncio
async def test_heuristic_years_of_experience():
    answerer = AIQuestionAnswerer()
    profile = UserProfile(years_of_experience=4)

    resp = await answerer.answer_question("How many years of experience do you have with Python?", profile=profile)
    assert resp.suggested_answer == "4"
    assert resp.confidence >= 0.80


@pytest.mark.asyncio
async def test_unknown_question_confidence():
    answerer = AIQuestionAnswerer()
    profile = UserProfile()

    resp = await answerer.answer_question("What is your favorite chess opening and why?", profile=profile)
    assert resp.confidence < 0.50


def test_gemini_configuration_detection():
    # Test unconfigured
    answerer_none = AIQuestionAnswerer(gemini_api_key="", openai_api_key="")
    assert not answerer_none.is_gemini_configured
    assert not answerer_none.is_openai_configured
    assert not answerer_none.is_configured

    # Test Gemini configured
    answerer_gemini = AIQuestionAnswerer(gemini_api_key="AIzaSyFakeGeminiKey123", openai_api_key="")
    assert answerer_gemini.is_gemini_configured
    assert not answerer_gemini.is_openai_configured
    assert answerer_gemini.is_configured


