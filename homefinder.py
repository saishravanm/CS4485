import chainlit as cl
import uuid
import boto3
from langchain_aws import ChatBedrockConverse
import serpapi
import os
from langchain_core.tools import Tool
from langchain_core.output_parsers import StrOutputParser
from langchain_tavily import TavilySearch
from langchain_classic.memory import ConversationBufferMemory
from langchain_classic.agents import initialize_agent, AgentType, create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
from dotenv import load_dotenv

def get_session_history(session_id):
    return DynamoDBChatMessageHistory(table_name="SessionTable",session_id=session_id)

def search_web(query: str) -> str:
    """
    This function searches the web.
    """
    params ={
        "q":query,
        "api_key":os.getenv("SERPAPI_KEY")
    }
    results = serpapi.search(params).as_dict()
    top_result = results['organic_results'][0]['snippet']
    return top_result

@cl.on_chat_start
def init():
    #generate user session id for the session
    session_id = uuid.uuid4()
    cl.user_session.set("id",session_id)
    session_id = cl.user_session.get("id")
    
    #define region
    region_name = "us-east-1"

#create dynamodb instance
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    client = boto3.client(
        'sts',
        aws_access_key_id= os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        region_name=region_name
    )

# Create the Bedrock model instance
    model = ChatBedrockConverse(
        model_id="amazon.nova-micro-v1:0",
        region_name=region_name,
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    )
    
    tools = []
    history = DynamoDBChatMessageHistory(table_name="SessionTable", session_id=session_id)

##define tools
    search_tool = TavilySearch(
            max_results=5,
            topic="general",
    )


    internet_tool = Tool(
            name="internet",
            func=search_web,
            description="Use this to search for current information on the internet"
    )

#append created tools to list
    tools.append(internet_tool)

#define parser and memory
    output_parser = StrOutputParser()
    memory = ConversationBufferMemory(chat_memory=history,memory_key="history",return_messages=True)

#define agentic prompt
    agent_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a very empathetic chatbot that has access to the internet and is running on a device of some kind (usually a phone) (name: \"HomeFinder\") which helps individuals who are homeless find the resources they need. Specifically, findShelter, findID, findMentalHealth, findPhysicalHealth, findStorage. You have a tool that lets you search the internet. You must answer ALL of the user's queries as empathetically as possible. If additional information is necessary to more precisely help the user find their resource, ask for it, such as their current location, current living status, how many people their living with etc. When the user starts the conversation without directly asking for a resource, start with an intro to what this chatbot can do, then do mental health check(the user can opt out of this if they want) and go from there. The goal is to be as conversational as possible."),
                MessagesPlaceholder(variable_name="history"),
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

#define agent executor
    agent_executor = AgentExecutor(
            agent=internet_agent,
            tools=tools,
            verbose=False,
            memory=memory,
            return_intermediate_steps=False,
            output_parser=StrOutputParser()
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
    
    #get agent response (JSON)
    response = agent_with_history.invoke({"question": str(message.content)}, config=config)
    
    #send agent response to be cleaned into user text
    cleaned_response = cleaning_chain.invoke({"agent_response":str(response)})
    await cl.Message(content=cleaned_response).send()

'''
implement function to delete history after session ends (user refreshes or clicks off)
@cl.on_chat_end
def deleteHistory():
'''

    