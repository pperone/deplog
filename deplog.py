import os
import time
import re

from slackclient import SlackClient

from sqlalchemy import create_engine  
from sqlalchemy import Column, String, Integer, ARRAY
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker


# Database creation and setup
engine = create_engine(os.environ['DEPLOG_DB_URL'])
base = declarative_base()

class Organization(base):  
    __tablename__ = 'organizations'

    channel = Column(String, primary_key=True)
    staging = Column(Integer)
    feature = Column(String)
    teammobile = Column(String)

Session = sessionmaker(engine)  
session = Session()

base.metadata.create_all(engine)


# Slack setup
slack_client = SlackClient(os.environ.get('DEPLOG_TOKEN'))
deplog_id = None


# Constants
RTM_READ_DELAY = 1
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


# Creates an organization in the database
def create_org(channel):
    org = Organization(channel=channel, feature='', staging='')
    session.add(Organization(channel=channel, feature='', staging=0))
    session.commit()
    return org


# Retrieves the organization from the database from the channel name
def get_org(channel):
    org = session.query(Organization).filter_by(channel=channel).first()
    return org


# Create organization if it doesn't exist, retrieve it if it does
def evaluate_org(channel):
    org = get_org(channel)

    if org:
        channel = org.channel
        staging = org.staging
        feature = org.feature
        teammobile = org.teammobile
    else:
        org = create_org(channel)
        channel = org.channel
        staging = org.staging
        feature = org.feature
        teammobile = org.teammobile
    
    return org, channel, staging, feature, teammobile


# Processes the message
def parse_bot_commands(slack_events):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            print(event["text"])
            user_id, message = parse_direct_mention(event["text"])
            org, channel, staging, feature, teammobile = evaluate_org(event["channel"])
            handle_event(channel, org, event["text"])

    return None, None


# Extract direct mention to bot
def parse_direct_mention(message_text):
    matches = re.search(MENTION_REGEX, message_text)

    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


# All the possible commands from user input
def handle_event(channel, org, message):
    response = None
    env_starter = '*Environment*'
    branch_starter = '*Branch*'

    if message.startswith('New version deployed'):
        environment = message[message.index(env_starter) + len(env_starter)].split()[0]
        branch = message[message.index(branch_starter) + len(branch_starter)].split()[0]

        if environment == 'staging':
          org.staging = branch
        
        response = "*Branches currently deployed to each environment:* \n\n :green_apple: *staging  |*  Current branch: *" + org.staging + "* \n :apple: *feature  |*  Current branch: *" + org.feature + "* \n :apple: *teammobile  |*  Current branch: *" + org.teammobile + "*"

        slack_client.api_call(
            "chat.postMessage",
            channel = channel,
            text = response,
            as_user = True
        )

        session.commit()


if __name__ == "__main__":
    if slack_client.rtm_connect(with_team_state=False):
        print("Deplog connected")
        deplog_id = slack_client.api_call("auth.test")["user_id"]

        while True:
            parse_bot_commands(slack_client.rtm_read())
            time.sleep(RTM_READ_DELAY)
    else:
        print("Connection failed. Exception traceback printed above.")
