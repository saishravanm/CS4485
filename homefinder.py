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

region_name = "us-east-1"

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
        if entity['Type'] != 'ADDRESS' or entity['Type'] != "PHONE":
            for i in range(entity['BeginOffset'],entity['EndOffset']):
                redacted_text[i] = '*'
    redacted_text = "".join(redacted_text)
    return redacted_text

# SerpAPI function removed - now using TavilySearch

@cl.on_chat_start
async def init():
    
    #generate user session id for the session
    session_id = uuid.uuid4()
    cl.user_session.set("id",session_id)
    session_id = cl.user_session.get("id")
    
    #define region
    cl.user_session.set("region_name",region_name)
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
        model_id="amazon.nova-micro-v1:0",
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

#define parser
    output_parser = StrOutputParser()

    resource_format = "Name: , Street Address: , Offered Services: , Average Cost: ,  Phone Number: , Website Link: "
    
#define agentic prompt - simplified and more conversational
    agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", f"You are HomeFinder, an empathetic AI assistant that helps people in the DFW area experiencing homelessness find resources. If the user's request is the word Emergency and nothing else, enquire about their situation. Recognize the user's language that they're speaking in (if it's hard to tell what language they're speaking in, the default language is English), and translate all your responses (and responses coming from any tools) during the conversation in the user speaking language. Before searching for resources, make sure you speak to the user empathetically about their situation, and when it seems clear that they just want the resources and not a detailed conversation about their needs, search for resources with the information you have. When searching for resources, send the search request in the language that the user is speaking in, use the knowledge base FIRST (ensure that the user provided parameters such as location adequately MATCH the resources in the knowledge base, don't just blatantly copy info from it), and if there's still any information still missing you can use the internet for current information. The resources returned must be as close as possible in either proximity and/or need to the user provided location/scenario. Be warm, understanding, and helpful. Ask follow-up questions to further refine your searches before using the internet or knowledge base (ie: location, more info about situation etc) to make it more of a personal experience. Focus on practical help like shelters, food, healthcare, and other essential services. Do a sentiment analysis on each user response and base your responses/resources on how the user seems to be feeling. Don't sound robotic, sound conversational. YOU MUST USE {resource_format} as your format for searching and showing the user the information you found.If the user has seemed to provide any personal identifiable information, kindly request them to not include anything as such (pii information you recieve should be donated by multiple *'s)"),                MessagesPlaceholder(variable_name="history"),
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
        if message.content == "Emergency":
            await cl.Message("Emergency Number List: \n911\n Crisis Hotline: 988 \n Homeless Hotline: (555) 211-HELP \nDomestic Violence Hotline: (555) 799-SAFE \n Disaster Distress Helpline 1-800-985-5990 \n National Maternal Mental Health Hotline 1-833-TLC-MAMA (1-833-852-6262) \n Poison Help Hotline 1-800-222-1222 \nSubstance Abuse and Mental Health Services Administration’s National Helpline 1-800-662-HELP (1-800-622-4357) ").send()
            
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
