#!/usr/bin/python3
import argparse
from datetime import datetime, timezone, timedelta
import html
import json
import os
import sys
import subprocess
import time
import logging
from collections import namedtuple
import xml.etree.ElementTree as ET

LOGFILE = 'story_checker.log'
HISTORY_FILE = 'story_checker_history.json'
NOTIFY_EMAIL = None  # Receiver email

Chapter = namedtuple('Chapter', ['title', 'link', 'pubdate'])

log = logging.getLogger(__name__)


def select_log_out(choice=None):
    log.setLevel(logging.DEBUG)
    if choice == 'file':
        lh = logging.FileHandler(LOGFILE)
    else:
        lh = logging.StreamHandler(sys.stdout)
    lh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s:\t%(message)s'))
    log.addHandler(lh)


STORIES = [
    # ('PGTE', 'https://practicalguidetoevil.wordpress.com/', 'pgte'),
    # ('Pale Lights', 'https://palelights613694448.wordpress.com/', '')
    ('TGAB', 'https://tiraas.net/', 'tgab'),
    ('Metaworld Chronicles', 'https://www.royalroad.com/fiction/syndication/14167', 'rss'),
    ('Seaborn', 'https://www.royalroad.com/fiction/syndication/30131', 'rss'),
    ('Dungeon Crawler Carl', 'https://www.royalroad.com/fiction/syndication/29358', 'rss'),
    ('Savage Divinity', 'https://www.royalroad.com/fiction/syndication/5701', 'rss'),
    ('Displaced', 'https://www.royalroad.com/fiction/syndication/15538', 'rss'),
    ('Super Minion', 'https://www.royalroad.com/fiction/syndication/21410', 'rss'),
    ('A Journey of Black and Red', 'https://www.royalroad.com/fiction/syndication/26675', 'rss'),
    ('The Calamitous Bob', 'https://www.royalroad.com/fiction/syndication/44132', 'rss'),
    ('The Many Lives of Cadence Lee', 'https://www.royalroad.com/fiction/syndication/35925', 'rss'),
    ('Delve', 'https://www.royalroad.com/fiction/syndication/25225', 'rss'),
    ('Only Villains Do That', 'https://www.royalroad.com/fiction/syndication/40182', 'rss'),
    # ('The Perfect Run', 'https://www.royalroad.com/fiction/syndication/36735', 'rss'),
    ('Kairos: A Greek Myth', 'https://www.royalroad.com/fiction/syndication/41033', 'rss'),
    ('I Am Going To Die', 'https://www.royalroad.com/fiction/syndication/21844', 'rss'),
    ('Tower of Somnus', 'https://www.royalroad.com/fiction/syndication/36983', 'rss'),
    ('Vigor Mortis', 'https://www.royalroad.com/fiction/syndication/40373', 'rss'),
    ('Sylver Seeker', 'https://www.royalroad.com/fiction/syndication/36065', 'rss'),
    ('Underland', 'https://www.royalroad.com/fiction/syndication/47557', 'rss'),
    ('REND', 'https://www.royalroad.com/fiction/syndication/32615', 'rss'),
    ('Essence of Cultivation', 'https://www.royalroad.com/fiction/syndication/34710', 'rss'),
    ('War Queen', 'https://www.royalroad.com/fiction/syndication/46850', 'rss'),
    ('This Used To Be About Dungeons', 'https://www.royalroad.com/fiction/syndication/45534', 'rss')
    # ('Blue Core', 'https://www.royalroad.com/fiction/syndication/25082', 'rss'),
]

def pparse(tree, i=1):
    print(f'{" "*i}{tree.tag} {tree.attrib}')
    for ch in tree:
        pparse(ch, i+2)

### GETTERS

def get_data(link):
    return html.unescape(subprocess.check_output(f'curl -s {link}'.split(' ')).decode())

def get_royalroad_rss(link):
    # html.unescape will break this
    data = subprocess.check_output(f'curl -s {link}'.split(' ')).decode()
    xml = ET.fromstring(data)
    for child in xml[0]:
        if child.tag == 'item':
            return Chapter(
                title=child[0].text,
                link=child[1].text,
                pubdate=datetime.strptime(child[4].text, '%a, %d %b %Y %H:%M:%S %Z').timestamp(),
            )


def get_tgab(link):
    data = get_data(link)
    acut = data.find('<article')
    while "post-password-required" in data[acut:acut+300]:
        acut = data.find('<article', acut+10)
    scut = data.find('<header', acut+10)
    ecut = data.find('</header>', scut) + 9

    xml = ET.fromstring(f'{data[scut:ecut]}')

    def parse(tree):
        for ch in tree:
            if ch.tag == 'header':
                h1 = ch[0][0]  # .h1.a
                date = ch[1][0][0][0]  # .entry-meta.date.a.time
                return Chapter(
                    title=h1.text,
                    link=h1.attrib['href'],
                    pubdate=datetime.strptime(date.attrib['datetime'], '%Y-%m-%dT%H:%M:%S%z').timestamp(),
                )
        return None

    return parse([xml])


def get_pgte(link):
    data = get_data(link)
    acut = data.find('<article')
    if data[acut : acut+100].startswith('<article id="post-3"'):  # skip pinned
        acut = data.find('<article', acut+10)
    scut = data.find('<header', acut+10)
    ecut = data.find('</header>', scut) + 9
    xml = ET.fromstring(f'{data[scut:ecut]}')

    def parse(tree):
        for ch in tree:
            if ch.tag == 'header':
                h1 = ch[0][0]  # .h1.a
                date = ch[1][0][0][-1]  # .entry-meta.posted-on.a.time
                return Chapter(
                    title=h1.text,
                    link=h1.attrib['href'],
                    pubdate=datetime.strptime(date.attrib['datetime'], '%Y-%m-%dT%H:%M:%S%z').timestamp(),
                )
        return None

    return parse([xml])


def assign_getters(r):
    story, link, getter_name = r
    if getter_name == 'rss':
        getter = get_royalroad_rss
    elif getter_name == 'tgab':
        getter = get_tgab
    elif getter_name == 'pgte':
        getter = get_pgte
    else:
        raise Exception(f'No getter named {getter_name}')
    return (story, link, getter)


class Checker:
    def __init__(self, send=False, update_history=True):
        self.send_email = send
        self.update_history = update_history
        self.history_file = os.path.expanduser(HISTORY_FILE)
        self.history = self.get_history()

    def get_history(self):
        if not os.path.exists(self.history_file):
            return {}
        with open(self.history_file, 'r') as inp:
            return json.loads(inp.read())

    def save_history(self):
        if not self.update_history:
            return
        with open(self.history_file, 'w') as out:
            out.write(json.dumps(self.history))

    def send_notification(self, address, name, chapter):
        if not address:
            raise Exception('Receiver address not set!')
        subject = name
        content = f'<a href="{chapter.link}">{chapter.title}</a>'
        data = f'Subject:{subject}\nContent-Type: text/html; charset="utf-8"\n\n{content}\n'
        subprocess.run(
            ['msmtp', '-a', 'sc-gmail', '-F', 'StoryChecker', address],
            stdin=subprocess.Popen(['printf', data], stdout=subprocess.PIPE).stdout,
        )

    def check_story(self, name, link, getter):
        try:
            chapter = getter(link)
        except Exception:
            log.exception(f'Failed to get {name}')
            return
        if chapter is None:
            log.error(f'Failed to get {name}')
            return
        last_ts = self.history.get(name, 0)
        is_new = last_ts < chapter.pubdate
        if is_new:
            self.history.update({name: chapter.pubdate})
        new_pfx = '--> ' if is_new else ''
        pretty_date = datetime.fromtimestamp(self.history[name]).replace(tzinfo=timezone.utc).astimezone(tz=None)
        log.info(f'{new_pfx}\t{pretty_date} - {name}')
        if is_new and self.send_email:
            self.send_notification(NOTIFY_EMAIL, name, chapter)

    def check_stories(self, stories):
        for story, link, getter in stories:
            self.check_story(story, link, getter)
            time.sleep(1.0)
        self.save_history()


def get_next_period():
    # delta = int(datetime.now().minute - 5)
    # period = 60.0 * (((delta >> 31) + 1) * 60 - delta)  # heh
    now = datetime.now()
    next_point = (now + timedelta(hours=1)).replace(minute=5, second=0, microsecond=0)
    period = (next_point - now).total_seconds()
    return period


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        '-d',
        type=str,
        metavar='email',
        help='Start periodic check loop and send notifications to email;'
        'run every 5th minute of an hour',
    )
    group.add_argument(
        '-t',
        type=str,
        metavar='email',
        default=None,
        const='NONE',
        nargs='?',
        help='Test run; sends email',
    )

    args = parser.parse_args()

    # Replace getter names with actual getters
    STORIES = list(map(assign_getters, STORIES))

    if args.d:
        select_log_out('file')
        NOTIFY_EMAIL = args.d
        checker = Checker(send=True)
        log.info('Starting loop')
        period = 600.0  # first time 10 minutes
        while True:
            log.info(f'Sleeping for {int(period)}s')
            time.sleep(period)
            checker.check_stories(STORIES)
            period = get_next_period()
    elif args.t:
        select_log_out('stdout')
        NOTIFY_EMAIL = args.t
        c = Checker(send=args.t != 'NONE', update_history=False)
        c.check_stories([('Test', 'http://google.com', lambda link: Chapter('Chapter 1', link, 1))])
    else:
        select_log_out('stdout')
        c = Checker(send=False, update_history=True)
        c.check_stories(STORIES)
