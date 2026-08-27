import pytest
from telegram.notifier import TelegramNotifier


def test_telegram_unconfigured():
    notifier = TelegramNotifier(bot_token="", chat_id="")
    assert not notifier.is_configured

    # Sending messages when unconfigured should safely return False without raising exceptions
    assert not notifier.send_message("Test message")
    test_res = notifier.test_connection()
    assert not test_res["success"]


def test_telegram_authorization_security():
    authorized_chat_id = "123456789"
    notifier = TelegramNotifier(bot_token="FAKE_TOKEN", chat_id=authorized_chat_id)

    # Authorized user
    reply = notifier.handle_command(user_chat_id="123456789", command="/help")
    assert "LinkedIn Job Assistant" in reply
    assert "Access denied" not in reply

    # Unauthorized user
    unauth_reply = notifier.handle_command(user_chat_id="999999999", command="/help")
    assert unauth_reply == "Access denied."


def test_telegram_command_responses():
    notifier = TelegramNotifier(bot_token="FAKE_TOKEN", chat_id="12345")

    start_reply = notifier.handle_command("12345", "/start")
    assert "Bot connected successfully" in start_reply

    help_reply = notifier.handle_command("12345", "/help")
    assert "/status" in help_reply
    assert "/jobs" in help_reply

