from mcp.server.fastmcp import FastMCP
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import datetime
import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from dateutil import parser
from twilio.rest import Client
from pydantic import BaseModel, field_validator,ValidationError
from typing import List, Union
import requests
import pytz

from dotenv import load_dotenv

load_dotenv()
# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar.events']


# Initialize FastMCP server with the name "mytools"
mcp = FastMCP("assistant")

@mcp.tool()
def send_email( sender_password, recipient_email, subject, message):
    """
    It sends emails to the neede person. 
    
    Args:

        sender_password: Password of the email being used.

        recipient_email: To whom email will be sent to.

        subject: Subject of the email.
 
        message: What will be send in the email.

        recipient_email: The person to whom user wants to send the mail
    """
    sender_email=os.getenv('sender_email')
    try:
        # Create message container
        msg = MIMEMultipart()
        msg['From'] = sender_email
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Attach the message body
        msg.attach(MIMEText(message, 'plain'))

        # Connect to Gmail SMTP server
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()  # Secure the connection
        server.login(sender_email, sender_password)

        # Send the email
        server.send_message(msg)
        print("Email sent successfully.")

        # Close the connection
        server.quit()

    except Exception as e:
        print(f"Failed to send email: {e}")


class ScheduleMeetingInput(BaseModel):
    summary: str
    description: str
    start_time: str  # Let LLM send natural language
    duration_minutes: int
    attendees_emails: Union[str, List[str]]

    @field_validator("attendees_emails")
    @classmethod
    def parse_emails(cls, v):
        if isinstance(v, str):
            return [email.strip() for email in v.replace(" and ", ",").split(",")]
        return v

@mcp.tool()
def schedule_meeting_input_parser(input: dict):
    """
    Wrapper for schedule_meeting using manual schema parsing from dict.
    """
    try:
        parsed = ScheduleMeetingInput(**input)
        return schedule_meeting(
            summary=parsed.summary,
            description=parsed.description,
            start_time=parsed.start_time,
            duration_minutes=parsed.duration_minutes,
            attendees_emails=parsed.attendees_emails,
        )
    except ValidationError as e:
        return f"❌ Input validation failed: {e}"


def authenticate_google():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    # If there are no valid credentials, let user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(r'E:\Medico_Gpt\mcp_client\app\servers\credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

@mcp.tool()
def schedule_meeting(summary, description, start_time, duration_minutes, attendees_emails):
    """
    Schedules a Google Calendar event with Google Meet conferencing.

    This function authenticates the user via OAuth2, connects to the Google Calendar API,
    and creates a calendar event with the provided details, including a Google Meet link.
    An email invitation is automatically sent to all listed attendees.

    Args:
        summary (str): The title or subject of the meeting.
        description (str): Additional details or agenda for the meeting.
        start_time (datetime.datetime): The start time of the meeting.
        duration_minutes (int): Duration of the meeting in minutes.
        attendees_emails (List[str]): A list of email addresses to invite to the meeting.

    Returns:
        None. Prints confirmation and the generated Google Meet link to the console.

    Note:
        - Requires a valid `credentials.json` file for Google OAuth2 in the project directory.
        - Automatically stores a `token.pickle` file for session reuse.
        - The user's Gmail account must have Google Calendar enabled.
        - Time zone is set to 'Asia/Karachi' by default; modify as needed.
    """
    creds = authenticate_google()
    service = build('calendar', 'v3', credentials=creds)
    if isinstance(attendees_emails, str):
        attendees_emails = [email.strip() for email in attendees_emails.split(",")]
    if isinstance(start_time, str):
        try:
            # Parse the time and attach timezone only if naive
            start_time = parser.parse(start_time)
            if start_time.tzinfo is None or start_time.tzinfo.utcoffset(start_time) is None:
                start_time = start_time.replace(tzinfo=pytz.timezone("Asia/Karachi"))
            # Force conversion to avoid offset errors
            start_time = start_time.astimezone(pytz.UTC).astimezone(pytz.timezone("Asia/Karachi"))
        except Exception as e:
            error_msg = f"Failed to schedule meeting: {e}"
            print(error_msg)
            return error_msg

 

    try:
        duration_minutes = int(duration_minutes)
        end_time = start_time + datetime.timedelta(minutes=duration_minutes)

        event = {
            'summary': summary,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'Asia/Karachi',
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'Asia/Karachi',
            },
            'attendees': [{'email': email} for email in attendees_emails],

            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet-{datetime.datetime.now().timestamp()}",
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
        }

        created_event = service.events().insert(
            calendarId='primary',
            body=event,
            conferenceDataVersion=1,
            sendUpdates='all'
        ).execute()
        print(created_event['hangoutLink'])

    except Exception as e:
        return f"Failed to schedule meeting: {e}"

@mcp.tool()
def send_message_via_whatsapp(body,to):
    """
    Sends a WhatsApp message using the Twilio API.

    This function initializes a Twilio client Account SID and Auth Token,
    then a WhatsApp message from the Twilio sandbox number to a verified recipient.

    Args:
    1) body: What message is to be sent.
    2) to: To whom will it be sent to.
    Note:
        - The recipient number must be verified with the Twilio WhatsApp sandbox.

    Returns:
        None: Prints the message body upon successful send.
    """
    account_sid = os.getenv("account_sid")
    auth_token = os.getenv("auth_token")
    from_ = os.getenv("from_")

    client = Client(account_sid, auth_token)

    message = client.messages.create(
    body=f'{body}',
    from_=from_,
    to=f'whatsapp:{to}'
    )
    print(message.body)


@mcp.tool()
def send_message_on_slack(channel: str, message: str):
    """
    Sends a message to a Slack channel using Slack Bot Token.

    Args:
        channel (str): Slack channel ID or name (e.g., '#general' or 'C12345678').
        message (str): The text message to send.

    Note:
        - Requires SLACK_BOT_TOKEN in environment variables.
        - The bot must be added to the channel before sending.
    """
    slack_token = os.getenv("SLACK_BOT_TOKEN")
    if not slack_token:
        return "❌ SLACK_BOT_TOKEN not found in environment variables."

    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {slack_token}"}
    payload = {"channel": channel, "text": message}

    response = requests.post(url, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        if data.get("ok"):
            return f"✅ Message sent to {channel}: {message}"
        else:
            return f"❌ Failed: {data.get('error')}"
    else:
        return f"❌ Slack API error {response.status_code}: {response.text}"



if __name__ == "__main__":
    mcp.run(transport="stdio")