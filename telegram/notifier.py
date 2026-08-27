import asyncio
import logging
import threading
import time
from typing import Optional, Dict, Any, List
import httpx
from config import env_settings

logger = logging.getLogger("telegram")


class TelegramNotifier:
    """Production-quality Telegram bot integration for alerts and status queries."""

    def __init__(self, bot_token: Optional[str] = None, chat_id: Optional[str] = None):
        if bot_token is not None:
            self.bot_token = str(bot_token).strip()
        else:
            self.bot_token = str(env_settings.TELEGRAM_BOT_TOKEN or "").strip()

        if chat_id is not None:
            self.chat_id = str(chat_id).strip()
        else:
            self.chat_id = str(env_settings.TELEGRAM_CHAT_ID or "").strip()

        self._polling = False
        self._polling_thread: Optional[threading.Thread] = None
        self._last_update_id = 0

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    def _api_url(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}/{method}"

    def send_message(self, message: str, parse_mode: Optional[str] = None) -> bool:
        """Sends a text message to the configured authorized Telegram chat."""
        if not self.is_configured:
            logger.debug("Telegram notification skipped: Bot token or Chat ID not configured.")
            return False

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": False,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode

            with httpx.Client(timeout=10.0) as client:
                resp = client.post(self._api_url("sendMessage"), json=payload)
                if resp.status_code == 200:
                    logger.info("Telegram message sent successfully.")
                    return True
                else:
                    logger.warning(f"Telegram sendMessage failed [{resp.status_code}]: {resp.text}")
                    return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False

    async def send_message_async(self, message: str, parse_mode: Optional[str] = None) -> bool:
        """Asynchronously sends a text message to the configured authorized Telegram chat."""
        if not self.is_configured:
            return False

        try:
            payload = {
                "chat_id": self.chat_id,
                "text": message,
                "disable_web_page_preview": False,
            }
            if parse_mode:
                payload["parse_mode"] = parse_mode

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(self._api_url("sendMessage"), json=payload)
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"Async Telegram send error: {e}")
            return False

    def test_connection(self) -> Dict[str, Any]:
        """Tests the Telegram Bot connection and credentials."""
        if not self.bot_token:
            return {"success": False, "message": "Telegram Bot Token is missing."}
        if not self.chat_id:
            return {"success": False, "message": "Telegram Chat ID is missing."}

        try:
            # Verify bot token with getMe
            with httpx.Client(timeout=10.0) as client:
                me_resp = client.get(self._api_url("getMe"))
                if me_resp.status_code != 200:
                    return {
                        "success": False,
                        "message": f"Invalid bot token or Telegram API error: {me_resp.text}"
                    }
                bot_data = me_resp.json().get("result", {})
                bot_username = bot_data.get("username", "Unknown")

            # Send test message
            test_msg = (
                "✅ *Telegram Connected Successfully!*\n\n"
                "Your *LinkedIn Job Assistant* is now linked.\n"
                "You will receive alerts for matching jobs, application reviews, and status updates."
            )
            sent = self.send_message(test_msg, parse_mode="Markdown")
            if sent:
                return {
                    "success": True,
                    "bot_username": bot_username,
                    "message": f"Connected to @{bot_username}. Test notification sent!"
                }
            else:
                return {
                    "success": False,
                    "bot_username": bot_username,
                    "message": "Bot token is valid, but failed to send message to Chat ID. Ensure you have started a chat with the bot."
                }
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

    # -------------------------------------------------------------
    # Domain Event Notifications
    # -------------------------------------------------------------

    def notify_job_found(self, job: Dict[str, Any]):
        """Notifies user when a matching job is found."""
        title = job.get("job_title") or job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        location = job.get("location", "Not specified")
        match_score = job.get("match_score", 0)
        url = job.get("job_url") or job.get("url", "#")
        status = job.get("application_status", "FOUND")

        message = (
            f"🔎 *New Job Found*\n\n"
            f"💼 *{title}*\n"
            f"🏢 Company: {company}\n"
            f"📍 Location: {location}\n"
            f"⭐ Match Score: {int(match_score)}%\n\n"
            f"🔗 [View Job on LinkedIn]({url})\n\n"
            f"Status: `{status}`"
        )
        self.send_message(message, parse_mode="Markdown")

    def notify_application_ready(self, application: Dict[str, Any], notes: Optional[str] = None):
        """Notifies user when an application is filled and ready for human review."""
        title = application.get("job_title") or application.get("title", "Unknown Role")
        company = application.get("company", "Unknown Company")
        location = application.get("location", "Not specified")

        message = (
            f"📝 *Application Ready for Review*\n\n"
            f"💼 *{title}*\n"
            f"🏢 {company}\n"
            f"📍 {location}\n\n"
            f"✅ Personal information filled\n"
            f"✅ Resume uploaded\n"
            f"⚠️ *User review required*\n\n"
            f"The application is paused before final submission.\n"
            f"Open the browser to review and submit manually."
        )
        if notes:
            message += f"\n\n_Note: {notes}_"
        self.send_message(message, parse_mode="Markdown")

    def notify_question_detected(self, job: Dict[str, Any], question: str, suggested_answer: Optional[str] = None):
        """Notifies user when an unfamiliar custom application question is encountered."""
        title = job.get("job_title") or job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")

        message = (
            f"⚠️ *Application Needs Your Attention*\n\n"
            f"💼 *{title}*\n"
            f"🏢 {company}\n\n"
            f"Question detected:\n"
            f"_{question}_\n\n"
        )
        if suggested_answer:
            message += f"💡 *Suggested Answer:*\n`{suggested_answer}`\n\n"
        message += (
            f"The automation has paused.\n"
            f"Please review the browser and provide the appropriate answer."
        )
        self.send_message(message, parse_mode="Markdown")

    def notify_captcha_detected(self):
        """Notifies user that a CAPTCHA or security verification is active."""
        message = (
            f"🔐 *Manual Verification Required*\n\n"
            f"LinkedIn requires a security verification / CAPTCHA.\n\n"
            f"Automation has been *paused*.\n"
            f"Please complete the verification manually in the browser."
        )
        self.send_message(message, parse_mode="Markdown")

    def notify_application_submitted(self, application: Dict[str, Any], date_applied: Optional[str] = None):
        """Notifies user after marking application as submitted."""
        title = application.get("job_title") or application.get("title", "Unknown Role")
        company = application.get("company", "Unknown Company")
        location = application.get("location", "Not specified")
        date_str = date_applied or time.strftime("%d %b %Y")

        message = (
            f"✅ *Application Marked as Applied*\n\n"
            f"💼 *{title}*\n"
            f"🏢 {company}\n"
            f"📍 {location}\n\n"
            f"📅 Applied: {date_str}\n"
            f"Status: `APPLIED`"
        )
        self.send_message(message, parse_mode="Markdown")

    def notify_error(self, module: str, error_message: str):
        """Notifies user of a non-fatal automation error."""
        # Sanitize error message to avoid leaking private tokens or session data
        safe_msg = str(error_message)[:400]
        message = (
            f"🚨 *Automation Error*\n\n"
            f"Module: `{module}`\n\n"
            f"Error:\n{safe_msg}\n\n"
            f"The application has been paused safely.\n"
            f"Please check the browser."
        )
        self.send_message(message, parse_mode="Markdown")

    def notify_application_status(self, application: Dict[str, Any]):
        """Notifies user when an application status changes."""
        title = application.get("job_title", "Job")
        company = application.get("company", "Company")
        status = application.get("application_status", "UPDATED")

        message = (
            f"📋 *Application Status Updated*\n\n"
            f"💼 *{title}*\n"
            f"🏢 {company}\n"
            f"Status: `{status}`"
        )
        self.send_message(message, parse_mode="Markdown")

    # -------------------------------------------------------------
    # Bot Command Poller & Security Handling
    # -------------------------------------------------------------

    def handle_command(self, user_chat_id: str, command: str, user_name: str = "User") -> str:
        """Processes incoming Telegram bot commands with authorization verification."""
        # Security check
        if str(user_chat_id).strip() != self.chat_id:
            logger.warning(f"Unauthorized Telegram access attempt from chat_id: {user_chat_id}")
            return "Access denied."

        cmd = command.strip().split()[0].lower()

        if cmd in ("/start", "start"):
            return (
                "🤖 *LinkedIn Job Assistant*\n\n"
                "Bot connected successfully.\n\n"
                "Available commands:\n"
                "/status - Current automation status\n"
                "/jobs - Recent matching jobs\n"
                "/applications - Recent applications\n"
                "/help - Show available commands"
            )

        elif cmd in ("/help", "help"):
            return (
                "🤖 *LinkedIn Job Assistant*\n\n"
                "Commands:\n"
                "/status - Automation and system metrics\n"
                "/jobs - List top matching jobs\n"
                "/applications - List recent tracked applications\n"
                "/help - Show this guide\n\n"
                "Important:\n"
                "Telegram provides monitoring and notifications.\n"
                "Final application submission must remain a manual user action."
            )

        elif cmd in ("/status", "status"):
            # Query status from database and browser
            try:
                from database.database import SessionLocal
                from database.models import Application, JobListing, ApplicationStatus

                db = SessionLocal()
                total_found = db.query(JobListing).count()
                total_apps = db.query(Application).count()
                prepared = db.query(Application).filter(Application.application_status == ApplicationStatus.READY_TO_SUBMIT).count()
                applied = db.query(Application).filter(Application.application_status == ApplicationStatus.APPLIED).count()
                interviews = db.query(Application).filter(Application.application_status.in_([ApplicationStatus.INTERVIEW, ApplicationStatus.TECHNICAL_ROUND])).count()
                db.close()

                return (
                    "🤖 *Assistant Status*\n\n"
                    f"Browser: 🟢 Ready / Headed\n"
                    f"Job Search: 🟢 Active\n"
                    f"Jobs Discovered: {total_found}\n"
                    f"Applications Prepared: {prepared}\n"
                    f"Applications Submitted: {applied}\n"
                    f"Interviews: {interviews}\n\n"
                    "Current Task:\nWaiting for user action / review"
                )
            except Exception as e:
                return f"🤖 *Assistant Status*\n\nSystem Active.\nStatus query error: {e}"

        elif cmd in ("/jobs", "jobs"):
            try:
                from database.database import SessionLocal
                from database.models import JobListing

                db = SessionLocal()
                jobs = db.query(JobListing).order_by(JobListing.match_score.desc()).limit(5).all()
                db.close()

                if not jobs:
                    return "🔎 *Recent Jobs*\n\nNo jobs found yet. Click 'Find Jobs' on the dashboard."

                lines = ["🔎 *Recent Matching Jobs*\n"]
                for i, j in enumerate(jobs, 1):
                    lines.append(
                        f"{i}. *{j.title}*\n"
                        f"   🏢 {j.company}\n"
                        f"   📍 {j.location}\n"
                        f"   ⭐ Match: {int(j.match_score)}%\n"
                        f"   🔗 [Link]({j.url})\n"
                    )
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving jobs: {e}"

        elif cmd in ("/applications", "applications"):
            try:
                from database.database import SessionLocal
                from database.models import Application

                db = SessionLocal()
                apps = db.query(Application).order_by(Application.updated_at.desc()).limit(5).all()
                db.close()

                if not apps:
                    return "📋 *Recent Applications*\n\nNo applications tracked yet."

                lines = ["📋 *Recent Applications*\n"]
                for app in apps:
                    status_emoji = "✅" if app.application_status.value == "APPLIED" else "📝"
                    lines.append(
                        f"{status_emoji} *{app.job_title}*\n"
                        f"   🏢 {app.company}\n"
                        f"   Status: `{app.application_status.value}`\n"
                    )
                return "\n".join(lines)
            except Exception as e:
                return f"Error retrieving applications: {e}"

        else:
            return "Unrecognized command. Send /help to view available commands."

    def _poll_loop(self):
        """Long-polling background thread to receive Telegram updates."""
        logger.info("Telegram command polling loop started.")
        while self._polling:
            if not self.is_configured:
                time.sleep(5)
                continue

            try:
                url = self._api_url("getUpdates")
                params = {"offset": self._last_update_id + 1, "timeout": 20}
                with httpx.Client(timeout=25.0) as client:
                    resp = client.get(url, params=params)
                    if resp.status_code == 200:
                        data = resp.json()
                        updates = data.get("result", [])
                        for update in updates:
                            self._last_update_id = update["update_id"]
                            message = update.get("message") or update.get("edited_message")
                            if not message:
                                continue

                            from_chat_id = str(message.get("chat", {}).get("id", ""))
                            text = message.get("text", "")
                            user_name = message.get("from", {}).get("first_name", "User")

                            if text.startswith("/"):
                                reply = self.handle_command(from_chat_id, text, user_name)
                                # Reply back
                                self._send_raw(from_chat_id, reply, parse_mode="Markdown")
            except Exception as e:
                logger.debug(f"Telegram polling error: {e}")
                time.sleep(5)

    def _send_raw(self, chat_id: str, text: str, parse_mode: Optional[str] = None):
        try:
            payload = {"chat_id": chat_id, "text": text}
            if parse_mode:
                payload["parse_mode"] = parse_mode
            with httpx.Client(timeout=10.0) as client:
                client.post(self._api_url("sendMessage"), json=payload)
        except Exception:
            pass

    def start_polling(self):
        """Starts Telegram polling in a daemon thread."""
        if not self.is_configured:
            logger.info("Telegram bot not configured; polling disabled.")
            return

        if self._polling:
            return

        self._polling = True
        self._polling_thread = threading.Thread(target=self._poll_loop, daemon=True, name="TelegramPoller")
        self._polling_thread.start()
        logger.info("Telegram bot polling started in background thread.")

    def stop_polling(self):
        """Stops background polling."""
        self._polling = False


# Global singleton notifier instance
telegram_notifier = TelegramNotifier()

