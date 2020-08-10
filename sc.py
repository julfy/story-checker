#!/usr/bin/python3
import argparse
from datetime import datetime, timezone
import json
import os
import sys
import subprocess
import time
import logging
from collections import namedtuple
import xml.etree.ElementTree as ET


########################################
# -d to run in infinite loop with output to log
#
# Requires sSMTP
# # settings for /etc/ssmtp/ssmtp.conf
# FromLineOverride=YES
# mailhub=smtp.gmail.com:587 ### -> note 587 for STARTTLS
# UseTLS=Yes
# UseSTARTTLS=Yes
# AuthUser=xxxxx@gmail.com  ### Sender email
# AuthPass=xxxxx
#
########################################
LOGFILE = 'story_checker.log'
HISTORY_FILE = 'story_checker_history.json'
NOTIFY_EMAIL = None  # Receiver email


Chapter = namedtuple('Chapter', ['title', 'link', 'pubdate'])

log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


STORIES = [
    ('PGTE', 'https://practicalguidetoevil.wordpress.com/', 'pgte'),
    ('TGAB', 'https://tiraas.net/', 'tgab'),
    ('Metaworld Chronicles', 'https://www.royalroad.com/fiction/syndication/14167', 'rss'),
    ('Seaborn', 'https://www.royalroad.com/fiction/syndication/30131', 'rss'),
    ('The Humble Life of a Skill Trainer', 'https://www.royalroad.com/fiction/syndication/30737', 'rss'),
    ('Dungeon Crawler Carl', 'https://www.royalroad.com/fiction/syndication/29358', 'rss'),
    ('Healer', 'https://www.royalroad.com/fiction/syndication/32494', 'rss'),
    ('Villager Three', 'https://www.royalroad.com/fiction/syndication/32576', 'rss'),
    ('Savage Divinity', 'https://www.royalroad.com/fiction/syndication/5701', 'rss'),
    ('Displaced', 'https://www.royalroad.com/fiction/syndication/15538', 'rss'),
    ('Never Die Twice', 'https://www.royalroad.com/fiction/syndication/32067', 'rss'),
    ('Super Minion', 'https://www.royalroad.com/fiction/syndication/21410', 'rss'),
]

def pparse(tree, i=1):
    print(f'{" "*i}{tree.tag} {tree.attrib}')
    for ch in tree:
        pparse(ch, i+2)

### GETTERS

def get_royalroad_rss(link):
    data = subprocess.check_output(f'curl -s {link}'.split(' ')).decode()
    xml = ET.fromstring(data)
    for child in xml[0]:
        if child.tag == 'item':
            return Chapter(title=child[0].text, link=child[1].text, pubdate=datetime.strptime(child[4].text, '%a, %d %b %Y %H:%M:%S %Z').timestamp())


def get_tgab(link):
    data = subprocess.check_output(f'curl -s {link}'.split(' ')).decode()
    scut = data.find('<article')
    ecut = data.find('</article>', scut) + 10
    xml = ET.fromstring(f'{data[scut:ecut]}')

    def parse(tree):
        for ch in tree:
            if ch.tag == 'article':
                h1 = ch[0][0][0]  # .header.h1.a
                date = ch[0][1][0][0][0]  # .header.entry-meta.date.a.time
                return Chapter(title=h1.text, link=h1.attrib['href'], pubdate=datetime.strptime(date.attrib['datetime'], '%Y-%m-%dT%H:%M:%S%z').timestamp())
        return None

    return parse([xml])


def get_pgte(link):
    data = subprocess.check_output(f'curl -s {link}'.split(' ')).decode()
    acut = data.find('<article')
    if data[acut:acut+100].startswith('<article id="post-3"'):  # skip pinned
        acut = data.find('<article', acut+10)
    scut = data.find('<header', acut+10)
    ecut = data.find('</header>', scut) + 9
    xml = ET.fromstring(f'{data[scut:ecut]}')

    def parse(tree):
        for ch in tree:
            if ch.tag == 'header':
                h1 = ch[0][0]  # .h1.a
                date = ch[1][0][0][-1]  # .entry-meta.posted-on.a.time
                return Chapter(title=h1.text, link=h1.attrib['href'], pubdate=datetime.strptime(date.attrib['datetime'], '%Y-%m-%dT%H:%M:%S%z').timestamp())
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

# Replace getter names with actual getters
STORIES = list(map(assign_getters, STORIES))

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
        subprocess.run(['sudo', 'ssmtp', '-F', 'StoryChecker', address], stdin=subprocess.Popen(['printf', data], stdout=subprocess.PIPE).stdout)

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
        log.info(f'{new_pfx}{name} last updated on {pretty_date}')
        if is_new and self.send_email:
            self.send_notification(NOTIFY_EMAIL, name, chapter)

    def check_stories(self, stories):
        for story, link, getter in stories:
            self.check_story(story, link, getter)
            time.sleep(1.0)
        self.save_history()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument('-d', type=str, metavar='email', help = 'Start periodic check loop and send notifications to email; 1h period')
    group.add_argument('-t', type=str, metavar='email', help = 'Test run; sends email')

    args = parser.parse_args()
    if args.d:
        lh = logging.FileHandler(LOGFILE)
        lh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s : %(message)s'))
        log.addHandler(lh)
        NOTIFY_EMAIL=args.d
        checker = Checker(send=True)
        log.info('Starting loop')
        while True:
            time.sleep(3600.0)
            checker.check_stories(STORIES)
    elif args.t:
        log.addHandler(logging.StreamHandler(sys.stdout))
        NOTIFY_EMAIL=args.t
        c = Checker(send=True, update_history=False)
        c.check_stories([('Test', 'http://google.com', lambda link: Chapter('Chapter 1', link, 1))])
    else:
        log.addHandler(logging.StreamHandler(sys.stdout))
        c=Checker(send=False)
        c.check_stories(STORIES)
