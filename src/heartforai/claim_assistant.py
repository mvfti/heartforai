import chainlit as cl
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import random
from pathlib import Path
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from heartforai import client, MISTRAL_MODEL, CONDITIONS_FILE_PATH
# from chainlit.input_widget import TextInput

# Get the project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent

# ==========================================
# ltenRestart
#
# 1. ENUMERATION & SPECIALIZED SCHEMA (FRAUD)
# ==========================================


class ClaimCategory(str, Enum):
    """Main claim categories for dispatching."""

    FRAUD = "FRAUD"
    PROPERTY_DAMAGE = "PROPERTY_DAMAGE"


class PropertyClaim(BaseModel):
    """Specific schema for PROPERTY DAMAGE claims (House/Apartment)."""

    claim_category: ClaimCategory = Field(
        default=ClaimCategory.PROPERTY_DAMAGE, Literal=True
    )

    # -----------------------------------------------------
    # I. POLICY DATA (Filled by the system)
    # -----------------------------------------------------
    # These fields MUST NOT be extracted by the LLM, but are essential
    # for final transmission and coverage evaluation.
    policy_id: Optional[str] = Field(
        None, description="Unique identifier of the insurance policy."
    )
    product_id: Optional[str] = Field(
        None, description="Product code of the insurance plan."
    )
    product_name: Optional[str] = Field(
        None,
        description="Name of the insurance product (e.g., Tenant Insurance - Plus).",
    )
    coverage_desc: Optional[str] = Field(
        None, description="Description of the coverages included in the policy."
    )
    policy_start_dt: Optional[str] = Field(
        None, description="Start date of the policy."
    )
    policy_end_dt: Optional[str] = Field(None, description="End date of the policy.")
    premium_amt: Optional[float] = Field(None, description="Annual premium amount.")
    language: Optional[str] = Field(
        None, description="Preferred language for communication (e.g., NL, FR)."
    )
    postal_code: Optional[str] = Field(
        None, description="Postal code of the insured property."
    )
    sentiment: Optional[int] = Field(
        None,
        description="Sentiment of the client. The sentiment score ranges from 0 to 5. 0 for neutral sentiment and progressively worse mood with an increase of 1",
    )

    # -----------------------------------------------------
    # II. INCIDENT DATA (Extracted by LLM from user input)
    # -----------------------------------------------------
    should_do_action: Optional[str] = Field(
        description="Based on the user input, determine if we need to proceed with an action (True) or not (False). Possible values: ['True', 'False']. Put null if the input is completely irrelevant to a claim."
    )

    damage_type: str = Field(
        description="Type of damage (e.g., Fire, Water Leak, Storm). Possible values: [Fire, Water, Storm]. The LLM MUST choose one value. Put 'UNKNOWN' if classification is impossible."
    )

    cause: Optional[str] = Field(
        description="Cause that led to the damage type. Put null if not mentioned."
    )

    incident_date: Optional[str] = Field(
        description="The exact date and time of the incident. Required for execution. Put null if not mentioned."
    )

    damage_location: Optional[str] = Field(
        description="The precise location of the damage (e.g., kitnchen, basement, roof). Required for execution. Put null if not mentioed."
    )

    def get_critical_fields(self) -> List[str]:
        # NOTE: should_do_action can be omitted here if it is not critical for execution
        return ["should_do_action", "incident_date", "damage_location", "cause"]


# ==========================================
# 1.1. LLM FUNCTIONS (Mistral API Calls)
# ==========================================


def get_random_policy():
    with open("database/db.json", "r") as file:
        # data will be a Python dictionary or list
        data = file.read()
        python_list = json.loads(data)
        random_policy = random.choice(python_list)

        print(random_policy)

        return random_policy


# ==========================================
# 2. LLM FUNCTIONS (Mistral API Calls)
# ==========================================


def call_mistral_for_json(user_text: str) -> Dict[str, Any]:
    """LLM 1: Extracts user data into structured JSON (PropertyClaim)."""

    extraction_prompt = (
        "You are a compassionate insurance assistant helping someone who has experienced property damage. "
        "Your role is to carefully listen to what they're telling you and extract the important details about their situation. "
        "Pay attention to when the incident happened, where it occurred, what type of damage it was, and what caused it. "
        "If any information is missing, that's okay - just mark those fields as 'null'. "
        "Remember, you're helping a real person through a difficult time, so be thorough and understanding in processing their information."
    )

    messages = [
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": user_text},
    ]

    response = client.chat.parse(
        model=MISTRAL_MODEL, messages=messages, response_format=PropertyClaim
    )
    return response.choices[0].message.content


def call_mistral_for_query(missing_fields: List[str]) -> str:
    """LLM 2: Generates a question to retrieve missing information."""

    query_prompt = (
        f"You are a caring insurance assistant helping someone through a difficult time. "
        f"You need to gently ask for some missing information: {', '.join(missing_fields)}. "
        f"Frame your question in a warm, conversational way - like you're talking to a friend who needs help. "
        f"Acknowledge that you understand this might be hard to talk about, and make it clear you're here to help them."
    )

    messages = [
        {"role": "system", "content": query_prompt},
        {"role": "user", "content": "Generate the question to ask the user."},
    ]

    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


def call_mistral_for_sentiment(user_text: str) -> int:
    """LLM: Analyzes the sentiment of the user's message and returns a score from 0 to 5."""

    sentiment_prompt = (
        "You are a **sentiment analysis expert**. Your role is to analyze the emotional tone "
        "of the user's message and assign a sentiment score from 0 to 5.\n\n"
        "Sentiment Scale:\n"
        "- 0: Neutral (no strong emotion)\n"
        "- 1: Slightly negative (minor concern or frustration)\n"
        "- 2: Moderately negative (noticeable frustration or worry)\n"
        "- 3: Negative (clear frustration, anger, or distress)\n"
        "- 4: Very negative (strong anger, panic, or distress)\n"
        "- 5: Extremely negative (severe distress, extreme anger, or desperation)\n\n"
        "Respond with ONLY the numeric score (0-5), nothing else."
    )

    messages = [
        {"role": "system", "content": sentiment_prompt},
        {
            "role": "user",
            "content": f"Analyze the sentiment of this message: {user_text}",
        },
    ]

    response = client.chat.complete(
        model=MISTRAL_MODEL, messages=messages, temperature=0.1
    )

    try:
        score = int(response.choices[0].message.content.strip())
        # Ensure score is within valid range
        return max(0, min(5, score))
    except ValueError:
        # Default to neutral if parsing fails
        return 0


def read_markdown_file() -> str:
    """Reads the content of a Markdown file."""

    try:
        with open(CONDITIONS_FILE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: The file {CONDITIONS_FILE_PATH} was not found.")
        return "ERROR: Client conditions file not found."


def call_mistral_to_assess_coverage(client_str: str) -> str:
    """
    LLM 2: Evaluates client coverage based on extracted data
    and general conditions.
    """

    client_data = dict(json.loads(client_str))

    general_conditions_md = read_markdown_file()
    client_data_str = "\n".join([f"- {k}: {v}" for k, v in client_data.items()])

    system_prompt = (
        f"You are a compassionate insurance professional helping someone understand their coverage after experiencing property damage. "
        f"Your role is to carefully review their situation against the policy rules and explain what coverage applies. "
        f"Be clear, honest, and kind in your assessment. Remember you're talking to someone who may be stressed or worried about their home.\n\n"
        f"--- POLICY RULES ---\n"
        f"{general_conditions_md}\n"
        f"-------------------\n"
    )

    user_prompt = (
        f"Please review this person's claim situation:\n\n"
        f"### What happened:\n"
        f"{client_data_str}\n\n"
        f"Based on their policy and what they've told us, please assess their coverage. "
        f"Structure your response as follows:\n"
        f"1. **My Assessment:** [COVERED | NOT COVERED | NEEDS MORE INFO]\n"
        f"2. **Here's why:** [Explain in one clear sentence, referencing the policy.]\n"
        f"3. **Important note:** [Include the required disclaimer.]"
    )

    # Definition of DISCLAIMER
    disclaimer = "This evaluation is generated by an AI model and is for informational purposes only; it does not constitute a definitive coverage decision. Please consult a human expert for the final determination."

    messages = [
        {"role": "system", "content": system_prompt},
        # Adding disclaimer directly in user prompt to ensure it is included
        {
            "role": "user",
            "content": user_prompt
            + f"\n\nUse the following exact text for the DISCLAIMER part:\n'{disclaimer}'",
        },
    ]

    # 5. Call to Mistral API
    response = client.chat.complete(
        model=MISTRAL_MODEL, messages=messages, temperature=0.1
    )

    return response.choices[0].message.content


def call_mistral_for_synthesis(final_prompt: str, sentiment: int = 0) -> str:
    """LLM 3: Synthesizes the humanized response after deterministic execution."""

    sentiment_context = ""
    if sentiment >= 4:
        sentiment_context = "The client is clearly very distressed and upset. Show deep empathy, acknowledge their difficult situation, and reassure them that you understand how challenging this must be."
    elif sentiment >= 2:
        sentiment_context = "The client is experiencing some frustration or worry. Be especially understanding and reassuring in your tone."
    else:
        sentiment_context = "Maintain a warm, supportive, and friendly tone."

    synthesis_prompt = f"You are a compassionate insurance assistant speaking directly to a client who has experienced property damage. {sentiment_context} Communicate like a caring friend who wants to help - use 'I', 'you', 'we' naturally. Avoid corporate jargon and technical terms. The actions to confirm are: {final_prompt}. Make the client feel heard, supported, and confident that they're in good hands."

    messages = [
        {"role": "system", "content": synthesis_prompt},
        {"role": "user", "content": "Write the final response."},
    ]

    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=messages,
    )
    return response.choices[0].message.content


# ==========================================
# 3. DETERMINISTIC PATH (Business Rules)
# ==========================================


def determinist_path(data: PropertyClaim) -> str:
    """Specific rules for FRAUD."""

    actions = [f"Claim type: {data.damage_type}."]

    if data.shoud_do_action.lower() != "true":
        actions.append(
            "ℹ️ No action required as per the user's input regarding property damage."
        )
        return "\n* " + "\n* ".join(actions)

    if data.is_secure is False:
        actions.append(
            "🔥 **SECURITY ACTION: Emergency service (firefighters/plumber) contacted to secure the area.**"
        )
        actions.append("🚧 Temporary emergency rehousing implemented.")
    else:
        actions.append(
            "✅ The area is secure. Starting the expert assessment procedure."
        )

    actions.append(
        f"📍 Expert assessment scheduled for the damage located at: {data.damage_location}."
    )

    return "\n* " + "\n* ".join(actions)


# ==========================================
# 4. ORCHESTRATION CHAINLIT (The Engine)
# ==========================================


def find_missing_critical_data(data_str: str) -> List[str]:
    """
    Returns the list of field names (snake_case) that are critical and missing.
    """
    data = json.loads(data_str)
    instance = PropertyClaim.model_validate(data)
    critical_fields = instance.get_critical_fields()
    missing = []
    for field_name in critical_fields:
        value = data.get(field_name)
        if value is None or (isinstance(value, float) and value == 0.0):
            missing.append(field_name)
    return missing


@cl.on_chat_start
async def start():
    # test = cl.Text(content="Initializing Mistral client...")
    cl.user_session.set("current_incident_data", None)

    # Add action button to view dashboard
    actions = [
        cl.Action(
            name="view_dashboard",
            value="dashboard",
            payload={"url": "/dashboard"},
            label="📊 View Claim Progress",
            description="Check your claim status on the dashboard",
        )
    ]

    await cl.Message(
        content="Hello! I'm really glad you reached out. I know dealing with property damage can be stressful, and I'm here to make this process as smooth as possible for you. Let's work through this together, step by step.",
    ).send()

    policy_data = get_random_policy()

    cl.user_session.set("policy_data", policy_data)

    # Save current policy to file so dashboard can access it
    current_session_file = PROJECT_ROOT / "database" / "current_session.json"
    with open(current_session_file, "w") as f:
        json.dump(policy_data, f, indent=2)

    await cl.Message(
        content=f"I've pulled up your policy information - you're covered under our {policy_data.get('product_name')} plan. Whenever you're ready, please tell me what happened. Take your time and share as much detail as you're comfortable with.",
        author="Assur-Bot",
    ).send()


@cl.action_callback("view_dashboard")
async def on_action(action: cl.Action):
    """Handle dashboard action button click"""
    await cl.Message(
        content="You can check on your claim progress anytime! [Click here to view your dashboard](/dashboard)",
    ).send()


@cl.on_settings_update
async def setup_agent(settings):
    # À chaque frappe dans le formulaire, on sauvegarde les données dans la session
    cl.user_session.set("form_data", settings)


@cl.on_message
async def main(message: cl.Message):
    user_input = message.content

    # Get policy from session instead of selecting a new random one
    policy_data = cl.user_session.get("policy_data")
    if not policy_data:
        # Fallback: if session lost, get random policy
        policy_data = get_random_policy()
        cl.user_session.set("policy_data", policy_data)

    current_data = cl.user_session.get("current_incident_data")

    # Concatenate collection history if necessary
    if current_data:
        user_input = f"Previous context: {json.dumps(current_data)}. New information: {user_input}"

    # -----------------------------------------------------
    # STEP A: DATA EXTRACTION (Specialized LLM 1)
    # -----------------------------------------------------
    await cl.Message(
        content="I'm listening carefully to what you're telling me... Let me make sure I understand everything correctly.",
        author="Agent",
    ).send()

    try:
        json_str = await cl.make_async(call_mistral_for_json)(user_input)
    except Exception as e:
        await cl.Message(
            content=f"I apologize - I'm having a moment of technical difficulty understanding your message. Could you try rephrasing that for me? I really want to make sure I capture all the important details.",
            author="Agent",
        ).send()
        return

    # -----------------------------------------------------
    # SENTIMENT ANALYSIS: Analyze user's emotional tone
    # -----------------------------------------------------
    # await cl.Message(
    #     content="**Sentiment Analysis:** Evaluating message tone...",
    #     author="Agent",
    # ).send()
    #
    try:
        sentiment_score = await cl.make_async(call_mistral_for_sentiment)(
            message.content
        )
    except Exception as e:
        # Silently default to neutral - no need to tell user about technical issues
        sentiment_score = 0

    # Update state
    cl.user_session.set("current_incident_data", json_str)

    validated_instance: PropertyClaim = PropertyClaim.model_validate_json(json_str)

    # Merge policy data and sentiment score into the model
    policy_data = cl.user_session.get("policy_data")
    if policy_data:
        # Create merged data with policy info
        merged_data = {**validated_instance.model_dump(), **policy_data}
        # Set sentiment score in the merged data
        merged_data["sentiment"] = sentiment_score
        validated_instance = PropertyClaim.model_validate(merged_data)
        json_trace = {
            k: (v.value if isinstance(v, Enum) else v)
            for k, v in validated_instance.model_dump().items()
        }
        cl.user_session.set("current_incident_data", json.dumps(json_trace, indent=2))

    # -----------------------------------------------------
    # STEP B: VALIDATION AND REQUEST FOR MISSING INFORMATION
    # -----------------------------------------------------

    missing_fields = find_missing_critical_data(
        cl.user_session.get("current_incident_data")
    )

    if missing_fields:
        # Create empathetic intro based on sentiment
        if sentiment_score >= 4:
            intro_msg = "I can hear how difficult this situation is for you. To help you as quickly as possible, I just need a few more details. I know it's hard to think about right now, but these will really help us move forward."
        elif sentiment_score >= 2:
            intro_msg = "I understand this is frustrating. To make sure we handle your claim properly, I need to ask you for a bit more information. It'll just take a moment."
        else:
            intro_msg = "Thank you for sharing that with me. To complete your claim, I need just a few more details from you. This will help us process everything smoothly."

        await cl.Message(content=intro_msg).send()

        additional_info = []

        # Create friendly field name mappings
        field_friendly_names = {
            "incident_date": "When did this happen? If you remember the approximate date and time, that would be really helpful",
            "damage_location": "Where exactly in your home did the damage occur? For example, which room or area",
            "cause": "What do you think caused this damage? Your best guess is perfectly fine",
            "should_do_action": "Should we proceed with processing your claim"
        }

        # --- BOUCLE "FORMULAIRE" ---
        for field in missing_fields:
            # Use friendly question if available, otherwise generate one
            if field in field_friendly_names:
                question_text = field_friendly_names[field]
            else:
                human_label = field.replace("_", " ").lower()
                question_text = f"Could you tell me about the {human_label}?"

            # 3. AskUserMessage bloque le script et attend la réponse de l'utilisateur
            res = await cl.AskUserMessage(content=question_text, timeout=180).send()

            if res:
                user_val = res["output"]
                additional_info.append(f"The user specifies for {field} : {user_val}")

        # --- MISE A JOUR DES DONNÉES ---
        # On injecte les nouvelles réponses dans le contexte et on relance l'extraction
        # pour s'assurer que le format (Date, Booléen) est correct.

        await cl.Message(
            content="Perfect, let me update everything with this new information...",
            author="Agent"
        ).send()

        # On concatène l'ancien input avec les nouvelles infos
        updated_input = f"{user_input} \n " + " \n ".join(additional_info)

        # RE-RUN LLM 1 (Extraction) avec les nouvelles infos
        try:
            json_str = await cl.make_async(call_mistral_for_json)(updated_input)
            # Mise à jour de l'instance validée
            validated_instance = PropertyClaim.model_validate_json(json_str)

            policy_data = cl.user_session.get("policy_data")
            # (Important) On refusionne avec les données police car l'extraction LLM ne les a pas
            if policy_data:
                merged_data = {**validated_instance.model_dump(), **policy_data}
                # Set sentiment score in the merged data
                merged_data["sentiment"] = sentiment_score
                validated_instance = PropertyClaim.model_validate(merged_data)
                json_trace = {
                    k: (v.value if isinstance(v, Enum) else v)
                    for k, v in validated_instance.model_dump().items()
                }
                cl.user_session.set(
                    "current_incident_data", json.dumps(json_trace, indent=2)
                )

            actions = [
                cl.Action(
                    name="view_dashboard",
                    value="dashboard",
                    payload={"url": "/dashboard"},
                    label="📊 View Claim Progress",
                    description="Check your claim status on the dashboard",
                )
            ]

            # Affichage de confirmation
            await cl.Message(
                content="Great! I've got everything I need now. Thank you so much for bearing with me - I know answering questions isn't easy when you're dealing with damage to your home.",
                author="Agent",
                actions=actions,
            ).send()

        except Exception as e:
            await cl.Message(
                content="I'm so sorry, I seem to be having trouble updating your information. Could we try that one more time?"
            ).send()
            return
    # -----------------------------------------------------
    # STEP C: EVALUATION IF THE CLIENT IS COVERED
    # -----------------------------------------------------

    # Create sentiment-aware message
    if sentiment_score >= 4:
        assessment_msg = "I know you're going through a really tough time right now. Let me check your policy coverage - I'll do everything I can to help you..."
    elif sentiment_score >= 2:
        assessment_msg = "Let me review your policy details to see how we can best support you with this claim..."
    else:
        assessment_msg = "Now let me take a look at your policy to see what coverage applies to your situation..."

    await cl.Message(
        content=assessment_msg,
        author="Agent",
    ).send()

    coverage_assessment = await cl.make_async(call_mistral_to_assess_coverage)(
        cl.user_session.get(
            "current_incident_data"
        ),  # put the form with the mandatory information
    )

    # Add empathetic framing based on sentiment
    if sentiment_score >= 4:
        intro = "I've carefully reviewed everything, and here's what I found:\n\n"
    elif sentiment_score >= 2:
        intro = "Okay, I've looked into your coverage. Here's the information:\n\n"
    else:
        intro = "Here's what I found regarding your coverage:\n\n"

    await cl.Message(
        content=f"{intro}{coverage_assessment}",
        author="Agent",
    ).send()

    # Clean up state after successful execution
    cl.user_session.set("current_incident_data", None)
