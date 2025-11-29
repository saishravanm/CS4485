from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
import chainlit as cl
import uuid
import boto3
import re
from langchain_aws import ChatBedrockConverse
import os
from typing import Optional
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
import chainlit.data as cl_data
import smtplib
from email.message import EmailMessage
from location_tools_langchain import (
    reset_location_state,
    ensure_location,
    search_resources,
    format_results_for_user,
    set_pending_query,
    get_pending_query,
    is_waiting_for_address
)
from location_store import store_session_location, clear_session_location, geocode_and_store

region_name = "us-east-1"
current_llm_message = ""
dynamodb = boto3.resource("dynamodb", region_name=region_name)
global_session_id = "" 

class CustomDataLayer(cl_data.BaseDataLayer):
    async def upsert_feedback(self, feedback):
        feedback_table = dynamodb.Table("user_feedback")
        data = {
         "llm_message":current_llm_message,
         "sentiment":feedback.value,
         "feedback":feedback.comment,   
        }
        item_key = {
            'SessionId':global_session_id
        }
        feedback_table.update_item(
            Key=item_key,
            UpdateExpression="SET #feedbackList = list_append(if_not_exists(#feedbackList, :empty_list),:val)",
            ExpressionAttributeNames={
                '#feedbackList':'feedbackList'
            },
            ExpressionAttributeValues={
                ':val':[data],
                ':empty_list': []
            },
        )
        return await super().upsert_feedback(feedback)
    
    async def build_debug_url(self):
        return await super().build_debug_url()
    async def close(self):
        return await super().close()
    async def create_element(self, element):
        return await super().create_element(element)
    async def create_step(self, step_dict):
        return await super().create_step(step_dict)
    async def create_user(self, user):
        return await super().create_user(user)
    async def delete_element(self, element_id, thread_id = None):
        return await super().delete_element(element_id, thread_id)
    async def delete_feedback(self, feedback_id):
        return await super().delete_feedback(feedback_id)
    async def delete_step(self, step_id):
        return await super().delete_step(step_id)
    async def delete_thread(self, thread_id):
        return await super().delete_thread(thread_id)
    async def get_element(self, thread_id, element_id):
        return await super().get_element(thread_id, element_id)
    async def get_thread(self, thread_id):
        return await super().get_thread(thread_id)
    async def get_thread_author(self, thread_id):
        return await super().get_thread_author(thread_id)
    async def get_user(self, identifier):
        return await super().get_user(identifier)
    async def list_threads(self, pagination, filters):
        return await super().list_threads(pagination, filters)
    async def update_step(self, step_dict):
        return await super().update_step(step_dict)
    async def update_thread(self, thread_id, name = None, user_id = None, metadata = None, tags = None):
        return await super().update_thread(thread_id, name, user_id, metadata, tags)

cl_data._data_layer=CustomDataLayer()

@cl.on_message
async def on_starter(message: cl.Message):
    print(message.content)
    if message.content == "Emergency":
        await cl.Message("If you are currently in an emergency, please call 911.\n Crisis Hotline: 988, Homeless Hotline: (555) 211-HELP, Domestic Violence Hotline: (555) 799-SAFE").send()
    else:
        main(message)

@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="Find Shelter",
            message="I'd like to find a shelter near my location."
        ),
        cl.Starter(
            label="Find Food Resources",
            message ="I'd like to find food resources near my location."
        ),
        cl.Starter(
            label="Find Healthcare",
            message="I'd like to find healthcare near my location."
        ),
        cl.Starter(
            label="Find Job Help",
            message="I'd like to find job help near my location."
        ),
        cl.Starter(
            label="Emergency",
            message="Emergency"
        ),
        cl.Starter(
            label="Nearby Resources",
            message="I'd like to find resources near me."
        )
    ]

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
        if entity['Type'] == 'ADDRESS' or entity['Type'] == "PHONE" or entity['Type'] == "NAME":
            pass
        else:
            print(entity['Type'])
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
        print(f"Action received: {action.name}")
        print(f"Action payload: {action.payload}")
        print(f"Action payload type: {type(action.payload)}")
        
        # Handle different payload formats
        if isinstance(action.payload, dict):
            latitude = action.payload.get("latitude")
            longitude = action.payload.get("longitude")
        else:
            # Try to get from action directly
            latitude = getattr(action.payload, "latitude", None)
            longitude = getattr(action.payload, "longitude", None)
        
        print(f"Extracted - Latitude: {latitude}, Longitude: {longitude}")
        
        if latitude is not None and longitude is not None:
            # Convert to float if they're strings
            try:
                latitude = float(latitude)
                longitude = float(longitude)
            except (ValueError, TypeError) as e:
                print(f"Could not convert to float: {e}")
                return
            
            cl.user_session.set("user_latitude", latitude)
            cl.user_session.set("user_longitude", longitude)
            print(f"Location received and stored: ({latitude}, {longitude})")
        else:
            print(f"Invalid location payload: {action.payload}")
            print(f"Latitude: {latitude}, Longitude: {longitude}")
    except Exception as e:
        print(f"Error handling location action: {e}")
        import traceback
        traceback.print_exc()

@cl.on_chat_start
async def init():
    # Reset location state for new session
    reset_location_state()
    
    # Generate user session id for the session
    session_id = str(uuid.uuid4())
    cl.user_session.set("id", session_id)
    print(f"New session started: {session_id}")
    global global_session_id
    global_session_id = session_id
    #define region
    cl.user_session.set("region_name",region_name)
    
    # Initialize location storage (will be set by action callback)
    cl.user_session.set("user_latitude", None)
    cl.user_session.set("user_longitude", None)
    print("Location session variables initialized")
#create dynamodb instance
    sts_client = boto3.client(
        'sts',
        region_name=region_name
    )
    

# Create Bedrock client first
    bedrock_client = boto3.client(
        service_name="bedrock-runtime",
        region_name=region_name,
    )

# Create the Bedrock model instance (main agent)
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
        retrieval_config={"vectorSearchConfiguration": {"numberOfResults": 4}},
        region_name=region_name
    )
    
    kb_tool = create_retriever_tool(
        retriever,
        "KnowledgeBaseSearch",
        "Searches for homeless resources and retrieves from Bedrock Knowledge Base. In order to return the response in the user selected language, specify using (Generate the answer in [USER_SPECIFIED_LANGUAGE]). So for example, if the user asks something in Spanish, you MUST include (Generate the answer in Spanish) in the query when calling the tool. The resources found must all be free, and/or of a low-cost if possible. "
    )

# Append tools - NO location tools, those are handled automatically
    tools.append(kb_tool)
    tools.append(search_tool)

#define parser
    output_parser = StrOutputParser()

    resource_format = "Name: , Street Address: , Offered Services: , Average Cost: ,  Phone Number: , Website Link: "
    
# Simplified prompt - location is handled automatically by the system
    system_prompt = fsystem_prompt = f"""You are HomeFinder, an empathetic AI assistant that helps people in the DFW area (Dallas, Fort Worth, Arlington, Plano, Irving, Frisco, Garland, McKinney, Denton, Richardson, Grapevine) experiencing homelessness find resources. If the user's request is the word Emergency and nothing else, enquire about their situation 

LANGUAGE:
- Recognize the user's language (default to English if unclear)
- Translate all responses and tool outputs to the user's language
- any time you use a tool such as the knowledge base or internet, tell the tool to 'generate the answer in [INSERT_USER_LANGUAGE]'
- 

CONVERSATION STYLE:
- Be warm, understanding, and helpful - don't sound robotic
- Speak empathetically about their situation
- When the user wants resources quickly, help them efficiently
- Ask follow-up questions to refine searches if needed
- If the user isn't willing to share any details about their situation, DO NOT KEEP ASKING THEM

SEARCHING FOR RESOURCES:
- Use the knowledge base FIRST for homeless resources
- Use internet search for additional/current information
- Focus on: shelters, food, healthcare, essential services
- Ensure that the user provided parameters such as location adequately MATCH the resources in the knowledge base, don't just blatantly copy info from it
- If you can't find relevant information, use the internet (using the TavilySearch tool) for current information
- ALL LINKS THAT YOU PROVIDE MUST BE TAKEN FROM THE INTERNET AND MUST WORK
- The resources returned must be as close as possible in either proximity and/or need to the user provided location/scenario.
- Be warm, understanding, and helpful. Take the user's language into concern as well, and if possible, find shelters that support the language the user is speaking in (you can search the internet for this as well)
- Ask follow-up questions to further refine your searches (as well as after making and returning searches), using the internet or knowledge base (ie: location, more info about situation etc) to make it more of a personal experience


OUTPUT FORMAT:
- Present resources clearly with: Name, Address, Services, Phone, Website
- Use this format when available: {resource_format}

PRIVACY:
- If user provides PII, kindly ask them not to include it
- Redact any PII received (show as multiple *'s)

LOCATION HANDLING:
- Location searches are handled AUTOMATICALLY by the system
- If the user asks for something "near me", the system will get their GPS automatically
- If the user provides an address, the system will geocode it automatically
- You will receive search results directly - just present them nicely to the user
- If you receive a message saying "need location", ask the user for their general area
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
            "Extract and return ONLY the final user-facing answer, so remove all thinking, internal thoughts, processing, and debug info. Don't include any of your thinking either like \"here is the final answer\". Omit any characters (whether it's empty newline characters etc) that make the response less clear or messy to the user. Return it in properly formatted markdown (NO MARKDOWN BOX WITH PLAIN_TEXT) that can render neatly in a Chainlit frontend (similar to chatgpt). Generate the final answer in the language that is in the 'question': 'QUESTION' field of the Agent response. For example, if the language that the question is in is Spanish, generate the answer you return in Spanish, which includes all resource descriptions and pretty much the entire text you get into Spanish (other than links). Make sure the output is in a clearly formatted text, not markdown or anything else."
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
            max_iterations=8,  # Increased to allow multiple tool calls (location + search)
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


        
# Multi-language "near me" patterns for location query detection
# Priority: English, Spanish, Chinese, Arabic
NEAR_ME_PATTERNS = [
    # English
    'near me', 'nearby', 'closest', 'close to me', 'around me', 'in my area',
    'near my location', 'close by', 'nearest',
    # Spanish
    'cerca de mí', 'cerca de mi', 'cercano', 'cercana', 'cerca de aquí',
    'cerca de aqui', 'en mi área', 'en mi area', 'próximo', 'proximo',
    # Chinese (Simplified)
    '附近', '靠近我', '离我近', '我附近', '周围',
    # Chinese (Traditional)
    '靠近我', '離我近',
    # Arabic
    'بالقرب مني', 'قريب مني', 'بجواري', 'حولي', 'في منطقتي',
]

# Patterns that indicate "near [specific address]"
NEAR_ADDRESS_PATTERNS = [
    # English
    r'near\s+(?!me|my|here)(.+?)(?:\?|$|\.|\s+that|\s+which)',
    # Spanish  
    r'cerca\s+de\s+(?!mí|mi|aquí|aqui)(.+?)(?:\?|$|\.)',
    # Chinese
    r'(?:在|靠近)\s*(.+?)\s*(?:附近|周围)',
    # Arabic
    r'(?:بالقرب من|قريب من)\s+(.+?)(?:\?|$|\.)',
]

# Common prefixes to strip when extracting search term
SEARCH_PREFIXES = [
    # English
    'find me a', 'find me', 'find a', 'find', 'search for a', 'search for',
    'look for a', 'look for', 'where is a', 'where is', 'where are',
    'show me a', 'show me', 'i need a', 'i need', 'get me a', 'get me',
    'looking for a', 'looking for',
    # Spanish
    'encuentra', 'encontrar', 'busca', 'buscar', 'dónde está', 'donde esta',
    'dónde hay', 'donde hay', 'necesito', 'muéstrame', 'muestrame',
    # Chinese
    '找', '搜索', '查找', '我要找', '我想找', '帮我找',
    # Arabic
    'أجد', 'ابحث عن', 'أين', 'أريد', 'أحتاج',
]


def detect_location_query(text: str, model=None) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Detect if query needs location using keyword matching.
    Supports English, Spanish, Chinese, Arabic.
    Returns: (is_location_query, search_query, user_address)
    
    Note: model parameter kept for backwards compatibility but not used.
    """
    text_lower = text.lower()
    
    # Check for "near me" type patterns (no specific address)
    is_near_me = any(pattern in text_lower for pattern in NEAR_ME_PATTERNS)
    
    # Check for "near [address]" patterns
    user_address = None
    if not is_near_me:
        for pattern in NEAR_ADDRESS_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                potential_address = match.group(1).strip()
                if potential_address and len(potential_address) > 2:
                    user_address = potential_address
                    break
    
    # If neither pattern matched, not a location query
    if not is_near_me and not user_address:
        return (False, None, None)
    
    # Extract search term by removing prefixes and location phrases
    search_term = text_lower
    
    # Remove common prefixes
    for prefix in SEARCH_PREFIXES:
        if search_term.startswith(prefix):
            search_term = search_term[len(prefix):].strip()
            break
    
    # Remove "near me" type suffixes
    for pattern in NEAR_ME_PATTERNS:
        if pattern in search_term:
            search_term = search_term.replace(pattern, '').strip()
    
    # Remove "near [address]" if present
    if user_address:
        for pattern in NEAR_ADDRESS_PATTERNS:
            search_term = re.sub(pattern, '', search_term, flags=re.IGNORECASE).strip()
    
    # Clean up punctuation and extra spaces
    search_term = re.sub(r'[?!.,]+$', '', search_term).strip()
    search_term = re.sub(r'\s+', ' ', search_term).strip()
    
    # If search term is empty or too short, set to None
    if not search_term or len(search_term) < 2:
        search_term = None
    
    print(f"DEBUG: Location query detected - near_me={is_near_me}, search='{search_term}', address={user_address}")
    return (True, search_term, user_address)


@cl.on_message
async def main(message: cl.Message):
    # Retrieve agent and cleaning chain
    agent_with_history = cl.user_session.get("agent_with_history")
    cleaning_chain = cl.user_session.get("cleaning_layer")
    session_id = cl.user_session.get("id")
    
    # Grab user session id
    config = {"configurable": {"session_id": session_id}}
    
    try:
        print(f"DEBUG: User message: {message.content}")
        if message.content == "Emergency":
            await cl.Message("Emergency Number List: \n911\n Crisis Hotline: 988 \n Homeless Hotline: (555) 211-HELP \nDomestic Violence Hotline: (555) 799-SAFE \n Disaster Distress Helpline 1-800-985-5990 \n National Maternal Mental Health Hotline 1-833-TLC-MAMA (1-833-852-6262) \n Poison Help Hotline 1-800-222-1222 \nSubstance Abuse and Mental Health Services Administration’s National Helpline 1-800-662-HELP (1-800-622-4357) ").send()
            
        #get the PII removed text
        
        # Get the PII removed text
        pii_removed_message = remove_PII(message.content)
        
        #print(f"DEBUG: Cleaned response: {cleaned_response}")
        
        # Check if we're waiting for an address (GPS failed, user providing location)
        if is_waiting_for_address(session_id):
            print(f"DEBUG: Waiting for address - treating message as location")
            pending_query = get_pending_query(session_id)
            
            # Try to geocode the user's message as an address
            geocode_result = geocode_and_store(session_id, pii_removed_message)
            
            if geocode_result:
                lat, lng = geocode_result
                print(f"DEBUG: Geocoded address to ({lat}, {lng})")
                
                # Now search with the pending query
                search_term = pending_query or "resources"
                print(f"DEBUG: Searching for '{search_term}' at ({lat}, {lng})")
                search_result = search_resources(session_id, search_term)
                
                # Clear pending query
                set_pending_query(session_id, None)
                
                if search_result["status"] == "success":
                    formatted = format_results_for_user(search_result)
                    enhanced_question = f"""The user asked for: "{pending_query}"
                        Their location: {pii_removed_message}

                        I found these results near them:

                        {formatted}

                        Please present these results warmly and helpfully."""
                    
                    response = await agent_with_history.ainvoke({"question": enhanced_question}, config=config)
                    cleaned_response = cleaning_chain.invoke({"agent_response": str(response)})
                    await cl.Message(content=cleaned_response).send()
                else:
                    await cl.Message(content=search_result["message"]).send()
                return
            else:
                # Geocoding failed - ask for a clearer address
                await cl.Message(content=f"I couldn't find that location. Could you try a more specific address? For example: 'Main Street, Dallas' or '75201'.").send()
                return
        
        # Detect location intent using keyword matching (supports EN/ES/ZH/AR)
        is_location_query, search_query, user_address = detect_location_query(pii_removed_message)
        
        if is_location_query:
            print(f"DEBUG: Location query detected - query: '{search_query}', address: {user_address}")
            
            # Ensure we have a location
            location_result = await ensure_location(session_id, user_address)
            
            if location_result["status"] == "need_address":
                # Store the pending query so we can use it when user provides address
                set_pending_query(session_id, search_query)
                await cl.Message(content=location_result["message"]).send()
                return
            
            if location_result["status"] == "error":
                await cl.Message(content=location_result["message"]).send()
                return
            
            # We have a location - search using natural language query
            search_term = search_query or "resources"  # Default if no query extracted
            print(f"DEBUG: Searching for '{search_term}' at ({location_result['lat']}, {location_result['lng']})")
            search_result = search_resources(session_id, search_term)
            
            if search_result["status"] == "success":
                # Format and send results
                formatted = format_results_for_user(search_result)
                
                # Let the agent add context/empathy to the results
                enhanced_question = f"""The user asked: "{pii_removed_message}"

                    I found these results near them:

                    {formatted}

                    Please present these results to the user in a warm, helpful way. Add any relevant context about the resources if you have knowledge about them."""
                
                response = await agent_with_history.ainvoke({"question": enhanced_question}, config=config)
                cleaned_response = cleaning_chain.invoke({"agent_response": str(response)})
                await cl.Message(content=cleaned_response).send()
            else:
                # No results - let the agent help
                await cl.Message(content=search_result["message"]).send()
        else:
            # Not a location query - use the agent normally
            response = await agent_with_history.ainvoke({"question": str(pii_removed_message)}, config=config)
            print(f"DEBUG: Agent response: {response}")
            
            cleaned_response = cleaning_chain.invoke({"agent_response": str(response)})
            print(f"DEBUG: Cleaned response: {cleaned_response}")
            global current_llm_message
            current_llm_message = cleaned_response
            await cl.Message(content=cleaned_response).send()
        
    except Exception as e:
        print(f"DEBUG: Error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
        await cl.Message(content=f"I'm sorry, I encountered an error. Please try again or rephrase your question.").send()


# Implement function to delete history after session ends (user refreshes or clicks off)
@cl.on_chat_end
def deleteHistory():
    user_id = cl.user_session.get('id')
    region_name = cl.user_session.get('region_name')
    
    # Clear session location and state
    if user_id:
        clear_session_location(str(user_id))
        reset_location_state(str(user_id))
    
    # Clear DynamoDB history
    table = dynamodb.Table('SessionTable')
    response = table.delete_item(Key={'SessionId': str(user_id)})
