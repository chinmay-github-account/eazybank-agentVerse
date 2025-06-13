import asyncio
import json
import uuid
import os

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from google.adk.tools import VertexAiSearchTool, google_search, agent_tool

# --- OpenAPI Tool Imports ---
from google.adk.tools.openapi_tool.openapi_spec_parser.openapi_toolset import OpenAPIToolset

# --- Pub/Sub Imports ---
from google.cloud import pubsub_v1

# --- Load Environment Variables ---
from dotenv import load_dotenv
load_dotenv()

# --- Constants ---
APP_NAME = "eazybank_support_app"
USER_ID = "eazybank_support_user_1"
SESSION_ID = f"session_eazybank_support_{uuid.uuid4()}"  # Unique session ID
GEMINI_MODEL = "gemini-2.0-flash"
PUB_SUB_TOPIC = "eazybank-handoff-topic"

# --- GCP Project and Location from .env ---
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT")
GOOGLE_CLOUD_LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION")

# --- Vertex AI Search Tool ---
DATA_STORE_ID = "projects/adk-hackathon-prj/locations/global/collections/default_collection/dataStores/eazybank-error-description_1749716205468"
eaxybank_error_description_tool = VertexAiSearchTool(data_store_id=DATA_STORE_ID)

# --- OpenAPI Specification to retrieve new account request details  ---
openapi_spec_string = """
{
  "openapi": "3.0.2",
  "info": {
    "title": "EazyBank Account Details Retrieval API",
    "description": "API to retrieve user account details from Firestore based on phone number.",
    "version": "1.0.0"
  },
  "servers": [
    {
      "url": "https://eazybank-new-applicant-checker-839338236077.us-central1.run.app"
    }
  ],
  "paths": {
    "/user_details": {
      "post": {
        "summary": "Retrieve user account details by phone number",
        "description": "Returns user account details (user_name, account_status, reason, account_number, account_balance, credit_card_number) from Firestore based on the provided phone number.",
        "operationId": "getUserDetails",
        "requestBody": {
          "required": true,
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "phone_no": {
                    "type": "integer",
                    "description": "The user's registered phone number.",
                    "example": 1234567890
                  }
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "description": "Successful response - User details retrieved",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "user_name": {
                      "type": "string",
                      "description": "The user's name.",
                      "example": "Sarah Connor"
                    },
                    "account_status": {
                      "type": "string",
                      "description": "The status of the user's account (approved, rejected, in progress, unknown).",
                      "example": "approved"
                    },
                    "reason": {
                      "type": "string",
                      "description": "The reason for account rejection (if applicable).",
                      "example": "Missing address information"
                    },
                    "account_number": {
                      "type": "integer",
                      "description": "The user's account number.",
                      "example": 9876543210
                    },
                    "account_balance": {
                      "type": "string",
                      "description": "The user's account balance.",
                      "example": "$1000.00"
                    },
                    "credit_card_number": {
                      "type": "string",
                      "description": "The user's associated credit card number.",
                      "example": "************1234"
                    }
                  }
                }
              }
            }
          },
          "400": {
            "description": "Bad Request - Missing phone_no in request body",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message.",
                      "example": "Missing phone_no in request body"
                    }
                  }
                }
              }
            }
          },
          "404": {
            "description": "Not Found - User not found with the provided phone_no",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message.",
                      "example": "User not found with phone_no: 1234567890"
                    }
                  }
                }
              }
            }
          },
          "405": {
            "description": "Method Not Allowed - Only POST requests are allowed",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message.",
                      "example": "Only POST requests are allowed"
                    }
                  }
                }
              }
            }
          },
          "500": {
            "description": "Internal Server Error",
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "error": {
                      "type": "string",
                      "description": "Error message.",
                      "example": "Database connection error"
                    }
                  }
                }
              }
            }
          }
        }
      }
    }
  }
}
"""

# --- Create OpenAPIToolset for Account Status Agent ---
account_status_toolset = OpenAPIToolset(
    spec_str=openapi_spec_string,
    spec_str_type='json',
    # No authentication needed
)

# --- Pub/Sub Tool ---
async def publish_to_pubsub(user_message: str, session_id: str) -> str:
    """
    Publishes the given message to the Pub/Sub topic for human agent handoff.

    Args:
        user_message: The user's message/query that triggered the handoff.
        session_id: The current session ID to retrieve conversation history.

    Returns:
        A message indicating the success or failure of the publish operation.
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(GOOGLE_CLOUD_PROJECT, PUB_SUB_TOPIC)

    try:
        # Retrieve conversation history from session service
        session_service = InMemorySessionService() # Initialize session service to retrieve the history
        session = await session_service.get_session(app_name=APP_NAME, user_id=USER_ID, session_id=session_id)

        conversation_history = []
        if session and session.messages:
            conversation_history = [msg.text for msg in session.messages]

        # Package the message
        message_data = {
            "user_message": user_message,
            "conversation_history": conversation_history,
            "user_id": USER_ID,  # Or retrieve from session if available
            "session_id": session_id,
        }
        message_json = json.dumps(message_data)
        message_bytes = message_json.encode("utf-8")

        # Publish the message
        future = publisher.publish(topic_path, message_bytes)
        future.result()  # Block until publish is complete

        return f"Successfully published message to Pub/Sub topic: {topic_path}"
    except Exception as e:
        return f"Error publishing message to Pub/Sub: {e}"

account_status_agent = LlmAgent(
name='account_status_agent',
model=GEMINI_MODEL,
instruction="""
        You are a specialist in helping customer to find out the status of their new bank account application.
        Your primary role is to retrieve the application status via an OpenAPI call to EazyBank's Cloud Run backend.
        When you receive a user identifier (mobile number or phone number) from the Root Agent, use it to query the API.
        If the account_status is active, provide the user with their account number, current balance, and any attached credit cards.
        If the account_status is rejected, provide the user with the reason for rejection.
        After providing the rejection reason, ask the user if they would like more details.
        If the account_status status is 'in progress', then respond to the customer saying that their application is in progress.
        If the account_status is not found or the status is 'unknown' or user needs more details how much longer it will take to process your application, then ask the customer it they want to speak to a human agent for further assistance.
        If you cannot find more detailed information,transfer the conversation to a human agent for further assistance.
        Do not hallucinate.
    """,
description = "To provide the user with the status of their account application status, and to extract account details if active using tools generated from an OpenAPI spec.",
tools = [account_status_toolset],
)

rejection_reason_agent = LlmAgent(
name="rejection_reason_agent",
model=GEMINI_MODEL,
instruction="""
        You're a specialist in providing a detailed explanation of why the user's account application was rejected.
        Your primary role is to provide more detail on why the user's application was rejected.
        Leverage the RAG-based system connected to the Datastore containing EazyBank's policy documents.
        When you receive the rejection reason from the Root Agent, extract the relevant information from the PDF document and provide a clear explanation to the user.
        If you cannot find more detailed information, inform the user and optionally ask the customer it they want to speak to a human agent for further assistance..
    """,
description = "To provide a detailed explanation of why the user's account application was rejected.",
tools=[eaxybank_error_description_tool],
)

market_insights_agent = LlmAgent(
name="market_insights_agent",
model=GEMINI_MODEL,
instruction = """
        You're a specialist in Google Search.
        Your primary role is to fetch the latest stock price and relevant market news for EazyBank.
        When the Root Agent transfers a user asking about EazyBank's performance, use the Google Search tool to gather the necessary information.
        Provide the user with the stock price and a brief summary of any relevant market news.
        Always cite your sources (e.g., 'According to Google Finance...').
    """,
description = "Agent to answer questions using Google Search to the root agent.",
tools=[google_search]
)

human_handoff_agent = LlmAgent(
name='human_handoff_agent',
model=GEMINI_MODEL,
instruction="""
        You're a specialist in agent for human agent delegation.
        Your primary role is to forward the user's request to a human agent.
        When you are activated, use the tool publish_to_pubsub with the user's message to send the user's message and conversation history to the human agent queue.
        Inform the user that they are being transferred to a human agent and that a representative will be with them shortly.
    """,
description = "AI Agent to seamlessly transition the user to a live human agent.",
tools=[publish_to_pubsub],
)

root_agent = LlmAgent(
name="RootAgent",
model=GEMINI_MODEL,
description="Master Agent for Orchestration of EazyBank Support",
instruction="""
        Hello! I'm your friendly AI assistant at EazyBank. I'm here to help you with your banking needs.

        My main job is to understand what you're asking and connect you with the right expert agent who can best assist you. Please be patient, and I will try my best to help you.

        Here's how I work:

        Understanding Your Request: I will listen carefully to your questions and requests. I'll pay attention to keywords like 'account status', 'rejection reason', 'stock price', 'market performance', 'human agent', and 'help' to figure out what you need.

        Account Application Status (account_status_agent):

        If you're asking about the status of an account application, I'll first need your registered mobile number to find your application.
        If you provide your registered mobile number, I'll connect you to account_status_agent, who can check the status for you.
        account_status_agent can also provide account details (account number, balance, credit card info) if your account has been approved.

        Rejection Details (rejection_reason_agent):

        If you're asking for more information about why your account application was rejected, I'll connect you to rejection_reason_agent. rejection_reason_agent can provide a more detailed explanation.

        Market Insights (market_insights_agent):

        If you're asking about EazyBank's performance in the market or our stock price or fund value, I'll connect you to market_insights_agent. market_insights_agent can give you the latest information.

        Human Assistance (human_handoff_agent):

        If you want to speak to a human agent, or if I think your request is too complicated for me to handle, I'll connect you to human_handoff_agent. human_handoff_agent will ensure a smooth transfer to a live agent.

        Interaction Style:

        I'll always be polite and friendly.
        I'll try to use clear and easy-to-understand language.

        Context Transfer:

        When I connect you to another agent, I'll provide them with a brief summary of what we've already discussed, so you don't have to repeat yourself.

        Greetings:

        If you simply greet me with a 'Hello' or 'Hi', I'll respond politely. Thank the user for contacting EazyBank  and ask how I can help you with your banking needs.
    """,
tools=[agent_tool.AgentTool(agent=account_status_agent),agent_tool.AgentTool(agent=rejection_reason_agent),agent_tool.AgentTool(agent=market_insights_agent), agent_tool.AgentTool(agent=human_handoff_agent)],
)

# Session and Runner
session_service = InMemorySessionService()
session = session_service.create_session(app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID)
runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)
