import os
import glob
import datetime
from types import List, Dict
from pypdf import PdfReader
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv


def save_flow_log(flow_updates:str,filename:str) -> Dict:
    '''writes and saves exection updates to a log file'''
    path='./logs'
    if not (filename in os.listdir(path)):
        with open(filename,'w+') as f:
            f.write('Log of the tool calls....Date:{}'.format(datetime.datetime.now()))

    with open(filename,'a') as f:
        f.write(flow_updates)

    return {'log_status':'saved'}

def read_doc(filename:str) -> Dict:
    '''reads the given filename and returns its content as a string object'''
    path='./policy'
    if filename in os.listdir(path):
        reader = PdfReader(path+filename+'.pdf')
        page = reader.pages
        return {'text':page}
    else:
        return {'text':''}
    
def mcp_db_tool():
    load_dotenv()
    DATABASE = os.getenv("DATABASE_NAME")
    conf={
    "mcpServers": {
        "MCP SQLite Server": {
            "command": "npx",
            "args": [
                "-y",
                "mcp-sqlite",
                "<path-to-your-sqlite-database.db>" #this should be changed later.
            ]
        }
    }
}
    return conf
    


