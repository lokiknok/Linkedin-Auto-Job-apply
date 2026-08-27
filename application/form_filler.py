import asyncio
import logging
import re
from typing import Dict, Any, Optional, List, Tuple
from config import UserProfile, user_settings
from application.form_detector import DetectedForm, DetectedField, form_detector
from application.resume_upload import resume_manager
from ai.question_answerer import question_answerer
from telegram.notifier import telegram_notifier

logger = logging.getLogger("form_filler")


class FormFiller:
    """Safely fills standard fields, attaches resume, answers mapped questions, and pauses before submission."""

    def get_field_value_mapping(self, profile: UserProfile) -> Dict[str, str]:
        """Returns standard dictionary mapping canonical names to user profile values."""
        return {
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "full_name": f"{profile.first_name} {profile.last_name}".strip(),
            "email": profile.email,
            "phone": profile.phone,
            "linkedin_url": profile.linkedin_url,
            "portfolio_url": profile.portfolio_url or "",
            "city": profile.location_city,
            "state": profile.location_state,
            "country": profile.location_country,
            "headline": profile.headline,
            "summary": profile.summary,
        }

    async def fill_current_step(
        self,
        page,
        job_info: Optional[Dict[str, Any]] = None,
        profile: Optional[UserProfile] = None
    ) -> Tuple[DetectedForm, List[str]]:
        """
        Detects fields on the current step and fills standard values safely.
        Returns the detected form status and a list of actions taken.
        """
        user_prof = profile or user_settings.profile
        value_map = self.get_field_value_mapping(user_prof)
        actions_taken = []

        # Detect form fields
        form = await form_detector.detect_form(page)

        # 1. Fill standard text fields
        for field in form.fields:
            if field.standard_name and field.standard_name in value_map:
                fill_val = value_map[field.standard_name]
                if fill_val:
                    success = await self._fill_text_input(page, field, fill_val)
                    if success:
                        field.filled = True
                        field.current_value = fill_val
                        actions_taken.append(f"Filled {field.label} ({field.standard_name})")

            # 2. Check for Resume field
            elif field.field_type == "file" or field.standard_name == "resume":
                uploaded = await resume_manager.upload_to_playwright_input(page)
                if uploaded:
                    field.filled = True
                    actions_taken.append("Attached resume PDF")

            # 3. Handle Custom Question if answerable via profile custom_qa or high-confidence AI
            elif field.is_custom_question and not field.current_value:
                # Ask AI / rule matcher for suggestion
                ai_resp = await question_answerer.answer_question(
                    question=field.label,
                    job_title=job_info.get("title") if job_info else None,
                    job_description=job_info.get("description") if job_info else None,
                    company=job_info.get("company") if job_info else None,
                    profile=user_prof
                )
                field.suggested_answer = ai_resp.suggested_answer

                # Auto-fill only if confidence is very high (>= 0.90) and matches options
                if ai_resp.confidence >= 0.90 and ai_resp.suggested_answer:
                    filled_custom = await self._fill_custom_field(page, field, ai_resp.suggested_answer)
                    if filled_custom:
                        field.filled = True
                        field.current_value = ai_resp.suggested_answer
                        actions_taken.append(f"Answered: '{field.label}' -> '{ai_resp.suggested_answer}'")
                else:
                    # Notify user of unfamiliar question
                    logger.info(f"Unfamiliar question requires user review: {field.label}")
                    if job_info:
                        telegram_notifier.notify_question_detected(
                            job_info,
                            field.label,
                            ai_resp.suggested_answer if ai_resp.suggested_answer else None
                        )

        return form, actions_taken

    async def _fill_text_input(self, page, field: DetectedField, value: str) -> bool:
        """Fills a standard text input field."""
        try:
            # Try by id
            selector = f"#{field.field_id}" if field.field_id and not field.field_id.startswith("text_") else None
            inp = await page.query_selector(selector) if selector else None

            if not inp:
                # Try finding by label or aria-label
                inp = await page.query_selector(f"input[aria-label*='{field.label}'], input[name='{field.field_id}']")

            if inp:
                # Clear and type
                await inp.fill("")
                await inp.type(value, delay=30)
                return True
            return False
        except Exception as e:
            logger.debug(f"Error filling text input '{field.label}': {e}")
            return False

    async def _fill_custom_field(self, page, field: DetectedField, answer: str) -> bool:
        """Attempts to fill radio, select, or text custom field with suggested answer."""
        try:
            if field.field_type == "radio":
                # Find matching radio label
                clean_ans = answer.lower().strip()
                labels = await page.query_selector_all("fieldset label")
                for lbl in labels:
                    lbl_text = (await lbl.inner_text()).lower().strip()
                    if clean_ans == lbl_text or (clean_ans == "yes" and "yes" in lbl_text) or (clean_ans == "no" and "no" in lbl_text):
                        await lbl.click()
                        return True

            elif field.field_type == "select":
                # Find select element
                sel = await page.query_selector(f"#{field.field_id}, select[aria-label*='{field.label}']")
                if sel:
                    clean_ans = answer.lower().strip()
                    for opt in field.options:
                        if clean_ans in opt.lower() or opt.lower() in clean_ans:
                            await sel.select_option(label=opt)
                            return True

            elif field.field_type in ("text", "textarea"):
                elem = await page.query_selector(f"#{field.field_id}, textarea[aria-label*='{field.label}'], input[aria-label*='{field.label}']")
                if elem:
                    await elem.fill(answer)
                    return True

            return False
        except Exception as e:
            logger.debug(f"Error filling custom field '{field.label}': {e}")
            return False

    async def click_next_step(self, page) -> Tuple[bool, str]:
        """
        Safely clicks Next/Continue in a multi-step modal.
        CRITICAL: Will NOT click 'Submit application'.
        """
        try:
            # Check for final submit button
            submit_btn = await page.query_selector(
                "button[aria-label*='Submit application'], button:has-text('Submit application')"
            )
            if submit_btn:
                logger.info("STOP: Final 'Submit application' button reached. Pausing for human review.")
                return False, "FINAL_SUBMIT_REACHED"

            # Check for Next / Continue button
            next_btn = await page.query_selector(
                "button[aria-label*='Continue to next step'], button:has-text('Next'), button[aria-label*='Review your application'], button:has-text('Review')"
            )
            if next_btn:
                btn_text = (await next_btn.inner_text()).strip()
                if "submit" in btn_text.lower():
                    logger.info("STOP: Submit button detected. Pausing for user review.")
                    return False, "FINAL_SUBMIT_REACHED"

                await next_btn.click()
                await asyncio.sleep(1.5)
                return True, f"Advanced step with '{btn_text}'"

            return False, "NO_NEXT_BUTTON"
        except Exception as e:
            logger.error(f"Error clicking next step: {e}")
            return False, f"ERROR: {e}"


form_filler = FormFiller()

