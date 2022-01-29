#!/usr/bin/python3 -tt

"""Usage:
  remindme.py REMINDER TIME ... [options]

Options:
  -h --help           show this HELP message and exit
  --repeat FREQUENCY  repeat reminder with frequency
  --minutes MINUTES   minutes for custom repeat increment
  --hours HOURS       hours for custom repeat increment
  --days DAYS         days for custom repeat increment
  --weeks WEEKS       weeks for custom repeat increment
  --months MONTHS     months for custom repeat increment
  --years YEARS       years for custom repeat increment
  --until STOP        repeat until, e.g. 5-14-2020-9:15am [default: '1-1-2038-12:00am']
"""

#print('Usage: remindme "do laundry" 12-18-2016-12:09am')
import datetime
import json
import maya
import re
import requests
import sys
import boto3
from docopt import docopt
import os

"""
today, tomorrow, M-Sun, next week, tonight
"""
monday = ['monday','mon','m']
tuesday = ['tuesday','tue','tues','t', 'tu']
wednesday = ['wednesday' ,'wed','weds','w']
thursday = ['thursday','thu','thurs','thur','th']
friday = ['friday','fri', 'f']
saturday = ['saturday', 'sat', 'sa']
sunday = ['sunday', 'sun', 'su']
weekdays = monday + tuesday + wednesday + thursday + friday + saturday + sunday

def time_of_day(time):
    # 8am, 8pm, 12am, 8:30am, 8:30pm, 12:30pm
    pattern = re.compile('(\d\d?)(:(\d\d))?(am|pm)')
    if pattern.match(time):
        hour = int(pattern.match(time).groups()[0])
        ampm = pattern.match(time).groups()[3]
        minute = pattern.match(time).groups()[2]
        if minute == None:
            minute = 0
        minute = int(minute)
    else:
        print('INVALID TIME FORMAT')
        print('try: 8am, 8:30am, 12pm, 12:17pm')
        sys.exit(0)
    if hour == 12:
        hour = 0
    if ampm == 'pm':
        hour += 12
    return (hour, minute)

def james_date_to_epoch(james_date):
    parts = james_date.split('-')
    if len(parts) != 4:
        raise ValueError(bad_time_syntax)
    month = parts[0]
    day = parts[1]
    year = parts[2]
    hour, minute = time_of_day(parts[3])
    maya_format = '{}-{}-{} {}:{}'.format(year, month, day, hour, minute)
    return maya.when(maya_format,timezone=timezone)

def get_midnight(timezone):
    now = maya.now()
    local_now = now.datetime(to_timezone=timezone, naive=True)
    year = local_now.year
    month = local_now.month
    day = local_now.day
    midnight = maya.when('-'.join(map(str,[year, month, day])), timezone=timezone)
    return midnight

def upload_reminder(time, reminder, api_key, url, readable):
    payload = {
        'reminder': reminder,
        'time': time,
        'readable_reminder_time': readable
    }
    headers = {
        'x-api-key': api_key
    }
    print(f'{url=}')
    #response = requests.post(url, data=json.dumps(payload))
    response = requests.post(url, data=json.dumps(payload), headers=headers)
    json_response = json.loads(response.text)
    print(json_response['message'])

def get_weekday_index(weekday):
    weekday = weekday.lower()
    if weekday in monday:
        return 0
    elif weekday in tuesday:
        return 1
    elif weekday in wednesday:
        return 2
    elif weekday in thursday:
        return 3
    elif weekday in friday:
        return 4
    elif weekday in saturday:
        return 5
    elif weekday in sunday:
        return 6
    else:
        print('expected a weekday or weekday abbreviation but got: {}'.format(weekday))
        sys.exit(0)

def get_days_from_today(target_weekday):
    # datetime weekday is a value from 0 to 6: Monday is 0, Thursday is 3, Sunday is 6
    today_weekday = datetime.datetime.today().weekday()
    target_weekday = get_weekday_index(target_weekday)
    if today_weekday < target_weekday:
        return target_weekday - today_weekday
    else:
        return 7 - today_weekday + target_weekday

def parse_time(time, midnight):
    if time[0].endswith('am') or time[0].endswith('pm'):
        return james_date_to_epoch(time[0])
    if time[-1].endswith('am') or time[-1].endswith('pm'):
        hours, minutes = time_of_day(time[-1])
    if time == ['tonight']:
        return midnight.add(hours=20)
    if time == ['tomorrow', 'morning']:
        return midnight.add(days=1, hours=8)
    if time[0] == 'today':
        return midnight.add(hours=hours, minutes=minutes)
    if time[0] == 'tomorrow':
        return midnight.add(days=1, hours=hours, minutes=minutes)
    if time[0].lower() in weekdays:
        days = get_days_from_today(time[0])
        return midnight.add(days=days, hours=hours, minutes=minutes)
    return midnight

def readable_timestamp(time):
    return maya.when(str(time),timezone=timezone).datetime(to_timezone=timezone)

def get_increment():
    if not arguments['--repeat']:
        print('expected repeats flag')
        sys.exit(0)
    repeat_option = arguments['--repeat']
    if repeat_option == 'daily':
        return {'days': 1}
    elif repeat_option == 'weekly':
        return {'days': 7}
    elif repeat_option == 'monthly':
        return {'months': 1}
    elif repeat_option in ['fortnightly', 'biweekly']:
        return {'days': 14}
    elif repeat_option == 'quarterly':
        return {'months': 3}
    elif repeat_option == 'biannually':
        return {'months': 6}
    elif repeat_option in ['yearly','annually']:
        return {'years': 1}
    elif repeat_option == 'custom':
        custom_flags = ['--minutes','--hours','--days','--weeks','--months','--years']
        return {flag[2:]:int(arguments[flag]) for flag in custom_flags if arguments[flag]}
    else:
        print('invalid repeat flag option')
        sys.exit(0)

def repeat_reminder(time, reminder):
    stop_date = james_date_to_epoch(arguments['--until'])
    stop_time = int(stop_date._epoch)
    print('stop date: ' + str(readable_timestamp(stop_time)))
    increment = get_increment()
    while int(time.add(**increment)._epoch) < stop_time:
        time = time.add(**increment)
        print_time = int(time._epoch)
        upload_reminder(print_time, reminder, password, url, str(readable_timestamp(print_time)))

def get_default_stack_id():
    return 'CdkReminders'

def get_client_credentials():
    url = os.popen('terraform output url').read().rstrip().strip('"')
    api_key = os.popen('terraform output api_key').read().rstrip().strip('"')
    timezone = 'US/Eastern'
    return url, api_key, timezone

        
if __name__ == '__main__':
    arguments = docopt(__doc__, version='Reminders 0.1')
    url, api_key, timezone = get_client_credentials()
    #print(f'{api_key=}')
    reminder = arguments['REMINDER']
    midnight = get_midnight(timezone)
    time = parse_time(arguments['TIME'], midnight)
    print_time = int(time._epoch)
    upload_reminder(print_time, reminder, api_key, url, str(readable_timestamp(print_time)))
    if arguments['--repeat']:
        repeat_reminder(time, reminder)
