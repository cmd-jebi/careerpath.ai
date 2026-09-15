# app.py
import json
import streamlit as st
from google import genai
from google.genai import types
from data import ONET_QUESTIONS, SHS_PATHWAYS, INSTITUTIONS, ONET_ATTRIBUTION, ONET_MODIFICATION_NOTICE
from pdf_generator import create_pdf_report

st.set_page_config(page_title="CareerPath AI", page_icon="🎓", layout="centered")

# --- STEP 1: LAUNCH & CONSENT SCREEN ---
st.title("🎓 CareerPath AI: SHS Guidance Engine")
st.caption("Aligned to the Strengthened SHS Curriculum (DepEd Memorandum No. 012, s. 2026)")

with st.expander("📄 Data Privacy Notice, Terms of Use & O*NET Attribution", expanded=True):
    st.write(
        "We collect Grade 10 marks and interest responses to provide exploratory "
        "guidance under RA 10173 (Data Privacy Act of 2012). Results are "
        "decision-support estimates and do not replace human counselors."
    )
    st.caption(ONET_ATTRIBUTION)

consent = st.checkbox("I agree to provide my academic and interest data for this guidance tool.")
if not consent:
    st.info("Please accept the terms above to proceed.")
    st.stop()

# --- STEP 2: STUDENT ACADEMIC MARKS INPUT ---
st.header("1. Academic Marks (Grade 10)")
col1, col2 = st.columns(2)
with col1:
    math_grade = st.number_input("Math Grade", min_value=60, max_value=100, value=85)
    sci_grade = st.number_input("Science Grade", min_value=60, max_value=100, value=85)
with col2:
    eng_grade = st.number_input("English Grade", min_value=60, max_value=100, value=85)
    tle_grade = st.number_input("TLE / Shop Grade", min_value=60, max_value=100, value=88)

tle_track = st.selectbox(
    "TLE Specialization / Interest Area (for TechPro matching)",
    ["ICT", "Industrial Arts", "Home Economics", "Agri-Fishery Arts"],
)
commerce_interest = st.checkbox("I have a strong interest in business, trade, or commerce")

# --- STEP 3: 60-ITEM O*NET PROFILER (MOBILE ACCORDIONS) ---
st.header("2. O*NET Interest Profiler")
st.write(
    "Check the activities you would like to do. Don't think about the pay or "
    "training it would take — just whether you'd enjoy it."
)
riasec_scores = {}
total_checked = 0
for domain, questions in ONET_QUESTIONS.items():
    with st.expander(f"📌 {domain} Activities"):
        score = 0
        for idx, q in enumerate(questions):
            if st.checkbox(q, key=f"{domain}_{idx}"):
                score += 1
                total_checked += 1
        riasec_scores[domain] = score

# --- STEP 4: LOW-ENGAGEMENT VALIDATOR ---
# O*NET's own scoring guidance flags an all-"strongly dislike" (or here,
# all-unchecked) response as a likely-invalid profile that should be
# retaken rather than scored (O*NET Interest Profiler Manual, Ch. 2).
low_engagement = total_checked == 0 or total_checked == 60
if low_engagement:
    st.warning(
        "⚠️ Response Check: you selected either none or all 60 items. This "
        "usually means the profile isn't a reliable read of your real "
        "interests. Consider retaking the checklist thoughtfully, and talk "
        "to your Guidance Counselor in the meantime."
    )

# --- STEP 5: AI RECOMMENDATION ENGINE (GEMINI) ---
st.header("3. Generate Your Pathway Recommendation")

if st.button("Generate Career Pathway Recommendations"):
    if low_engagement:
        st.error("Please provide realistic interest responses before generating recommendations.")
    else:
        api_key = st.secrets.get("GEMINI_API_KEY")
        if not api_key:
            st.error(
                "This app isn't configured with an API key yet. "
                "The site owner needs to add GEMINI_API_KEY to Streamlit secrets."
            )
        else:
            client = genai.Client(api_key=api_key)

            # DM 012, s.2026 rules given explicitly — the model's own training
            # data predates this memo, so it cannot be trusted to know the
            # 2-track / elective-cluster structure on its own.
            system_context = """
You are assisting a Philippine Senior High School (SHS) guidance tool.
As of DepEd Memorandum No. 012, s. 2026 (Strengthened SHS Curriculum),
there are only 2 tracks: Academic and Technical Professional (TechPro).
Rigid strands no longer exist. Under Academic, a student can pick
elective clusters: STEM, ABM, HUMSS, GAS, Arts & Design, Sports.
TechPro has specializations: ICT, Industrial Arts, Home Economics,
Agri-Fishery Arts. A "doorway option" lets a student add a limited
number of electives from the other track. Do not recommend the old
4-strand (STEM/ABM/HUMSS/TVL) model — it no longer exists.
"""

            prompt = f"""{system_context}

Analyze this Grade 10 student:
- Subject grades (0-100): Math {math_grade}, Science {sci_grade}, English {eng_grade}, TLE {tle_grade}
- Commerce/business interest indicated: {commerce_interest}
- TLE specialization interest: {tle_track}
- RIASEC interest checklist results (count out of 10 per domain): {riasec_scores}

Return your evaluation as the requested JSON structure. Keep language
concise, encouraging, and clear for a 16-year-old student. Do not
invent specific numeric match percentages beyond what is reasonable
from the inputs given; describe fit qualitatively (e.g. "strong fit",
"moderate fit") rather than fabricating precise statistics.

Reference data for your chosen cluster/specialization — draw your
degree, TESDA, scholarship, and institution suggestions primarily
from this list. You may add a well-known program not listed here if
it clearly fits, but do not invent specific institution names or
locations beyond what is given; if the provided institution list
doesn't cover the student's region, say so plainly and suggest they
confirm with their regional CHED or TESDA office instead of guessing.

{json.dumps(SHS_PATHWAYS, indent=2)}

Institution reference (starter list only, not comprehensive):
{json.dumps(INSTITUTIONS, indent=2)}
"""

            response_schema = {
                "type": "object",
                "properties": {
                    "primary_track": {"type": "string"},
                    "primary_cluster": {"type": "string"},
                    "primary_rationale": {"type": "string"},
                    "doorway_option": {"type": "string"},
                    "prerequisite_gaps": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "degree_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "tesda_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "scholarship_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "career_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "institution_suggestions": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "primary_track", "primary_cluster", "primary_rationale",
                    "prerequisite_gaps", "degree_suggestions", "tesda_suggestions",
                    "scholarship_suggestions", "career_suggestions", "institution_suggestions",
                ],
            }

            import time

            # Google's shared free-tier capacity occasionally returns a
            # transient 503 ("model currently experiencing high demand").
            # Retry a couple of times with backoff, then fall back to the
            # lighter Flash-Lite alias, before giving up — this prevents a
            # single momentary spike from derailing a live demo.
            def _generate_with_resilience():
                models_to_try = ["gemini-flash-latest", "gemini-flash-lite-latest"]
                last_error = None
                for model_name in models_to_try:
                    for attempt in range(2):  # 2 tries per model
                        try:
                            return client.models.generate_content(
                                model=model_name,
                                contents=prompt,
                                config=types.GenerateContentConfig(
                                    temperature=0.2,
                                    response_mime_type="application/json",
                                    response_schema=response_schema,
                                ),
                            )
                        except Exception as e:
                            last_error = e
                            if "503" in str(e) or "UNAVAILABLE" in str(e):
                                time.sleep(2 * (attempt + 1))  # 2s, then 4s
                                continue
                            raise  # non-503 errors: don't waste retries, fail fast
                raise last_error

            try:
                with st.spinner("Analyzing profile and matching to DepEd tracks..."):
                    response = _generate_with_resilience()
                result = response.parsed  # structured dict matching response_schema
                st.success("Analysis complete!")

                st.subheader(f"Primary Recommendation: {result['primary_track']} — {result['primary_cluster']}")
                st.write(result["primary_rationale"])

                if result.get("doorway_option"):
                    st.info(f"**Doorway option:** {result['doorway_option']}")

                st.markdown("**Prerequisite Gaps to Review:**")
                for gap in result["prerequisite_gaps"]:
                    st.markdown(f"- {gap}")

                st.markdown("**Suggested CHED Degree Programs:**")
                for d in result["degree_suggestions"]:
                    st.markdown(f"- {d}")

                st.markdown("**Suggested TESDA Certifications:**")
                for t in result["tesda_suggestions"]:
                    st.markdown(f"- {t}")

                st.markdown("**Scholarships to Look Into:**")
                for s in result["scholarship_suggestions"]:
                    st.markdown(f"- {s}")

                st.markdown("**Entry-Level Career Paths:**")
                for c in result["career_suggestions"]:
                    st.markdown(f"- {c}")

                st.markdown("**Institutions to Check (starter list — confirm with your regional CHED/TESDA office):**")
                for i in result["institution_suggestions"]:
                    st.markdown(f"- {i}")

                st.caption(ONET_MODIFICATION_NOTICE)

                # Store for PDF generation
                st.session_state["result"] = result
                st.session_state["scores"] = riasec_scores

            except Exception as e:
                # Never let a raw API/model error reach the student's screen —
                # this is exactly the failure mode that killed v1 (dead model,
                # no error handling, crash during a live demo).
                st.error(
                    "Something went wrong generating your recommendation. "
                    "This can happen if the AI service is temporarily busy "
                    "or unavailable. Please try again in a moment, or "
                    "continue your session with your Guidance Counselor."
                )
                st.caption(f"Technical detail (for developers): {e}")

# --- STEP 6: PDF EXPORT BUTTON ---
if "result" in st.session_state:
    pdf_bytes = create_pdf_report(st.session_state["scores"], st.session_state["result"])
    st.download_button(
        label="📥 Download Full Guidance Summary (PDF)",
        data=pdf_bytes,
        file_name="CareerPath_AI_Guidance_Report.pdf",
        mime="application/pdf",
    )