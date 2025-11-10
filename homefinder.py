import chainlit as cl
import uuid
import boto3
from langchain_aws import ChatBedrockConverse
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import tool
from langchain_tavily import TavilySearch
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
from langchain_classic.memory import ConversationBufferMemory
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_classic.agents.agent_toolkits.conversational_retrieval.tool import create_retriever_tool
import json
import time
from datetime import datetime
from dotenv import load_dotenv
from osm_utils import geocode_address, query_shelters_near_location

def get_session_history(session_id):
    # Create boto3 session with credentials
    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name="us-east-1"
    )
    return DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        boto3_session=session
    )

def remove_PII(text):
    #language_response = comprehend_client.detect_dominant_language(Text=text).json()
    #language = language_response['']
    comprehend_client = boto3.client(
        service_name="comprehend",
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
    )
    language_code = comprehend_client.detect_dominant_language(Text=text)['Languages'][0]['LanguageCode']
    print(language_code)
    if language_code != "en" or language_code != "es":
        language_code = "en"
    response = comprehend_client.detect_pii_entities(Text=text,LanguageCode=language_code)
    redacted_text = list(text)
    for entity in response['Entities']:
        if entity['Type'] != 'ADDRESS':
            for i in range(entity['BeginOffset'],entity['EndOffset']):
                redacted_text[i] = '*'
    redacted_text = "".join(redacted_text)
    return redacted_text

# Location tools for OSM integration
@tool
def getLocation() -> str:
    """
    Get the user's current location. Checks for cached GPS location from browser first.
    If no cached location is available, returns an error indicating the agent should 
    ask the user for their rough location (city, neighborhood, or address).
    
    Use this tool when you need the user's location for location-based searches.
    If this tool returns a LOCATION_REQUIRED error, you must ask the user for their 
    location before proceeding with location-based queries.
    
    Returns:
        JSON string with location coordinates if available, or error if not.
        Format if available: {"latitude": float, "longitude": float, "source": "browser_gps"}
        Format if unavailable: {"error": "LOCATION_REQUIRED", "message": "...", "suggestion": "..."}
    """
    # Check cache for location
    location = cl.user_session.get("location")
    
    if location:
        return json.dumps({
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "source": location.get("source", "browser_gps")
        })
    else:
        return json.dumps({
            "error": "LOCATION_REQUIRED",
            "message": "No cached location available. The agent should ask the user for their rough location.",
            "suggestion": "Ask the user: 'I'd like to help you find resources nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you.'"
        })


@tool
def findSheltersNearLocation(
    latitude: float = None,
    longitude: float = None,
    address: str = None,
    radius_km: float = 5.0
) -> str:
    """
    Find homeless shelters near a location using OpenStreetMap data.
    
    This tool requires either coordinates (latitude/longitude) OR an address string.
    If an address is provided, it will be geocoded to coordinates first.
    The tool then searches OpenStreetMap for shelters within the specified radius.
    
    Use this tool when the user asks for shelters or resources "near me" or near a 
    specific location. You should call getLocation() first to check for cached location,
    or ask the user for their location if getLocation() returns LOCATION_REQUIRED.
    
    Args:
        latitude: Latitude coordinate (use with longitude, not address)
        longitude: Longitude coordinate (use with latitude, not address)
        address: Address string (e.g., "Dallas, TX", "1201 E 9th St, Dallas", "Oak Cliff")
        radius_km: Search radius in kilometers (default: 5.0)
    
    Returns:
        JSON string with list of shelters found, including name, coordinates, address, etc.
    """
    # Validate input
    if not address and (not latitude or not longitude):
        return json.dumps({
            "error": "INVALID_INPUT",
            "message": "Either address or both latitude and longitude must be provided."
        })
    
    # Geocode if address provided
    if address:
        lat, lon = geocode_address(address)
        if not lat or not lon:
            return json.dumps({
                "error": "GEOCODING_FAILED",
                "message": f"Could not geocode address: {address}. Please try a different format or be more specific."
            })
        # Polite delay for OSM rate limiting
        time.sleep(1)
    else:
        lat, lon = latitude, longitude
    
    # Query shelters
    radius_m = int(radius_km * 1000)
    shelters = query_shelters_near_location(lat, lon, radius_m)
    
    # Format results
    return json.dumps({
        "count": len(shelters),
        "shelters": shelters,
        "search_location": {
            "latitude": lat,
            "longitude": lon,
            "address": address if address else None
        },
        "radius_km": radius_km
    })

# SerpAPI function removed - now using TavilySearch

@cl.on_chat_start
def init():
    #generate user session id for the session
    session_id = uuid.uuid4()
    cl.user_session.set("id",session_id)
    session_id = cl.user_session.get("id")
    
    #define region
    region_name = "us-east-1"
    cl.user_session.set("region_name",region_name)
#create dynamodb instance
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    sts_client = boto3.client(
        'sts',
        aws_access_key_id= os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=region_name
    )
    

# Create Bedrock client first
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region_name,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )

# Create the Bedrock model instance
    model = ChatBedrockConverse(
        model_id="amazon.nova-micro-v1:0",
        client=bedrock_client,
        region_name=region_name,
    )
    
    tools = []
    # Create boto3 session with credentials
    session = boto3.Session(
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=region_name
    )
    history = DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        boto3_session=session
    )

##define tools
    # Use TavilySearch for web search
    search_tool = TavilySearch(
            max_results=5,
            topic="general",
            search_depth="advanced"
    )
    
    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id="VWS7WOM9RG",
        retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 5}},
    )
    
    kb_tool = create_retriever_tool(
        retriever,
        "KnowledgeBaseSearch",
        "Searches for homeless resources and retrieves from Bedrock Knowledge Base"
    )

#append created tools to list
    tools.append(kb_tool)
    tools.append(search_tool)
    tools.append(getLocation)
    tools.append(findSheltersNearLocation)

#define parser
    output_parser = StrOutputParser()

    resource_format = "Name: , Street Address: , Offered Services: , Average Cost: ,  Phone Number: , Website Link: "
    
#define agentic prompt - simplified and more conversational
    agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", f"You are HomeFinder, an empathetic AI assistant that helps people in the DFW area experiencing homelessness find resources. Recognize the user's language that they're speaking in (if it's hard to tell what language they're speaking in, the default language is English), and translate all your responses (and responses coming from any tools) during the conversation in the user speaking language. Before searching for resources, make sure you speak to the user empathetically about their situation, and when it seems clear that they just want the resources and not a detailed conversation about their needs, search for resources with the information you have. When searching for resources, send the search request in the language that the user is speaking in, use the knowledge base FIRST (ensure that the user provided parameters such as location adequately MATCH the resources in the knowledge base, don't just blatantly copy info from it), and if there's still any information still missing you can use the internet for current information. The resources returned must be as close as possible in either proximity and/or need to the user provided location/scenario. Be warm, understanding, and helpful. Ask follow-up questions to further refine your searches before using the internet or knowledge base (ie: location, more info about situation etc) to make it more of a personal experience. Focus on practical help like shelters, food, healthcare, and other essential services. Do a sentiment analysis on each user response and base your responses/resources on how the user seems to be feeling. Don't sound robotic, sound conversational. YOU MUST USE {resource_format} as your format for searching and showing the user the information you found.If the user has seemed to provide any personal identifiable information, kindly request them to not include anything as such (pii information you recieve should be donated by multiple *'s). You have access to location-based tools: (1) getLocation() - Check if user's location is cached from browser GPS. If location is available, returns coordinates. If not available, returns LOCATION_REQUIRED error. When you see LOCATION_REQUIRED, you MUST ask the user for their location empathetically. (2) findSheltersNearLocation() - Find shelters near a location using OpenStreetMap. Requires location as input (coordinates or address). Call getLocation() first to check for cached location. If getLocation() returns LOCATION_REQUIRED, ask user for location first. When user asks for shelters/resources 'near me' or location-based queries: First call getLocation() to check for cached location. If getLocation() returns coordinates, use them with findSheltersNearLocation(). If getLocation() returns LOCATION_REQUIRED, ask user empathetically: 'I'd like to help you find shelters nearby. Could you tell me what city or neighborhood you're in? This helps me search for resources close to you.' After user provides location, call findSheltersNearLocation() with the location. Format results using the resource_format template. Be warm and empathetic when asking for location. Accept flexible input like city names, neighborhoods, or addresses. If geocoding fails, ask user to try a different format."),                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
                ("system","{agent_scratchpad}")
            ]
    )   
#defining cleaning prompt
    cleaning_prompt = ChatPromptTemplate.from_template(
            "Here is the agent's response:\n\n{agent_response}\n\n"
            "Extract and return ONLY the final user-facing answer, so remove all thinking, internal thoughts, processing, and debug info. Don't include any of your thinking either like \"here is the final answer\". Omit any characters (whether it's empty newline characters etc) that make the response less clear or messy to the user. Return it in properly formatted markdown (NO MARKDOWN BOX WITH PLAIN_TEXT) that can render neatly in a Chainlit frontend (similar to chatgpt)"
    )

#define primary agent
    internet_agent = create_tool_calling_agent(
            llm=model,
            tools=tools,
            prompt=agent_prompt
    )
    memory = ConversationBufferMemory(chat_memory=history,memory_key="history",return_messages=True)
#define agent executor with proper error handling and iteration limits
    agent_executor = AgentExecutor(
            agent=internet_agent,
            tools=tools,
            verbose=True,  # Enable verbose for debugging
            max_iterations=5,  # Limit iterations to prevent loops
            max_execution_time=30,  # 30 second timeout
            return_intermediate_steps=True,  # Keep for debugging
            handle_parsing_errors=True,  # Handle parsing errors gracefully
            output_parser=StrOutputParser(),
            memory=memory
    )

    cleaning_chain = cleaning_prompt | model | output_parser
#agent_chain = agent_prompt | model | output_parser

# Wrap the chain with message history functionality
    agent_with_history = RunnableWithMessageHistory(
        runnable=agent_executor,
        get_session_history=get_session_history,
        input_messages_key="question",
        history_messages_key="history",
        output_parser=output_parser
        )
    
    cl.user_session.set("cleaning_layer",cleaning_chain)
    cl.user_session.set("agent_with_history",agent_with_history)


# Handler to receive location from frontend (location.js)
@cl.action_callback("set_location")
async def on_set_location(action):
    """
    Store location from browser GPS in user session.
    Called when location.js successfully obtains GPS coordinates.
    """
    try:
        cl.user_session.set("location", {
            "latitude": action.payload["latitude"],
            "longitude": action.payload["longitude"],
            "timestamp": datetime.now().isoformat(),
            "source": "browser_gps"
        })
        print(f"DEBUG: Location stored: {action.payload['latitude']}, {action.payload['longitude']}")
    except Exception as e:
        print(f"DEBUG: Error storing location: {e}")

        
@cl.on_message
async def main(message: cl.Message):
    
    #retrieve agent and cleaning chains
    agent_with_history = cl.user_session.get("agent_with_history")
    cleaning_chain = cl.user_session.get("cleaning_layer")

    #grab user session id
    config = {"configurable": {"session_id": cl.user_session.get("id")}}
    
    try:
        #get agent response with debugging
        print(f"DEBUG: User message: {message.content}")
        
        #get the PII removed text
        pii_removed_message = remove_PII(message.content)
        response = agent_with_history.invoke({"question": str(pii_removed_message)}, config=config)
        print(f"DEBUG: Agent response: {response}")
        
        #send agent response to be cleaned into user text
        cleaned_response = cleaning_chain.invoke({"agent_response":str(response)})
        print(f"DEBUG: Cleaned response: {cleaned_response}")
        await cl.Message(content=cleaned_response).send()
        
    except Exception as e:
        print(f"DEBUG: Error occurred: {str(e)}")
        await cl.Message(content=f"I'm sorry, I encountered an error: {str(e)}. Please try again or rephrase your question.").send()


#implement function to delete history after session ends (user refreshes or clicks off)
@cl.on_chat_end
def deleteHistory():
    user_id = cl.user_session.get('id')
    region_name = cl.user_session.get('region_name')
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    table = dynamodb.Table('SessionTable')
    response = table.delete_item(Key={'SessionId': user_id})
    

    