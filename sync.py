import calendar
import datetime
import json
import random

import gkeepapi

# noinspection PyUnresolvedReferences
from apiclient.discovery import build
from httplib2 import Http
from oauth2client import file, client, tools

"""
time setup
"""

now, next_days, previous_days = datetime.datetime.now(), {}, []


def get_note_str(dt):
    return calendar.day_name[dt.weekday()] + " " + str(dt.day) + "." + str(dt.month)


for i in range(7):
    next_days[get_note_str(now + datetime.timedelta(i))] = []

for i in range(-1, -10, -1):
    previous_days.append(get_note_str(now + datetime.timedelta(i)))

"""
login google calendar
"""

SCOPES = 'https://www.googleapis.com/auth/calendar.readonly'
store = file.Storage('credentials.json')
creds = store.get()
if not creds or creds.invalid:
    flow = client.flow_from_clientsecrets('calendar_secret.json', SCOPES)
    creds = tools.run_flow(flow, store)
service = build('calendar', 'v3', http=creds.authorize(Http()))

"""
login and sync google keep (sync can take some time)
"""

keep = gkeepapi.Keep()
with open("keep_secret.json") as f:
    creds_keep = json.load(f)
    keep.login(creds_keep["username"], creds_keep["app_password"])

"""
get upcoming events between today and 7 days from now
"""

d_start = now.isoformat() + 'Z'
d_fin = ((now + datetime.timedelta(7))
         .replace(hour=0, minute=0, second=0, microsecond=0)
         - datetime.timedelta(seconds=1)).isoformat() + 'Z'

events = service.events().list(calendarId='primary', timeMin=d_start, timeMax=d_fin,
                               singleEvents=True, orderBy='startTime').execute().get('items', [])

for event in events:
    start = event['start'].get('dateTime', event['start'].get('date'))

    try:
        dt = datetime.datetime.strptime(start.split("+")[0], '%Y-%m-%dT%H:%M:%S')
        next_days[get_note_str(dt)].append("%02d:%02d - %s" % (dt.hour, dt.minute, event["summary"]))

    except ValueError:
        # event for whole day
        dt = datetime.datetime.strptime(start, '%Y-%m-%d')
        next_days[get_note_str(dt)].append(event["summary"])

"""
get or add upcoming keep days
"""

for i, next_day in enumerate(next_days):
    glists = list(keep.find(func=lambda x: x.title == next_day))

    # check if note already exists
    if len(glists) > 0:
        glist = glists[0]
    else:
        glist = keep.createList(next_day, [])
        # noinspection PyTypeChecker
        glist.color = random.choice(list(gkeepapi.node.ColorValue))

    if i == 0:
        glist.pinned = True

    # add calendar summaries to list
    for summary in next_days[next_day]:
        if summary not in glist.text:
            glist.add(summary)

"""
remove old notes and add to backlog
"""

backlog = list(keep.find(func=lambda x: x.title == "Backlog"))[0]

for previous_day in previous_days:
    glists = list(keep.find(func=lambda x: x.title == previous_day))

    if len(glists) > 0:
        glist = glists[0]

        for item in glist.items:
            if not item.checked:
                backlog.add(item.text)

        glist.delete()

keep.sync()
