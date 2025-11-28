import chainlit as cl
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from enum import Enum
import json
import os

from mistralai import Mistral



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
    shoud_do_action: str = Field(
        description="Based on the user input see if we need to do an action (if it doesnt talk about house damage, we do nothing). Possible values: [True, False]. "
    )
    damage_type: str = Field(
        description="Type of damage (e.g., Fire, Water Leak, Storm). Possible values: [Fire, Water, Storm]. "
    )
    incident_date: Optional[str] = Field(description="The exact date and time of the incident. Required for execution.")
    damage_location: Optional[str] = Field(description="The precise location of the damage (e.g., kitchen, basement, roof). Required for execution.")
    is_secure: Optional[bool] = Field(description="True if the area is secured (e.g., fire out, leak stopped), False otherwise. Required for execution.")

    def get_critical_fields(self) -> List[str]:
        return ["shoud_do_action", "incident_date", "damage_location", "is_secure"]
    


# ==========================================
# 2. LLM FUNCTIONS (Mistral API Calls)
# ==========================================

def call_mistral_for_json(user_text: str, client: Mistral) -> Dict[str, Any]:
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


def call_mistral_for_query(missing_fields: List[str], client: Mistral) -> str:
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


def call_mistral_for_synthesis(final_prompt: str, client: Mistral) -> str:
    """LLM 3 : Synthétise la réponse humanisée après l'exécution déterministe."""
    
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
    """Determines which critical fields are missing (null) for execution."""
    
    # Using the PropertyClaim instance to get critical fields
    instance = PropertyClaim(**data)
    critical_fields = instance.get_critical_fields()
    
    missing = []
    for field_name in critical_fields:
        value = data.get(field_name)
        # Manquant si None, ou si c'est le montant et qu'il est 0.0
        if value is None or (isinstance(value, float) and value == 0.0):
            missing.append(field_name.replace('_', ' ').title())
            
    return missing


@cl.on_chat_start
async def start():
    global client
    global MISTRAL_MODEL
    # --- Configuration ---
    MISTRAL_MODEL = "mistral-tiny" 

    api_key = "DNJ2Duuaislp57c9ezYHX85ZvWhCQgIR"
    client = Mistral(api_key=api_key)

    cl.user_session.set("current_incident_data", None)
    await cl.Message(
        content="👋 Welcome to HomeResQ. How can I assist you today?",
    ).send()


@cl.on_message
async def main(message: cl.Message):
    global client
    user_input = message.content
    
    current_data = cl.user_session.get("current_incident_data")
    
    # Concaténation de l'historique de collecte si nécessaire
    if current_data:
        user_input = f"Previous context: {json.dumps(current_data)}. New information: {user_input}"

    # -----------------------------------------------------
    # ÉTAPE A : EXTRACTION DES DONNÉES (LLM 1 Spécialisé)
    # -----------------------------------------------------
    await cl.Message(content="🧠 **LLM 1 - Extraction :** Filling the PropertyClaim schema...", author="Agent").send()

    try:
        json_str = await cl.make_async(call_mistral_for_json)(user_input, client)
    except Exception as e:
        await cl.Message(content=f"Error during Mistral call (Extraction): {e}.", author="System Error").send()
        return

    # Mise à jour de l'état
    cl.user_session.set("current_incident_data", json_str)
    
    validated_instance: PropertyClaim = PropertyClaim.model_validate_json(json_str)
    # Affichage du JSON extrait pour la traçabilité (avec conversion Enum)
    json_trace = {k: (v.value if isinstance(v, Enum) else v) for k, v in validated_instance.model_dump().items()}
    await cl.Message(
        content=f"**JSON Extrait :**\n```json\n{json.dumps(json_trace, indent=2)}\n```",
        author="Trace du Modèle"
    ).send()

    # -----------------------------------------------------
    # ÉTAPE B : VALIDATION ET DEMANDE D'INFO MANQUANTE
    # -----------------------------------------------------
        
    missing_fields = find_missing_critical_data(validated_instance.model_dump())
            
    if missing_fields:
        # LLM 2: Generates Question and pauses execution
        await cl.Message(content="❓ **Validation:** Missing critical data detected...", author="Agent").send()
        query_message = await cl.make_async(call_mistral_for_query)(missing_fields, client)
        
        await cl.Message(
            content=query_message,
            author="Assur-Bot"
        ).send()
        return 
    
    # -----------------------------------------------------
    # ÉTAPE C : EXÉCUTION DÉTERMINISTE FINALE
    # -----------------------------------------------------
    
    deterministic_result = determinist_path(validated_instance)
        
    await cl.Message(
        content=f"🛠️ **Deterministic Actions Executed:**\n{deterministic_result}",
        author="Agent"
    ).send()

    # Clean up state after successful execution
    cl.user_session.set("current_incident_data", None) 

    # -----------------------------------------------------
    # STEP D: SYNTHESIS (LLM 3)
    # -----------------------------------------------------
    final_prompt = (
        f"The type of house damage handled was: {validated_instance.damage_type}. The actions taken are: {deterministic_result}"
    )
    
    final_answer = await cl.make_async(call_mistral_for_synthesis)(final_prompt, client)
    
    await cl.Message(
        content=f"📣 **Final humanized response:**\n{final_answer}",
        author="Assur-Bot"
    ).send()