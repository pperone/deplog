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

class Organization(base):  
    __tablename__ = 'organizations'

    channel = Column(String, primary_key=True)
    staging = Column(Integer)
    feature = Column(String)

Session = sessionmaker(engine)  
session = Session()

base.metadata.create_all(engine)


# Slack setup
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
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
    else:
        org = create_org(channel)
        channel = org.channel
        staging = org.staging
        feature = org.feature
    
    return org, channel, staging, feature


# Processes the message
def parse_bot_commands(slack_events):
    for event in slack_events:
        if event["type"] == "message" and not "subtype" in event:
            user_id, message = parse_direct_mention(event["text"])
            org, channel, staging, feature = evaluate_org(event["channel"])

            if "attachments" in event:
                if event["attachments"][0]["author_subname"] == 'BugBot':
                    handle_event(channel)
            elif user_id == deplog_id:
                handle_event(channel)

    return None, None


# Extract direct mention to bot
def parse_direct_mention(message_text):
    matches = re.search(MENTION_REGEX, message_text)

    return (matches.group(1), matches.group(2).strip()) if matches else (None, None)


# All the possible commands from user input
def handle_command(command, team):
    response = None
    users = team.users.split()

    if command.startswith('assign'):
        if len(users) > 0:
            response = users[team.current]
            if team.current == len(users) - 1:
                team.current = 0
            else:
                team.current += 1
        else:
            response = "There is no one assigned for taking tasks yet. Use the *add* command followed by a user mention."

    if command.startswith('list'):
        if len(users) > 0:
            response = users
        else:
            response = "There is no one assigned for taking tasks yet. Use the *add* command followed by a user mention."

    if command.startswith('increase'):
        if len(users) > team.current + 1:
            team.current += 1
            response = "Position in queue moved forward by one person"
        elif len(users) > 1:
            team.current = 0
            response = "Position in queue moved forward by one person"
        else:
            response = "Queue position can\'t be moved"
    
    if command.startswith('decrease'):
        if team.current > 0:
            team.current -= 1
            response = "Position in queue moved backward by one person"
        elif len(users) > 1:
            team.current = len(users) - 1
            response = "Position in queue moved backward by one person"
        else:
            response = "Queue position can\'t be moved"

    if command.startswith('current'):
        response = "Queue position is currently *{}*.".format(team.current)

    if command.startswith('add'):
        mention = command.split()[1]

        if mention:
            team.users += " " + mention
            response = "{} added to bug squashing squad.".format(mention)
        else:
            response = "Not a valid addition. Try tagging someone."

    if command.startswith('remove'):
        mention = command.split()[1]

        if mention in users:
            remove = " " + mention
            updated = team.users.replace(remove, '')
            team.users = updated
            response = "{} removed from bug squashing squad.".format(mention)
        else:
            response = "{} is not part of the bug squashing squad.".format(mention)

        if team.current >= len(users):
            team.current -= 1
    
    if command.startswith('last'):
        if len(users) > 0:
            response = users[team.current - 1]
        else:
            response = "There is no one assigned for taking tasks yet. Use the *add* command followed by a user mention."

    slack_client.api_call(
        "chat.postMessage",
        channel = team.channel,
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