import logging
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel

logger = logging.getLogger("form_detector")


class DetectedField(BaseModel):
    field_id: str
    label: str
    field_type: str  # text, select, radio, checkbox, textarea, file
    standard_name: Optional[str] = None  # e.g., "email", "phone", "first_name", or None if custom question
    current_value: Optional[str] = None
    options: List[str] = []
    required: bool = False
    is_custom_question: bool = False
    suggested_answer: Optional[str] = None
    filled: bool = False


class DetectedForm(BaseModel):
    is_modal_open: bool = False
    current_step_title: Optional[str] = None
    fields: List[DetectedField] = []
    has_resume_field: bool = False
    has_unanswered_questions: bool = False
    is_final_step: bool = False
    next_button_text: Optional[str] = None


STANDARD_PATTERNS = {
    "first_name": [r"\bfirst\s*name\b", r"\bgiven\s*name\b", r"\bfname\b"],
    "last_name": [r"\blast\s*name\b", r"\bfamily\s*name\b", r"\bsurname\b", r"\blname\b"],
    "full_name": [r"\bfull\s*name\b", r"\bcomplete\s*name\b", r"\byour\s*name\b"],
    "email": [r"\bemail\b", r"\be-mail\b", r"\belectronic\s*mail\b"],
    "phone": [r"\bphone\b", r"\bmobile\b", r"\btelephone\b", r"\bcell\s*phone\b", r"\bcontact\s*number\b"],
    "linkedin_url": [r"\blinkedin\b", r"\blinkedin\s*profile\b", r"\bprofile\s*url\b"],
    "portfolio_url": [r"\bportfolio\b", r"\bwebsite\b", r"\bgithub\b", r"\bpersonal\s*site\b", r"\bblog\b"],
    "city": [r"\bcity\b", r"\blocation\s*\(city\)", r"\bcurrent\s*city\b"],
    "state": [r"\bstate\b", r"\bprovince\b", r"\bstate\s*/\s*province\b"],
    "country": [r"\bcountry\b", r"\bcountry\s*/\s*region\b"],
    "headline": [r"\bheadline\b"],
    "summary": [r"\bsummary\b", r"\babout\s*you\b"],
}


def classify_field_label(label_text: str, name_attr: str = "", id_attr: str = "") -> Optional[str]:
    """Identifies if a label/attribute corresponds to a recognized standard field."""
    tokens = [label_text.strip(), name_attr.strip(), id_attr.strip()]
    combined = " ".join([t for t in tokens if t]).lower()

    if not combined:
        return None

    for std_name, patterns in STANDARD_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, combined):
                return std_name
    return None


class FormDetector:
    """Inspects Playwright DOM elements inside LinkedIn Easy Apply modals or application pages."""

    async def detect_form(self, page) -> DetectedForm:
        """Inspects current page/modal and extracts all fields, steps, and buttons."""
        form = DetectedForm()

        try:
            # Check if Easy Apply modal is present
            modal = await page.query_selector(".jobs-easy-apply-modal, .jobs-easy-apply-content, div[role='dialog']")
            form.is_modal_open = modal is not None
            container = modal if modal else page

            # Check step header / title
            header_elem = await container.query_selector("h3, h2.t-16, .jobs-easy-apply-modal__header, div[data-test-easy-apply-header]")
            if header_elem:
                form.current_step_title = (await header_elem.inner_text()).strip()

            # Check next/review/submit buttons
            submit_btn = await container.query_selector(
                "button[aria-label*='Submit application'], button:has-text('Submit application'), button:has-text('Submit')"
            )
            review_btn = await container.query_selector(
                "button[aria-label*='Review your application'], button:has-text('Review')"
            )
            next_btn = await container.query_selector(
                "button[aria-label*='Continue to next step'], button:has-text('Next')"
            )

            if submit_btn or (review_btn and not next_btn):
                form.is_final_step = True
                form.next_button_text = "Submit application" if submit_btn else "Review"
            elif next_btn:
                form.is_final_step = False
                form.next_button_text = (await next_btn.inner_text()).strip()

            # 1. Text & Email & Tel inputs
            input_elements = await container.query_selector_all("input[type='text'], input[type='email'], input[type='tel'], input:not([type])")
            for inp in input_elements:
                field_info = await self._parse_input_element(inp, page)
                if field_info:
                    form.fields.append(field_info)

            # 2. Textarea elements
            textarea_elements = await container.query_selector_all("textarea")
            for ta in textarea_elements:
                ta_info = await self._parse_textarea_element(ta, page)
                if ta_info:
                    form.fields.append(ta_info)

            # 3. Select / Dropdown elements
            select_elements = await container.query_selector_all("select")
            for sel in select_elements:
                sel_info = await self._parse_select_element(sel, page)
                if sel_info:
                    form.fields.append(sel_info)

            # 4. Radio button fieldsets
            fieldsets = await container.query_selector_all("fieldset")
            for fs in fieldsets:
                radio_info = await self._parse_radio_fieldset(fs, page)
                if radio_info:
                    form.fields.append(radio_info)

            # 5. File upload input
            file_input = await container.query_selector("input[type='file']")
            if file_input:
                form.has_resume_field = True
                form.fields.append(
                    DetectedField(
                        field_id="resume_file",
                        label="Resume Upload",
                        field_type="file",
                        standard_name="resume",
                        required=True
                    )
                )

            # Check unanswered questions
            for f in form.fields:
                if f.is_custom_question and not f.current_value:
                    form.has_unanswered_questions = True

            return form

        except Exception as e:
            logger.error(f"Error detecting application form: {e}")
            return form

    async def _parse_input_element(self, inp, page) -> Optional[DetectedField]:
        try:
            inp_id = await inp.get_attribute("id") or ""
            name_attr = await inp.get_attribute("name") or ""
            curr_val = await inp.input_value()

            # Find associated label
            label_text = ""
            if inp_id:
                label_elem = await page.query_selector(f"label[for='{inp_id}']")
                if label_elem:
                    label_text = (await label_elem.inner_text()).strip()

            if not label_text:
                aria_label = await inp.get_attribute("aria-label") or ""
                placeholder = await inp.get_attribute("placeholder") or ""
                label_text = aria_label or placeholder or name_attr or inp_id

            if not label_text and not inp_id:
                return None

            std_name = classify_field_label(label_text, name_attr, inp_id)
            is_custom = std_name is None

            return DetectedField(
                field_id=inp_id or name_attr or "text_input",
                label=label_text,
                field_type="text",
                standard_name=std_name,
                current_value=curr_val,
                is_custom_question=is_custom,
                filled=bool(curr_val)
            )
        except Exception:
            return None

    async def _parse_textarea_element(self, ta, page) -> Optional[DetectedField]:
        try:
            ta_id = await ta.get_attribute("id") or ""
            name_attr = await ta.get_attribute("name") or ""
            curr_val = await ta.input_value()

            label_text = ""
            if ta_id:
                label_elem = await page.query_selector(f"label[for='{ta_id}']")
                if label_elem:
                    label_text = (await label_elem.inner_text()).strip()

            if not label_text:
                label_text = await ta.get_attribute("aria-label") or "Question Textarea"

            std_name = classify_field_label(label_text, name_attr, ta_id)

            return DetectedField(
                field_id=ta_id or name_attr or "textarea",
                label=label_text,
                field_type="textarea",
                standard_name=std_name,
                current_value=curr_val,
                is_custom_question=True,
                filled=bool(curr_val)
            )
        except Exception:
            return None

    async def _parse_select_element(self, sel, page) -> Optional[DetectedField]:
        try:
            sel_id = await sel.get_attribute("id") or ""
            name_attr = await sel.get_attribute("name") or ""

            label_text = ""
            if sel_id:
                label_elem = await page.query_selector(f"label[for='{sel_id}']")
                if label_elem:
                    label_text = (await label_elem.inner_text()).strip()

            if not label_text:
                label_text = await sel.get_attribute("aria-label") or "Dropdown Select"

            # Options
            opt_elems = await sel.query_selector_all("option")
            options = []
            for opt in opt_elems:
                txt = (await opt.inner_text()).strip()
                if txt and txt.lower() not in ("select an option", "--"):
                    options.append(txt)

            curr_val = await sel.input_value()
            std_name = classify_field_label(label_text, name_attr, sel_id)

            return DetectedField(
                field_id=sel_id or name_attr or "select_input",
                label=label_text,
                field_type="select",
                standard_name=std_name,
                current_value=curr_val,
                options=options,
                is_custom_question=std_name is None,
                filled=bool(curr_val)
            )
        except Exception:
            return None

    async def _parse_radio_fieldset(self, fs, page) -> Optional[DetectedField]:
        try:
            legend = await fs.query_selector("legend")
            label_text = (await legend.inner_text()).strip() if legend else "Radio Question"

            radio_inputs = await fs.query_selector_all("input[type='radio']")
            if not radio_inputs:
                return None

            options = []
            curr_val = None
            for r in radio_inputs:
                r_id = await r.get_attribute("id")
                r_val = await r.get_attribute("value") or ""
                checked = await r.is_checked()

                r_label = ""
                if r_id:
                    lbl = await page.query_selector(f"label[for='{r_id}']")
                    if lbl:
                        r_label = (await lbl.inner_text()).strip()

                opt_text = r_label or r_val
                if opt_text:
                    options.append(opt_text)
                if checked:
                    curr_val = opt_text

            std_name = classify_field_label(label_text)

            return DetectedField(
                field_id="radio_group",
                label=label_text,
                field_type="radio",
                standard_name=std_name,
                current_value=curr_val,
                options=options,
                is_custom_question=True,
                filled=bool(curr_val)
            )
        except Exception:
            return None


form_detector = FormDetector()
