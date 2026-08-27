import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from config import user_settings
from database.database import SessionLocal
from database.models import Application, JobListing, ApplicationStatus
from browser.linkedin_browser import browser_manager
from application.form_detector import form_detector
from application.form_filler import form_filler
from application.resume_upload import resume_manager
from telegram.notifier import telegram_notifier

logger = logging.getLogger("workflow")


class ApplicationWorkflow:
    """Coordinates the human-in-the-loop application preparation workflow."""

    async def prepare_application(self, job_url_or_id: str) -> Dict[str, Any]:
        """
        Opens the job in LinkedIn, triggers Easy Apply, fills standard fields and resume,
        and pauses before the final submission for manual user inspection.
        """
        db = SessionLocal()
        try:
            # 1. Look up job from JobListing or Application
            job_listing = db.query(JobListing).filter(
                (JobListing.url == job_url_or_id) | (JobListing.job_id == job_url_or_id)
            ).first()

            app_record = db.query(Application).filter(Application.job_url == job_url_or_id).first()

            job_title = (job_listing.title if job_listing else None) or (app_record.job_title if app_record else "Target Position")
            company = (job_listing.company if job_listing else None) or (app_record.company if app_record else "Company")
            location = (job_listing.location if job_listing else None) or (app_record.location if app_record else "Location")
            job_url = (job_listing.url if job_listing else None) or (app_record.job_url if app_record else job_url_or_id)
            description = (job_listing.description if job_listing else None) or (app_record.job_description if app_record else "")
            match_score = (job_listing.match_score if job_listing else 0.0) or (app_record.match_score if app_record else 0.0)

            # Ensure Application record exists in DB
            if not app_record:
                app_record = Application(
                    job_title=job_title,
                    company=company,
                    location=location,
                    job_url=job_url,
                    job_description=description,
                    match_score=match_score,
                    application_status=ApplicationStatus.REVIEWING,
                    resume_used=user_settings.preferences.resume_path
                )
                db.add(app_record)
                db.commit()
                db.refresh(app_record)
            else:
                app_record.application_status = ApplicationStatus.REVIEWING
                db.commit()

            job_info = {
                "title": job_title,
                "company": company,
                "location": location,
                "url": job_url,
                "description": description,
                "match_score": match_score
            }

            # 2. Check Browser Status
            if not browser_manager.is_running:
                start_res = await browser_manager.start(headless=False)
                if not start_res["success"]:
                    return {
                        "success": False,
                        "message": f"Browser could not be started: {start_res.get('message')}",
                        "application": app_record.to_dict()
                    }

            page = await browser_manager.get_page()
            if not page:
                return {"success": False, "message": "Failed to acquire browser page."}

            # 3. Navigate to Job URL
            browser_manager.set_status(f"Opening job: {job_title} at {company}", "Preparing Application")
            nav_success = await browser_manager.navigate_to(job_url)
            if not nav_success:
                return {
                    "success": False,
                    "message": "Navigation paused or failed (check browser for login / security verification).",
                    "application": app_record.to_dict()
                }

            # 4. Check for Easy Apply Button
            await asyncio.sleep(2)
            apply_btn = await page.query_selector(
                "button.jobs-apply-button, button:has-text('Easy Apply'), div.jobs-apply-button--top-card button"
            )

            actions_summary = []
            if apply_btn:
                btn_text = (await apply_btn.inner_text()).strip()
                logger.info(f"Clicking apply button: '{btn_text}'")
                await apply_btn.click()
                await asyncio.sleep(2)

                # 5. Multi-Step Form Filling Loop
                max_steps = 6
                last_form = None
                for step in range(max_steps):
                    logger.info(f"Processing application step {step + 1}...")
                    form_state, step_actions = await form_filler.fill_current_step(
                        page=page,
                        job_info=job_info,
                        profile=user_settings.profile
                    )
                    actions_summary.extend(step_actions)
                    last_form = form_state

                    # Check if at final submit screen
                    advanced, reason = await form_filler.click_next_step(page)
                    if not advanced or reason == "FINAL_SUBMIT_REACHED":
                        logger.info(f"Step loop finished: {reason}")
                        break

                # 6. Mark Application as Ready for Review in DB
                app_record.application_status = ApplicationStatus.READY_TO_SUBMIT
                app_record.notes = f"Prepared automatically on {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')}. " + "; ".join(actions_summary)
                if last_form:
                    app_record.form_data = json.dumps([f.dict() for f in last_form.fields])
                db.commit()
                db.refresh(app_record)

                # 7. Notify via Telegram
                telegram_notifier.notify_application_ready(
                    application=app_record.to_dict(),
                    notes="Application paused before final submission. Please review and submit manually in browser."
                )

                browser_manager.set_status(
                    "Application prepared! PAUSED for manual user review and final submission in browser.",
                    "PAUSED - Ready for Review"
                )

                return {
                    "success": True,
                    "message": "Application prepared successfully. Automation has paused before final submission.",
                    "application": app_record.to_dict(),
                    "actions": actions_summary,
                    "paused_for_review": True
                }

            else:
                # Direct apply external link or already applied
                logger.info("Easy Apply button not directly found on page. Might be external application or already applied.")
                app_record.application_status = ApplicationStatus.REVIEWING
                app_record.notes = "Opened job page. Please inspect application options in the browser."
                db.commit()
                db.refresh(app_record)

                browser_manager.set_status("Job page opened. Check browser to continue application.", "Reviewing")

                return {
                    "success": True,
                    "message": "Job page opened. Easy Apply modal not auto-triggered; please review in browser.",
                    "application": app_record.to_dict(),
                    "actions": ["Opened job page in browser"],
                    "paused_for_review": True
                }

        except Exception as e:
            logger.error(f"Error in prepare_application workflow: {e}")
            telegram_notifier.notify_error("application/workflow.py", str(e))
            return {
                "success": False,
                "message": f"Error preparing application: {str(e)}"
            }
        finally:
            db.close()

    def mark_applied(self, application_id: int, notes: Optional[str] = None) -> Dict[str, Any]:
        """Marks an application as APPLIED in SQLite and sends Telegram notification."""
        db = SessionLocal()
        try:
            app_record = db.query(Application).filter(Application.id == application_id).first()
            if not app_record:
                return {"success": False, "message": "Application record not found."}

            app_record.application_status = ApplicationStatus.APPLIED
            app_record.date_applied = datetime.utcnow()
            if notes:
                app_record.notes = (app_record.notes or "") + f"\nUser Note: {notes}"

            db.commit()
            db.refresh(app_record)

            # Send Telegram notification
            telegram_notifier.notify_application_submitted(
                application=app_record.to_dict(),
                date_applied=app_record.date_applied.strftime("%d %b %Y")
            )

            browser_manager.set_status(f"Application marked as APPLIED: {app_record.job_title}", "Ready")

            return {
                "success": True,
                "message": "Application status updated to APPLIED.",
                "application": app_record.to_dict()
            }
        except Exception as e:
            db.rollback()
            logger.error(f"Error marking application applied: {e}")
            return {"success": False, "message": str(e)}
        finally:
            db.close()


# Global singleton workflow instance
application_workflow = ApplicationWorkflow()

