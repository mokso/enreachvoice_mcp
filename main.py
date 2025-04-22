import enreachvoice
import logging
import json
import os
from dataclasses import dataclass, asdict
from mcp.server.fastmcp import FastMCP


# EnreachVoice API credentials from env variables
APIUSER = os.getenv("ENREACHVOICE_APIUSER")
APISECRET = os.getenv("ENREACHVOICE_APISECRET")

mcp = FastMCP("EnreachVoice Queues")

client = enreachvoice.Client(username=APIUSER, secretkey=APISECRET)


logging.basicConfig(
    level=logging.DEBUG
)

# https://doc.enreachvoice.com/beneapi/#queue-information
queuetypes = {
    1: "UserDirect",
    2: "PersonalWork",
    4: "ServiceQueue",
    5: "IvrQueue",
    6: "ShortNumber",
    7: "Technical"
}
# https://doc.enreachvoice.com/beneapi/#queueopenstatus
queueopenstatus = {
    0: "Dynamic",
    1: "Closed",
    2: "Dynamic",
    3: "Closed",
    4: "Dynamic",
    5: "Open",
    6: "Dynamic"
}

# dataclass to combine relevatn queue information
@dataclass
class Queue:
    id: str
    name: str
    type: str
    description: str = None # descrption comes form direcotry entry
    number: str = None # first number of the queue
    openstatus: str = None
    maxwaittime: int = None
    queuelength: int = None
    ongoingcalls: int = None
    agentsonwrapup: int = None
    freeagents: int = None
    servingagents: int = None

    def to_json(self) -> str:
        return json.dumps(asdict(self))

@dataclass
class DirectoryEntry:
    id: str
    name: str
    email: str
    worknumber: str
    mobilenumber: str
    othernumber: str
    description: str
    company: str
    subcompany: str
    location: str
    departmetn: str

    def to_json(self) -> str:
        return json.dumps(asdict(self))

def get_queue_directoryinfo():
    # Firest get all directories
    directories = client.invoke_api(
        path="/directory", 
        method="GET"
    )

    # get directory named "Default"
    directory_id = None
    for d in directories:
        if d["Name"] == "Default":
            directory_id = d["ID"]
            break
    if directory_id is None:
        logging.error("No Default directory found")
        return None

    # get service queue directory entries from the default directory
    directory_entries = client.invoke_api(
        path=f"/directory/{directory_id}", 
        method="GET",
        params={"EntryTypes": "2", "MaxCount": "1000"}
    )

    return directory_entries["Entries"]
                                 
@mcp.resource("data://queues")
@mcp.tool("get_queues")
def get_queues():
    """
    Get all queues from the EnreachVoice system. Use this to retrieve information of all contact center queues in the Enreach Voice system.
    This function uses the EnreachVoice API to get the queues and their status.
    It returns a list of Queue objects, which contain the following information:
    - id: The ID of the queue
    - name: The name of the queue
    - type: The type of the queue (e.g. ServiceQueue, IvrQueue, etc.)
    - description: The description of the queue
    - number: The first number of the queue
    - openstatus: The open status of the queue (e.g. Open, Closed, etc.)
    - maxwaittime: The maximum wait time for the queue
    - queuelength: The length of the queue
    - ongoingcalls: The number of ongoing calls in the queue
    - agentsonwrapup: The number of agents on wrap up in the queue
    - freeagents: The number of free agents in the queue
    - servingagents: The number of serving agents in the queue
    Returns:
        list: List of Queue objects
    """
    try:
        # get queues
        queues = client.invoke_api(path="/queues", method="GET")

        # get queue directory info
        directory_entries = get_queue_directoryinfo()

        # convert to dataclass
        queuelist = []
        for q in queues:
            if q["Status"] is None:
                continue

            status = q["Status"]
            queue = Queue(
                id=q["Id"],
                name=q["Name"],
                # select the first number from the list
                number=q["Numbers"][0] if q["Numbers"] else None,
                type=queuetypes.get(q["TypeId"], "Unknown"),
                openstatus=queueopenstatus.get(status["OpenStatus"], "Unknown"),
                maxwaittime=status["MaxWaitTime"],
                queuelength=status["QueueLength"],
                ongoingcalls=status["OngoingCalls"],
                agentsonwrapup=status["AgentsOnWrapUp"],
                freeagents=status["FreeAgents"],
                servingagents=status["ServingAgents"]
            )
            # get directory entry
            for entry in directory_entries:
                if entry["QueueId"] == q["Id"]:
                    queue.description = entry["Description"]
                    break

            queuelist.append(queue)

        return queuelist
    except Exception as e:
        logging.error(f"Error getting queues: {e}")
        return None


def get_directoryentry_by_number(number:str):
    directories = client.invoke_api(
        path="/directory", 
        method="GET"
    )

    entries = []
    for d in directories:
        directory_id = d["ID"]
        result = client.invoke_api(
            path=f"/directory/{directory_id}", 
            method="GET",
            params={"Number": number, "MaxCount": "1000"}
        )
        if result["Entries"]:
            entries += result["Entries"]
            
    print(f"Found {len(entries)} entries for number {number}")
    print(json.dumps(entries, indent=4))
    # convert to dataclass
    directory_entries = []
    for entry in entries:
        directory_entry = DirectoryEntry(
            id=entry["Id"],
            name=entry["FirstName"] + " " + entry["LastName"] if entry["FirstName"] else entry["LastName"],
            email=entry["Email"],
            worknumber=entry["WorkNumber"],
            mobilenumber=entry["MobileNumber"],
            othernumber=entry["OtherNumber"],
            description=entry["Description"],
            company=entry["Company"],
            subcompany=entry["Subcompany"],
            location=entry["Location"],
            departmetn=entry["Department"]
        )
        directory_entries.append(directory_entry)
    return directory_entries


def main():
    mcp.run()

if __name__ == "__main__":
    main()

    