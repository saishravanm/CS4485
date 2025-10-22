import chainlit as cl
import boto3
from langchain_aws import ChatBedrockConverse
from langchain_community.chat_message_histories import DynamoDBChatMessageHistory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.tools import Tool
from langchain.agents import create_agent
import uuid
import serpapi
from langchain_aws.agents.base import BedrockAgentsRunnable
from langchain.tools import BaseTool


def search_web(query: str) -> str:
    """
    This function searches the web.
    """
    params ={
        "q":query,
        "api_key":"f31233afdea256c2f97c5063768c34bf297cdbf58976f4cefe40330a5d27bc1d"
    }
    results = serpapi.search(params).get_dict()
    top_result = results['organic_results'][0]['snippet']
    return top_result


@cl.on_chat_start
def init():
    cl.user_session.set("id",str(uuid.uuid4))
    
    region_name = "us-east-1"
    dynamodb = boto3.resource("dynamodb", region_name=region_name)
    client = boto3.client(
        'sts',
        aws_access_key_id='AKIA3PZEYYKFHBZD2YUP',
        aws_secret_access_key='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',
        region_name=region_name
    )

# Create the Bedrock model instance
    model = ChatBedrockConverse(
        model_id="amazon.nova-micro-v1:0",
        region_name=region_name,
        aws_access_key_id="AKIA3PZEYYKFHBZD2YUP",
        aws_secret_access_key="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"
    )
    output_parser = StrOutputParser()
    internet_tool = Tool(
        name="internet",
        func=search_web,
        description="Use this to search for current information on the internet"
    )
    model.bind_tools([internet_tool])
# Initialize the DynamoDB message history
    history = DynamoDBChatMessageHistory(table_name="SessionTable", session_id=cl.user_session.get("id"))

# Define the chat prompt template
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are a chatbot which helps individuals who are homeless find the resources they need. "
                    "Specifically, findShelter, findID, findMentalHealth, findPhysicalHealth, findStorage. "
                    "Try to answer the user's questions as empathetically as possible. You have a tool that lets you search the internet"),
            MessagesPlaceholder(variable_name="history"),
            ("human", "{question}"),
        ]
    )

# Define the output parser
    
    #emergency_agent = create_react_agent(model,[search_web],prompt="Use this to search for current information on the internet")
    internet_agent = create_agent(
        model=model,
        tools=[internet_tool],
        debug=True
    )
# Create the complete conversation chain
    chain = prompt | model | output_parser

# Wrap the chain with message history functionality
    chain_with_history = RunnableWithMessageHistory(
        chain,
        lambda session_id: DynamoDBChatMessageHistory(
            table_name="SessionTable", session_id=session_id
        ),
        input_messages_key="question",
        history_messages_key="history",
    )
    
    cl.user_session.set("chain_with_history",chain_with_history)
    
    
    
    

@cl.on_message
async def main(message: cl.Message):
    chain_with_history = cl.user_session.get("chain_with_history")
    config = {"configurable": {"session_id": cl.user_session.get("id")}}
    response = chain_with_history.invoke({"question": str(message.content)}, config=config)
    print(str(message.content))
    await cl.Message(content=response).send()