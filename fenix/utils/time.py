# Copyright (c) 2018 OpenStack Foundation.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
import datetime


def str_to_datetime(dt_str):
    mdate, mtime = dt_str.split()
    year, month, day = map(int, mdate.split('-'))
    hours, minutes, seconds = map(int, mtime.split(':'))
    return datetime.datetime(year, month, day, hours, minutes, seconds)


def datetime_to_str(dt):
    return (dt.strftime('%Y-%m-%d %H:%M:%S'))


def reply_time_str(wait):
    now = datetime.datetime.utcnow()
    reply = now - datetime.timedelta(
        seconds=wait)
    return (reply.strftime('%Y-%m-%d %H:%M:%S'))


def time_now_str():
    return datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')


def is_time_after_time(before, after):
    if type(before) == str:
        time_before = str_to_datetime(before)
    else:
        time_before = before
    if type(after) == str:
        time_after = str_to_datetime(after)
    else:
        time_after = after
    if time_before > time_after:
        return True
    else:
        return False
