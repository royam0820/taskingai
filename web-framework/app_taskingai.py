from fastapi import FastAPI, HTTPException, Body, Depends
from fastapi.responses import FileResponse, JSONResponse
import logging
import os
from dotenv import load_dotenv
import taskingai
import taskingai.assistant

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# Set the environment variable
taskingai.init(api_key=os.environ["TASKINGAI_API_KEY"])

# Making the app
app = FastAPI()
chat_sessions = {}  # Fixed typo here

def get_assistant():
    return taskingai.assistant

# Chat logic
class ChatLogic:
    async def chat(self, assistant, user_id, user_message):
        raise NotImplementedError

    async def _chat_logic(
        self, assistant: taskingai.assistant, assistant_id, user_id, user_message
    ):
        try:
            chat_id = chat_sessions.get(user_id)
            if not chat_id:
                chat = assistant.create_chat(assistant_id=assistant_id)
                if not chat:
                    raise Exception("Failed to create chat session")
                chat_id = chat.chat_id
                chat_sessions[user_id] = chat_id

            assistant_message = assistant.create_message(
                assistant_id=assistant_id,
                chat_id=chat_id,
                text=user_message,
            )
            if not assistant_message:
                raise Exception("Failed to get assistant's response")

            return assistant_message.content.text

        except Exception as e:
            logger.error(f"Error occurred: {e}")
            return None

# Chat with fallback
class ChatWithFallback(ChatLogic):
    def __init__(self, chat_logic):
        self._chat_logic = chat_logic

    async def chat(self, assistant, assistant_id1, assistant_id2, user_id, user_message):
        response = await self._chat_logic(assistant, assistant_id1, user_id, user_message)
        if response is None:
            logger.info("Using fallback assistant")
            response = await self._chat_logic(assistant, assistant_id2, user_id, user_message)
        return JSONResponse(content={"assistant_response": response})

# Create a factory pattern to use the chat with fallback or the chat without fallback
def chat_logic_factory(use_fallback=True):  # Added use_fallback parameter
    chat_logic = ChatLogic()
    if use_fallback:  # fallback is True
        return ChatWithFallback(chat_logic)
    else:
        return chat_logic

@app.get("/")
async def read_index():
    try:
        return FileResponse("static/index.html")
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Static file not found")

@app.post("/chat")
async def chat_endpoint(
    user_id: str,
    user_message: str = Body(..., embed=True),
    assistant: taskingai.assistant = Depends(get_assistant),
):
    chat_logic = chat_logic_factory()
    try:
        response = await chat_logic.chat(assistant, user_id, user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error during chat processing: {str(e)}")
    
    if response is None:
        raise HTTPException(status_code=500, detail="Failed to get a response from the assistant")

    logger.info(f"Chat session for user {user_id} completed successfully.")
    return {"assistant_response": response}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8080)
