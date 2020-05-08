import os
import time
import re

from slackclient import SlackClient

from sqlalchemy import create_engine  
from sqlalchemy import Column, String, Integer, ARRAY
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker


# Database creation and setup
engine = create_engine(os.environ['DATABASE_URL'])
base = declarative_base()
debug_channel = 'C01224QRGSV'
debugging = True

class Organization(base):  
    __tablename__ = 'organizations'

    channel = Column(String, primary_key=True)
    staging = Column(String)
    feature = Column(String)
    teammobile = Column(String)

Session = sessionmaker(engine)  
session = Session()

base.metadata.create_all(engine)


# Slack setup
slack_client = SlackClient(os.environ.get('DEPLOG_TOKEN'))
deplog_id = None


# Constants
CHANNEL = 'G0E437QDD'
RTM_READ_DELAY = 1
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"


# Retrieves the organization from the database from the channel name
def get_org(channel):
    org = session.query(Organization).filter_by(channel=channel).first()
    return org


# Processes the message
def parse_bot_commands(slack_events):
    org = get_org(CHANNEL)

    for event in slack_events:
        if 'channel' in event:
            if event["channel"] == CHANNEL: 
                if event["type"] == "message":
                    if "attachments" in event:
                        handle_event(org, event)

    return None, None


# All the possible commands from user input
def handle_event(org, event):
    response = None
    production = False
    title = event["attachments"][0]["title"]
    environment = event["attachments"][0]["fields"][0]["value"]
    branch = event["attachments"][0]["fields"][1]["value"]
    s_icon = ':apple:'
    f_icon = ':apple:'
    t_icon = ':apple:'

    if title.startswith('New version deployed'):
        if environment == 'staging':
            org.staging = branch
        elif environment == 'feature':
            org.feature = branch
        elif environment == 'teammobile':
            org.teammobile = branch
        elif environment == 'production':
            production = True

        if org.staging == 'develop':
            s_icon = ':green_apple:'

        if org.feature == 'develop':
            f_icon = ':green_apple:'

        if org.teammobile == 'develop':
            t_icon = ':green_apple:'

        response = "\n \n" + s_icon + " *staging  |*  Current branch: *" + org.staging + "* \n\n " + f_icon + " *feature  |*  Current branch: *" + org.feature + "* \n\n " + t_icon + " *teammobile  |*  Current branch: *" + org.teammobile + "*"

        if not production:
            if debugging:
                slack_client.api_call(
                    "chat.postMessage",
                    channel = CHANNEL,
                    text = response,
                    as_user = True
                )
                session.commit()

                slack_client.api_call(
                    "chat.postMessage",
                    channel = debug_channel,
                    text = event,
                    as_user = True
                )
                session.commit()
            else:
                slack_client.api_call(
                    "chat.postMessage",
                    channel = CHANNEL,
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
