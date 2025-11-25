import chainlit as cl
import uuid
import boto3
from langchain_aws import ChatBedrockConverse
import os
from langchain_core.output_parsers import StrOutputParser
from langchain_tavily import TavilySearch
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
from langchain_classic.memory import ConversationBufferMemory
from langchain_aws.retrievers import AmazonKnowledgeBasesRetriever
from langchain_classic.agents.agent_toolkits.conversational_retrieval.tool import create_retriever_tool
import json
from dotenv import load_dotenv
from location_request import get_user_location
from location_tools_langchain import get_user_location_tool, geocode_address_tool, search_nearby_tool, reset_location_cache

region_name = "us-east-1"
def get_secret_key(secret_name):
    client = boto3.client('secretsmanager',region_name=region_name)
    
    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except Exception as e:
        raise e
    else:
        if 'SecretString' in get_secret_value_response:
            secret = get_secret_value_response['SecretString']
            return json.loads(secret)


def get_session_history(session_id):
    # Create boto3 session with credentials
    session = boto3.Session(
        region_name="us-east-1"
    )
    return DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        boto3_session=session,
    )

def remove_PII(text):
    #language_response = comprehend_client.detect_dominant_language(Text=text).json()
    #language = language_response['']
    comprehend_client = boto3.client(
        service_name="comprehend",
        region_name=region_name
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

# SerpAPI function removed - now using TavilySearch

# Chainlit action handler to receive location from frontend
@cl.action_callback("set_location")
async def on_set_location(action: cl.Action):
    """
    Receives location coordinates from location.js and stores in user session
    """
    try:
        print(f"🔔 Action received: {action.name}")
        print(f"📦 Action payload: {action.payload}")
        print(f"📦 Action payload type: {type(action.payload)}")
        
        # Handle different payload formats
        if isinstance(action.payload, dict):
            latitude = action.payload.get("latitude")
            longitude = action.payload.get("longitude")
        else:
            # Try to get from action directly
            latitude = getattr(action.payload, "latitude", None)
            longitude = getattr(action.payload, "longitude", None)
        
        print(f"📍 Extracted - Latitude: {latitude}, Longitude: {longitude}")
        
        if latitude is not None and longitude is not None:
            # Convert to float if they're strings
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError) as e:
                print(f"⚠️ Could not convert to float: {e}")
                return
            
            cl.user_session.set("user_latitude", latitude)
            cl.user_session.set("user_longitude", longitude)
            print(f"✅ Location received and stored: ({latitude}, {longitude})")
        else:
            print(f"⚠️ Invalid location payload: {action.payload}")
            print(f"⚠️ Latitude: {latitude}, Longitude: {longitude}")
    except Exception as e:
        print(f"❌ Error handling location action: {e}")
        import traceback
        traceback.print_exc()

@cl.on_chat_start
async def init():
    # Reset location cache for new session
    reset_location_cache()
    
    #generate user session id for the session
    session_id = uuid.uuid4()
    cl.user_session.set("id",session_id)
    session_id = cl.user_session.get("id")
    
    #define region
    cl.user_session.set("region_name",region_name)
    
    # Initialize location storage (will be set by action callback)
    cl.user_session.set("user_latitude", None)
    cl.user_session.set("user_longitude", None)
    print("✅ Location session variables initialized")
#create dynamodb instance
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    sts_client = boto3.client(
        'sts',
        region_name=region_name
    )
    

# Create Bedrock client first
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region_name,
    )

# Create the Bedrock model instance
    model = ChatBedrockConverse(
        model_id="amazon.nova-lite-v1:0",
        client=bedrock_client,
        region_name=region_name,
    )
    
    tools = []
    # Create boto3 session with credentials
    session = boto3.Session(
        region_name=region_name
    )
    history = DynamoDBChatMessageHistory(
        table_name="SessionTable",
        session_id=session_id,
        boto3_session=session
    )

##define tools
    os.environ["TAVILY_API_KEY"] = get_secret_key("tavapikey")["TAVILY_API_KEY"]
    # Use TavilySearch for web search
    search_tool = TavilySearch(
            max_results=5,
            topic="general",
            search_depth="advanced"
    )
    
    retriever = AmazonKnowledgeBasesRetriever(
        knowledge_base_id="VWS7WOM9RG",
        retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 5}},
        region_name=region_name
    )
    
    kb_tool = create_retriever_tool(
        retriever,
        "KnowledgeBaseSearch",
        "Searches for homeless resources and retrieves from Bedrock Knowledge Base"
    )

#append created tools to list
    tools.append(kb_tool)
    tools.append(search_tool)
    tools.append(get_user_location_tool)
    tools.append(geocode_address_tool)
    tools.append(search_nearby_tool)

#define parser
    output_parser = StrOutputParser()

    resource_format = "Name: , Street Address: , Offered Services: , Average Cost: ,  Phone Number: , Website Link: "
    
#define agentic prompt - simplified and more conversational
    system_prompt = f"""You are HomeFinder, an empathetic AI assistant that helps people in the DFW area experiencing homelessness find resources.

LANGUAGE:
- Recognize the user's language (default to English if unclear)
- Translate all responses and tool outputs to the user's language

CONVERSATION STYLE:
- Be warm, understanding, and helpful - don't sound robotic
- Speak empathetically about their situation before searching
- When the user just wants resources quickly, search with available info
- Ask follow-up questions to refine searches (location, situation details)
- Do sentiment analysis and adapt responses to how user seems to be feeling

SEARCHING FOR RESOURCES:
- Use the knowledge base FIRST
- Ensure user-provided location matches resources in knowledge base
- Use internet search for missing/current information
- Resources must be close in proximity and/or need to user's location/scenario
- Focus on: shelters, food, healthcare, essential services

OUTPUT FORMAT:
- YOU MUST USE this format: {resource_format}

PRIVACY:
- If user provides PII, kindly ask them not to include it
- Redact any PII received (show as multiple *'s)

LOCATION TOOLS (CRITICAL - READ CAREFULLY):
- For 'near me', 'nearby', 'closest to me': call get_user_location_tool exactly ONCE
- AFTER calling get_user_location_tool, check the response:
  * If it contains coordinates: proceed with search_nearby_tool
  * If it says "error", "denied", "failed", or "ALREADY FAILED": DO NOT call get_user_location_tool again. Instead, IMMEDIATELY respond to the user with a friendly message asking for their location. Example: "I wasn't able to access your GPS. No worries though! Could you share a rough location - like a neighborhood, nearby intersection, or landmark? It doesn't have to be exact, any general area helps me find resources near you."
- When user provides an address/location: use geocode_address_tool ONCE to convert to coordinates
- If geocode returns "ALREADY GEOCODED": DO NOT call it again. Use the coordinates from the message.
- After getting coordinates, use search_nearby_tool to find places
- NEVER call the same tool twice in a row with the same parameters
- If ANY tool response contains "STOP CALLING" or "ALREADY": immediately stop calling that tool and use the data provided
"""

    agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", system_prompt),
                MessagesPlaceholder(variable_name="history"),
                ("human", "{question}"),
                ("system", "{agent_scratchpad}")
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
            max_iterations=3,  # Limit iterations to prevent loops
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
        response = await agent_with_history.ainvoke({"question": str(pii_removed_message)}, config=config)
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
