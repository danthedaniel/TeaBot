import praw
import re
import configparser
import time
from bs4 import BeautifulSoup
from requests.exceptions import HTTPError

import puni
from puni import exceptions

from . import command

class subInfo:
    def __init__(self, r, subreddit):
        self.r = r

        if type(subreddit) == str:
            self.praw = self.r.get_subreddit(subreddit)
        elif type(subreddit) == praw.objects.Subreddit:
            self.praw = subreddit
        else:
            raise TypeError('subInfo only accepts a string or a praw Subreddit object for the subreddit parameter')

        self.reset_timeouts()
        self.reset_usernotes()

    def __str__(self):
        return self.praw.display_name

    def reset_timeouts(self):
        self.cache_timeout = {'modmail': 0, 'automoderator_wiki': 0, 'stylesheet': 0}

    def reset_usernotes(self):
        try:
            self.un = puni.UserNotes(r, self.praw)
        except PuniPermissionError:
            self.r.send_message(self.praw, 'Permission Error', 'TeaBot does not have the `wiki` permission and can not access usernotes.\n\nTo utilize this functionality please add the permission node and run the `!reset` command.')

class TeaBot:
    def __init__(self, config):
        config = configparser.RawConfigParser()
        config.read(config)

        self.username  = config.get('teaBot credentials', 'username')
        self.password  = config.get('teaBot credentials', 'password')
        version        = config.get('General', 'version')
        self.useragent = config.get('General', 'useragent')

        self.inbox_timeout = 0

        self.r = praw.Reddit(user_agent=self.useragent)
        self.r.login(self.username, self.password)

        self.subreddits = self.init_subreddits()

        print('TeaBot v' + version + ' started')

        self.url_verifier = re.compile(r'(https?://(?:www.)?reddit.com/r/\w{3,}/comments/([A-Za-z\d]{6})/[^\s]+/([A-Za-z\d]{7})?)')

    def init_subreddits(self):
        subreddits = []
        sub_strip = re.compile(r'^.*/r/(\w+)/?$')

        soup = BeautifulSoup(r.request(r.user._url).content.decode('utf-8'))

        for link in soup.find(id="side-mod-list").find_all('a'):
            address = link.get('href')
            sr_name = re.search(sub_strip, address).group(1)

            sub = self.r.get_subreddit(sr_name)

            try:
                sub.fetch()
                subreddits.append(subInfo(self.r, sr_name))

                print('Added ' + sr_name + ' to list of subreddits to monitor')
            except HTTPError as e:
                if e.response.error_code == 404:
                    pass
                else:
                    raise e

        return subreddits

    def check_pms(self):
        if (time.time() - self.inbox_timeout) > self.r.config.cache_timeout + 1:
            self.inbox_timeout = time.time()

            for message in self.r.get_unread(limit=10):     
                if message.new == True:
                    message.mark_as_read()

                    if message.author == None and message.distinguished == 'moderator':
                        self.add_new_subreddit(message.subreddit)

    def check_modmail(self):
        for subreddit in self.subreddits:
            if (time.time() - subreddit.cache_timeout['modmail']) > self.r.config.cache_timeout + 1:
                subreddit.cache_timeout['modmail'] = time.time()

                for modmail in subreddit.praw.get_mod_mail(limit=6):        
                    #Perform checks on top level modmail            
                    if modmail.new == True:
                        modmail.mark_as_read()

                        if modmail.distinguished == 'moderator':
                            self.message_commands(modmail, subreddit)

                    #Perform checks on modmail replies
                    for reply in modmail.replies:
                        if reply.new == True:
                            reply.mark_as_read()

                            if reply.distinguished == 'moderator':
                                Command(subreddit, reply)

    def add_new_subreddit(self, subreddit):
        welcome_message = '''Before using TeaBot, please look at the command and permission documentation [here](http://www.reddit.com/r/teaearlgraycold/wiki/teabot).\n
        For full functionality you need to give TeaBot the following permissions: `mail`,`config`,`flair`,`wiki`,`access`,`posts`.'''
        
        self.r.accept_moderator_invite(subreddit)
        self.subreddits.append(subInfo(self.r, subreddit))
        self.r.send_message(subreddit, 'TeaBot Moderator Invite Acception', welcome_message)