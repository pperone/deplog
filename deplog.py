import os
import time
import re

from slackclient import SlackClient

from datetime import datetime, timedelta

from sqlalchemy import create_engine  
from sqlalchemy import Column, String, Integer, ARRAY
from sqlalchemy.ext.declarative import declarative_base  
from sqlalchemy.orm import sessionmaker


# Database creation and setup
engine = create_engine(os.environ['DATABASE_URL'])
base = declarative_base()
debug_channel = 'C01224QRGSV'
debugging = False

class Organization(base):  
    __tablename__ = 'organizations'

    channel = Column(String, primary_key=True)
    staging = Column(String)
    s_deployer = Column(String)
    s_deployed = Column(String)
    feature = Column(String)
    f_deployer = Column(String)
    f_deployed = Column(String)
    teammobile = Column(String)
    t_deployer = Column(String)
    t_deployed = Column(String)

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
    # ev = {"type": "message", "subtype": "bot_message", "text": "", "suppress_notification": False, "username": "Slackistrano", "icons": {"image_48": "https://s3-us-west-2.amazonaws.com/slack-files2/bot_icons/2017-05-24/187498878213_48.png"}, "bot_id": "B0E14A2BA", "team": "T02FPTL8D", "bot_profile": {"id": "B0E14A2BA", "deleted": False, "name": "incoming-webhook", "updated": 1446819626, "app_id": "A0F7XDUAZ", "icons": {"image_36": "https://a.slack-edge.com/80588/img/services/outgoing-webhook_36.png", "image_48": "https://a.slack-edge.com/80588/img/services/outgoing-webhook_48.png", "image_72": "https://a.slack-edge.com/80588/img/services/outgoing-webhook_72.png"}, "team_id": "T02FPTL8D"}, "attachments": [{"fallback": "Pablo Ulguin has finished deploying branch master of backlotcars to production", "title": "New version deployed :boom::bangbang:", "id": 1, "color": "2eb886", "fields": [{"title": "Environment", "value": "load-test", "short": True}, {"title": "Branch", "value": "master", "short": True}, {"title": "Deployer", "value": "Pablo Ulguin", "short": True}, {"title": "Revision", "value": "53b853d", "short": True}, {"title": "Time to deploy", "value": "04:37", "short": True}, {"title": "www", "value": "https://backlotcars.com", "short": True}]}], "channel": "G0E437QDD", "event_ts": "1589220562.071000", "ts": "1589220562.071000"}
    org = get_org(CHANNEL)

    for event in slack_events:
        if 'channel' in event:
            if event["channel"] == CHANNEL: 
                if event["type"] == "message":
                    if "attachments" in event:
                        if "title" in event["attachments"][0]:
                            handle_event(org, event)
                
                # handle_event(org, ev)

                # slack_client.api_call(
                #     "chat.postMessage",
                #     channel = debug_channel,
                #     text = event,
                #     as_user = True
                # )
                # session.commit()
                    
    return None, None


# All the possible commands from user input
def handle_event(org, event):
    response = None
    production = False
    t = (datetime.now() - timedelta(hours = 3)).strftime("%b %d %Y, %H:%M UY")

    title = event["attachments"][0]["title"]
    environment = event["attachments"][0]["fields"][0]["value"]
    branch = event["attachments"][0]["fields"][1]["value"]
    deployer = event["attachments"][0]["fields"][2]["value"]

    s_icon = ':apple:'
    f_icon = ':apple:'
    t_icon = ':apple:'

    if title.startswith('New version deployed'):
        if environment == 'staging':
            org.staging = branch
            org.s_deployer = deployer
            org.s_deployed = t
        elif environment == 'feature':
            org.feature = branch
            org.f_deployer = deployer
            org.f_deployed = t
        elif environment == 'teammobile':
            org.teammobile = branch
            org.t_deployer = deployer
            org.t_deployed = t
        elif environment == 'production':
            production = True

        if org.staging == 'develop' or org.staging.startswith('master_pre_production'):
            s_icon = ':green_apple:'

        if org.feature == 'develop' or org.feature.startswith('master_pre_production'):
            f_icon = ':green_apple:'

        if org.teammobile == 'develop' or org.teammobile.startswith('master_pre_production'):
            t_icon = ':green_apple:'

        response = s_icon + " *staging    |*    Current branch: *" + org.staging + "    |*    Deployed by *" + org.s_deployer + "* on " + org.s_deployed + " \n\n"\
                   + f_icon + " *feature    |*    Current branch: *" + org.feature + "    |*    Deployed by *" + org.f_deployer + "* on " + org.f_deployed + " \n\n"\
                   + t_icon + " *teammobile    |*    Current branch: *" + org.teammobile + "    |*    Deployed by *" + org.t_deployer + "* on " + org.t_deployed

        time.sleep(120)

        if not production:
            if debugging:
                slack_client.api_call(
                    "chat.postMessage",
                    channel = debug_channel,
                    text = response,
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
