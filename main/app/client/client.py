"""
client.py

This file implements a LangChain MCP client that:
  - Loads configuration from a JSON file specified by the config environment variable.
  - Connects to one or more MCP servers defined in the config.
  - Loads available MCP tools from each connected server.
  - Uses the Google Gemini API (via LangChain) to create a React agent with access to all tools.
  - Runs an interactive chat loop where user queries are processed by the agent.

Detailed explanations:
  - Retries (max_retries=2): If an API call fails due to transient issues (e.g., timeouts), it will retry up to 2 times.
  - Temperature (set to 0): A value of 0 means fully deterministic output; increase this for more creative responses.
  - Environment Variable: config should point to a config JSON that defines all MCP servers.
"""

import asyncio                        # For asynchronous operations
import os                             # To access environment variables and file paths
import sys                            # For system-specific parameters and error handling
import json                           # For reading and writing JSON data
from contextlib import AsyncExitStack # For managing multiple asynchronous context managers

from mcp import ClientSession, StdioServerParameters  # For managing MCP client sessions and server parameters
from mcp.client.stdio import stdio_client             # For establishing a stdio connection to an MCP server

from langchain_mcp_adapters.tools import load_mcp_tools  # Adapter to convert MCP tools to LangChain compatible tools
from langgraph.prebuilt import create_react_agent        # Function to create a prebuilt React agent using LangGraph
from langchain_google_genai import ChatGoogleGenerativeAI  # Wrapper for the Google Gemini API via LangChain
from langchain_core.messages import HumanMessage, AIMessage


from dotenv import load_dotenv
load_dotenv()  # Load environment variables from a .env file (e.g., GOOGLE_API_KEY)

class CustomEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle non-serializable objects returned by LangChain.
    If the object has a 'content' attribute (such as HumanMessage or ToolMessage), serialize it accordingly.
    """
    def default(self, o):
        # Check if the object has a 'content' attribute
        if hasattr(o, "content"):
            # Return a dictionary containing the type and content of the object
            return {"type": o.__class__.__name__, "content": o.content}
        # Otherwise, use the default serialization
        return super().default(o)


def read_config_json():
    """
    Reads the MCP server configuration JSON.

    Priority:
      1. Try to read the path from the config environment variable.
      2. If not set, fallback to a default file 'config.json' in the same directory.

    Returns:
        dict: Parsed JSON content with MCP server definitions.
    """
    # Attempt to get the config file path from the environment variable
    config_path = os.getenv("config")

    if not config_path:
        # If environment variable is not set, use a default config file in the same directory as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(script_dir, "config.json")
        print(f"config not set. Falling back to: {config_path}")

    try:
        # Open and read the JSON config file
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception as e:
        # If reading fails, print an error and exit the program
        print(f" Failed to read config file at '{config_path}': {e}")
        sys.exit(1)


llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",             # Specify the Google Gemini model variant to use
    temperature=0,                            # Set temperature to 0 for deterministic responses
    max_retries=2,                            # Set maximum retries for API calls to 2 in case of transient errors
    google_api_key=os.getenv("GOOGLE_API_KEY")  # Retrieve the Google API key from environment variables
)

class MCPAgentWrapper:
    def __init__(self):
        self.stack = AsyncExitStack()
        self.agent = None
        self.chat_history = []  # Stores HumanMessage and AIMessage objects

    async def initialize(self):
        config = read_config_json()
        mcp_servers = config.get("mcpServers", {})
        if not mcp_servers:
            raise RuntimeError("No MCP servers found in the configuration.")

        await self.stack.__aenter__()
        tools = []

        for server_name, server_info in mcp_servers.items():
            try:
                print(f"\nConnecting to MCP Server: {server_name}...")
                server_params = StdioServerParameters(
                    command=server_info["command"],
                    args=server_info["args"]
                )
                read, write = await self.stack.enter_async_context(stdio_client(server_params))
                session = await self.stack.enter_async_context(ClientSession(read, write))
                await session.initialize()
                server_tools = await load_mcp_tools(session)
                for tool in server_tools:
                    print(f"  Loaded tool: {tool.name}")
                tools.extend(server_tools)
                print(f"✔ {len(server_tools)} tools loaded from {server_name}.")
            except Exception as e:
                print(f"✘ Failed to connect to server {server_name}: {e}")

        if not tools:
            raise RuntimeError("No tools loaded from any server.")

        self.agent = create_react_agent(llm, tools)
        print("Agent initialized with tools.")

    async def invoke(self, user_input: str):
        """
        Adds the user query to the history, sends it to the agent,
        appends the response to history, and returns the response.
        """
        if not self.agent:
            raise RuntimeError("Agent not initialized. Call initialize() first.")
        print("Hi", user_input)
        # Add user input to history
        self.chat_history.append(HumanMessage(content=user_input))

        # Invoke with full message history
        response = await self.agent.ainvoke({"messages": self.chat_history})

        # Append latest AI response to history
        ai_messages = [
            msg for msg in response.get("messages", [])
            if isinstance(msg, AIMessage) and msg.content.strip()
        ]
        if ai_messages:
            self.chat_history.append(ai_messages[-1])

        return response

    async def run_agent(self):
        """
        Interactive CLI loop for testing.
        """
        if not self.agent:
            await self.initialize()

        print("\nMCP Client Ready! Type 'quit' to exit.")
        while True:
            query = input("\nQuery: ").strip()
            if query.lower() == "quit":
                break
            try:
                response = await self.invoke(query)
                ai_messages = [
                    msg.content for msg in response["messages"]
                    if isinstance(msg, AIMessage) and msg.content.strip()
                ]
                print(f"\n{ai_messages[-1] if ai_messages else '⚠️ No AIMessage found.'}")
            except Exception as e:
                print(f" Error: {e}")
