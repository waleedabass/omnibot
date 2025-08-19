import uvicorn
from fastapi import FastAPI,Request
from pydantic import BaseModel
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from app.client.client import MCPAgentWrapper

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

from fastapi.staticfiles import StaticFiles
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Global instance of the wrapper
mcp_wrapper = MCPAgentWrapper()

@app.on_event("startup")
async def startup_event():
    await mcp_wrapper.initialize()

class QueryInput(BaseModel):
    message: str

@app.post("/chat")
async def chat(request: Request):
    data = await request.json()
    message = data.get("message", "")
    message=f"You are omnibot a personal assistant built by waleed abbas. Now cater this query: {message}"
    try:
        response = await mcp_wrapper.invoke(message)
        
        if hasattr(response, 'get'):
            ai_messages = [
                msg for msg in response.get("messages", [])
                if hasattr(msg, "content") and getattr(msg, "content", "").strip()
            ]
        else:
            print(f"Response is not a dict-like object: {response}")
            return {"response": "Invalid response format from MCP wrapper"}

        print(f"AI messages found: {len(ai_messages)}")
        for i, msg in enumerate(ai_messages):
            print(f"Message {i}: {msg.content[:100]}")

        if not ai_messages:
            return {"response": "No AIMessage returned. Try rephrasing your request."}

        return {"response": ai_messages[-1].content}

    except Exception as e:
        import traceback
        print(f"Error in chat endpoint: {e}")
        traceback.print_exc()
        return {"error": str(e)}


@app.get("/")
async def index():
    return FileResponse("app/templates/index.html")

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
