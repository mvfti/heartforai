import chainlit as cl
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import random
import os
from chainlit.input_widget import TextInput
from mistralai import Mistral


global client
global MISTRAL_MODEL
# --- Configuration ---
MISTRAL_MODEL = "mistral-small-2506" 

api_key = "DNJ2Duuaislp57c9ezYHX85ZvWhCQgIR"
client = Mistral(api_key=api_key)

# ==========================================
# 1. ENUMERATION & SPECIALIZED SCHEMA (FRAUD)
# ==========================================

class ClaimCategory(str, Enum):
    """Main claim categories for dispatching."""
    FRAUD = "FRAUD"
    PROPERTY_DAMAGE = "PROPERTY_DAMAGE"
    

class PropertyClaim(BaseModel):
    """Specific schema for PROPERTY DAMAGE claims (House/Apartment)."""
    claim_category: ClaimCategory = Field(default=ClaimCategory.PROPERTY_DAMAGE, Literal=True)
    
    # -----------------------------------------------------
    # I. POLICY DATA (Filled by the system)
    # -----------------------------------------------------
    # These fields MUST NOT be extracted by the LLM, but are essential 
    # for final transmission and coverage evaluation.
    policy_id: Optional[str] = Field(None, description="Unique identifier of the insurance policy.")
    product_id: Optional[str] = Field(None, description="Product code of the insurance plan.")
    product_name: Optional[str] = Field(None, description="Name of the insurance product (e.g., Tenant Insurance - Plus).")
    coverage_desc: Optional[str] = Field(None, description="Description of the coverages included in the policy.")
    policy_start_dt: Optional[str] = Field(None, description="Start date of the policy.")
    policy_end_dt: Optional[str] = Field(None, description="End date of the policy.")
    premium_amt: Optional[float] = Field(None, description="Annual premium amount.")
    language: Optional[str] = Field(None, description="Preferred language for communication (e.g., NL, FR).")
    postal_code: Optional[str] = Field(None, description="Postal code of the insured property.")
    
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
        description="The precise location of the damage (e.g., kitchen, basement, roof). Required for execution. Put null if not mentioned."
    )
    
    def get_critical_fields(self) -> List[str]:
        # NOTE: should_do_action can be omitted here if it is not critical for execution
        return ["should_do_action", "incident_date", "damage_location", "cause"]
    

# ==========================================
# 1.1. LLM FUNCTIONS (Mistral API Calls)
# ==========================================

def get_random_policy():
    with open('database/db.json', 'r') as file:
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
    f"You are a **home insurance expert**. Your role is to **extract the key information** "
    f"from the user's text to **fill the PropertyClaim JSON schema**. "
    f"If any information is missing, **return 'null'** for the 'Optional' field."
    )
    
    messages = [
        {"role": "system", "content": extraction_prompt},
        {"role": "user", "content": user_text},
    ]


    response = client.chat.parse(
        model=MISTRAL_MODEL,
        messages=messages,
        response_format = PropertyClaim
    )
    return response.choices[0].message.content


def call_mistral_for_query(missing_fields: List[str]) -> str:
    """LLM 2: Generates a question to retrieve missing information."""
    
    query_prompt = (
    f"You are a **customer service assistant**. The following information is missing to process the file: {', '.join(missing_fields)}. "
    f"Draft an **empathetic sentence** to ask the user for this supplementary information."
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


def read_markdown_file() -> str:
    """Reads the content of a Markdown file."""

    CONDITIONS_FILE_PATH = "./products/insurance/bank_insurance/home/GENERAL_CONDITIONS.MD" 
    try:
        with open(CONDITIONS_FILE_PATH, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Error: The file {CONDITIONS_FILE_PATH} was not found.")
        return "ERROR: Client conditions file not found."
    
def call_mistral_to_assess_coverage(client_data: Dict) -> str:
    """
    LLM 2: Evaluates client coverage based on extracted data 
    and general conditions.
    """
    general_conditions_md = read_markdown_file()
    client_data_str = "\n".join([f"- {k}: {v}" for k, v in client_data.items()])
    
    system_prompt = (
        f"You are a highly skilled **Insurance Underwriter Agent**. Your task is to determine "
        f"if a claim is likely covered based on the policy rules provided below.\n"
        f"You MUST provide a clear rationale for your decision based ONLY on the provided data.\n\n"
        
        f"--- POLICY RULES (MARKDOWN) ---\n"
        f"{general_conditions_md}\n"
        f"-------------------------------\n"
    )
    
    user_prompt = (
        f"Assess the coverage for the following claim incident:\n\n"
        f"### INCIDENT DATA\n"
        f"{client_data_str}\n\n"
        
        f"Based on the POLICY RULES and the INCIDENT DATA, is the claim covered? "
        f"Your response MUST follow this exact structure:\n"
        f"1. **DECISION:** [COVERED | NOT COVERED | NEEDS MORE INFO]\n"
        f"2. **JUSTIFICATION (1 Sentence):** [One sentence explaining the reason based on policy rules.]\n"
        f"3. **DISCLAIMER:** [The required disclaimer phrase.]"
    )
    
    # Definition of DISCLAIMER
    disclaimer = "This evaluation is generated by an AI model and is for informational purposes only; it does not constitute a definitive coverage decision. Please consult a human expert for the final determination."
    
    messages = [
        {"role": "system", "content": system_prompt},
        # Adding disclaimer directly in user prompt to ensure it is included
        {"role": "user", "content": user_prompt + f"\n\nUse the following exact text for the DISCLAIMER part:\n'{disclaimer}'"},
    ]
    
    # 5. Call to Mistral API
    response = client.chat.complete(
        model=MISTRAL_MODEL,
        messages=messages,
        temperature=0.1
    )
    
    return response.choices[0].message.content

def call_mistral_for_synthesis(final_prompt: str) -> str:
    """LLM 3: Synthesizes the humanized response after deterministic execution."""
    
    synthesis_prompt = (
        f"You are the case closure assistant. Synthesize the following response for the client in a professional and empathetic manner, confirming the actions taken. The actions to confirm are: {final_prompt}"
    )
    
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

    if (data.shoud_do_action.lower() != "true"):
        actions.append("ℹ️ No action required as per the user's input regarding property damage.")
        return "\n* " + "\n* ".join(actions)
    
    if data.is_secure is False:
        actions.append("🔥 **SECURITY ACTION: Emergency service (firefighters/plumber) contacted to secure the area.**")
        actions.append("🚧 Temporary emergency rehousing implemented.")
    else:
        actions.append("✅ The area is secure. Starting the expert assessment procedure.")
        
    actions.append(f"📍 Expert assessment scheduled for the damage located at: {data.damage_location}.")
    
    return "\n* " + "\n* ".join(actions)


# ==========================================
# 4. ORCHESTRATION CHAINLIT (The Engine) 
# ==========================================

def find_missing_critical_data(data: dict) -> List[str]:
    """
    Returns the list of field names (snake_case) that are critical and missing.
    """
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


    test = cl.Text(content="Initializing Mistral client...")
    cl.user_session.set("current_incident_data", None)
    await cl.Message(
        content="👋 Welcome to HomeResQ. How can I assist you today?",
    ).send()

    policy_data = get_random_policy()
    
    cl.user_session.set("policy_data", policy_data)

    await cl.Message(
        content=f"**Policy Data Loaded:** Policy ID `{policy_data.get('policy_id')}` ({policy_data.get('product_name')}). How can I help you with your claim today?",
        author="Assur-Bot"
    ).send()


@cl.on_settings_update
async def setup_agent(settings):
    # À chaque frappe dans le formulaire, on sauvegarde les données dans la session
    cl.user_session.set("form_data", settings)

@cl.on_message
async def main(message: cl.Message):
    global client
    user_input = message.content
    
    policy_data = get_random_policy()
    current_data = cl.user_session.get("current_incident_data")
    
    # Concatenate collection history if necessary
    if current_data:
        user_input = f"Previous context: {json.dumps(current_data)}. New information: {user_input}"

    # -----------------------------------------------------
    # STEP A: DATA EXTRACTION (Specialized LLM 1)
    # -----------------------------------------------------
    await cl.Message(content="🧠 **LLM 1 - Extraction :** Filling the PropertyClaim schema...", author="Agent").send()

    try:
        json_str = await cl.make_async(call_mistral_for_json)(user_input)
    except Exception as e:
        await cl.Message(content=f"Error during Mistral call (Extraction): {e}.", author="System Error").send()
        return

    # Update state
    cl.user_session.set("current_incident_data", json_str)
    
    validated_instance: PropertyClaim = PropertyClaim.model_validate_json(json_str)

    policy_data = cl.user_session.get("policy_data")

    # 3. Merge data: create a combined dictionary
    if policy_data:
        # Merge claim data (LLM) with policy data (DB)
        current_claim_data = validated_instance.model_dump()
        merged_data = {**current_claim_data, **policy_data}
        
        # 4. Create a FINAL PropertyClaim instance with ALL data
        final_validated_instance = PropertyClaim.model_validate(merged_data)
        
        # The rest of the script should use final_validated_instance
        validated_instance = final_validated_instance

    # Display extracted JSON for traceability (with Enum conversion)
    json_trace = {k: (v.value if isinstance(v, Enum) else v) for k, v in validated_instance.model_dump().items()}
    await cl.Message(
        content=f"**Extracted JSON:**\n```json\n{json.dumps(json_trace, indent=2)}\n```",
        author="Model Trace"
    ).send()

    # -----------------------------------------------------
    # STEP B: VALIDATION AND REQUEST FOR MISSING INFORMATION  
    # -----------------------------------------------------
        
    missing_fields = find_missing_critical_data(validated_instance.model_dump())
            
    if missing_fields:
        await cl.Message(content="⚠️ Certaines informations essentielles sont manquantes pour avancer.").send()
        
        additional_info = []

        # --- BOUCLE "FORMULAIRE" ---
        for field in missing_fields:
            # 1. On rend le nom du champ plus lisible (ex: incident_date -> Incident Date)
            human_label = field.replace('_', ' ').capitalize()
            
            # 2. On utilise l'LLM (optionnel) ou une phrase simple pour poser la question
            # Ici, on fait simple pour simuler un champ de formulaire
            question_text = f"👉 Veuillez préciser : **{human_label}** ?"
            
            # 3. AskUserMessage bloque le script et attend la réponse de l'utilisateur
            res = await cl.AskUserMessage(content=question_text, timeout=180).send()
            
            if res:
                user_val = res['output']
                additional_info.append(f"L'utilisateur précise pour {field} : {user_val}")
        
        # --- MISE A JOUR DES DONNÉES ---
        # On injecte les nouvelles réponses dans le contexte et on relance l'extraction
        # pour s'assurer que le format (Date, Booléen) est correct.
        
        await cl.Message(content="🔄 Mise à jour du dossier en cours...", author="System").send()
        
        # On concatène l'ancien input avec les nouvelles infos
        updated_input = f"{user_input} \n " + " \n ".join(additional_info)
        
        # RE-RUN LLM 1 (Extraction) avec les nouvelles infos
        try:
            json_str = await cl.make_async(call_mistral_for_json)(updated_input)
            # Mise à jour de l'instance validée
            validated_instance = PropertyClaim.model_validate_json(json_str)
            
            # (Important) On refusionne avec les données police car l'extraction LLM ne les a pas
            if policy_data:
                merged_data = {**validated_instance.model_dump(), **policy_data}
                validated_instance = PropertyClaim.model_validate(merged_data)
                
            # Affichage de confirmation
            await cl.Message(
                content=f"✅ Merci ! Dossier complet. \nChamps mis à jour : {', '.join(missing_fields)}", 
                author="Agent"
            ).send()

        except Exception as e:
            await cl.Message(content=f"Erreur lors de la mise à jour : {e}").send()
            return
    # -----------------------------------------------------
    # STEP C: EVALUATION IF THE CLIENT IS COVERED
    # -----------------------------------------------------
    
    await cl.Message(content="⚖️ **LLM 3 - Coverage Assessment:** Evaluating claim eligibility...", author="Agent").send()
    
    coverage_assessment = await cl.make_async(call_mistral_to_assess_coverage)(
        dict(),  # put the form with the mandatory information
        client
    )
    
    await cl.Message(
        content=f"🔎 **Coverage Decision:**\n{coverage_assessment}",
        author="Underwriter Bot"
    ).send()

    # Clean up state after successful execution
    cl.user_session.set("current_incident_data", None) 
