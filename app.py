import os, shutil, uuid, uvicorn
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi.responses import FileResponse, JSONResponse
from fastapi import FastAPI, File, UploadFile, HTTPException
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.teams import RoundRobinGroupChat

from File_Operations import raw_text_from_file, write_point_to_docx, write_point_to_pdf
from Prompt import COMPLIANCE_CHECK_PROMPT, CORRECTION_PROMPT, WRITER_PROMPT
# from Config_Data import load_config_data

# groq_api_key = load_config_data["GROQ_API_KEY"]
# groq_model = load_config_data["GROQ_llama_3_3_70B_VERSATILE"]
# groq_model_1 = load_config_data["GROQ_llama_3_3_70B_SPECTEC"]
# groq_base_url = load_config_data["GROQ_BASE_URL"]
# UPLOAD_DIR = Path(load_config_data["FILE_PROCESSING_PATH"])
groq_api_key = os.getenv("GROQ_API_KEY")
groq_model = os.getenv("GROQ_llama_3_3_70B_VERSATILE")
groq_model_1 = os.getenv("GROQ_llama_3_3_70B_SPECTEC")
groq_base_url = os.getenv("GROQ_BASE_URL")
UPLOAD_DIR = Path(os.getenv("FILE_PROCESSING_PATH"))


os.makedirs(UPLOAD_DIR, exist_ok=True)

site = FastAPI(title="Document Compliance API")

ALLOWED_EXTENSIONS = {"pdf", "docx"}

model_client = OpenAIChatCompletionClient(
        model = groq_model,
        api_key = groq_api_key,
        base_url = groq_base_url,
        temperature = 0.3,
        max_tokens = 512,
        model_info = {
            "vision": False,
            "function_calling": True,
            "json_output": False,
            "family": "unknown",
        },
    )

async def compliance_check(text:str) -> str:
    compliance_check_agent = AssistantAgent(
        name="Compliance_Check_Assistant",
        description="This agent is responsible for checking compliance in provided text.",
        system_message=COMPLIANCE_CHECK_PROMPT,
        model_client=model_client,
    )
    stream = compliance_check_agent.run(task=text)
    return await stream

async def correct_writer(text:str):
    compliance_correction_agent = AssistantAgent(
        name="Compliance_Correction_Assistant",
        description="Ensures text compliance with Federal Plain Language Guidelines by correcting grammar, sentence structure, and clarity.",
        system_message=CORRECTION_PROMPT,
        model_client=model_client,
    )
    document_writer_agent = AssistantAgent(
        name = "Document_Writer_Agent",
        description = "Writes structured text to DOCX or PDF files based on function output without modifications.",
        system_message = WRITER_PROMPT,
        model_client = model_client,
        tools = [write_point_to_docx, write_point_to_pdf],
        reflect_on_tool_use = True,
    )
    agent_list = [compliance_correction_agent, document_writer_agent]
    termination = TextMentionTermination("TERMINATE")
    group_chat = RoundRobinGroupChat(agent_list, termination_condition=termination, max_turns=len(agent_list))
    stream = group_chat.run(task=text)
    return await stream

@site.post("/compliance_check", summary="Upload and assess document compliance")
async def check_compliance(file: UploadFile = File(...)):
    try:
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF and DOCX allowed.")
        
        unique_filename = f"{uuid.uuid4()}_{file.filename.rsplit('.', 1)[0]}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        text_from_file = await raw_text_from_file(file_path)
        compliance_status = await compliance_check(text_from_file)
        status = compliance_status.messages[1].content.strip()
        return JSONResponse(content = {"compliance_status":status})
    except Exception as ed:
        return str(f"Error occured: {ed}")
    finally:
        os.remove(file_path)

@site.post("/updated_document_compliance", summary="Upload and assess document compliance and correct it")
async def process_document(file: UploadFile = File(...)):
    try:
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported file format. Only PDF and DOCX allowed.")
        
        unique_filename = f"{uuid.uuid4()}_{file.filename.rsplit('.', 1)[0]}.{file_extension}"
        file_path = os.path.join(UPLOAD_DIR, unique_filename)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        raw_text = await raw_text_from_file(file_path)
        compliance_status = await compliance_check(raw_text)
        input_text = f"compliance status: {compliance_status}\nfile name: Processed_{file.filename}\ntext: {raw_text}"
        _final_output = await correct_writer(input_text)
        processed_file_path = f"{UPLOAD_DIR}\\Processed_{file.filename}"
        return FileResponse(processed_file_path, filename=f"Processed_{file.filename}")
    except Exception as err:
        return str(f"Error occured: {err}")
    finally:
        os.remove(file_path)

if __name__ == "__main__":
    uvicorn.run(site, port=8888)