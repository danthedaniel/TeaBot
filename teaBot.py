import re
import praw
import html
import time
import shlex
import urllib
import logging
import traceback
import OAuth2Util
import configparser
from xml.sax.saxutils import unescape
import requests
from requests.exceptions import HTTPError

from modules import puni
from modules import mmdb
from teaBotExceptions import *

class subInfo:
    def __init__(self, r, subreddit):
        self.praw = subreddit
        self.un = puni.UserNotes(r, subreddit)
        self.mmdb = mmdb.ModmaildB(r, subreddit)
        
        self.cache_timeout = {'comments': 0, 
                              'modmail': 0, 
                              'automoderator_wiki': 0, 
                              'stylesheet': 0, 
                              'moderators': 0}

        self.permissions_cache = {}

        self.last_comment = 0

    def __str__(self):
        return self.praw.display_name

class TeaBot:
    def __init__(self, config_file):
        config = configparser.RawConfigParser()
        config.read(config_file)

        self.version        = config.get('General', 'version')
        sr_list        = config.get('General', 'subreddits').split(',')
        self.useragent = config.get('General', 'useragent')

        self.inbox_timeout = 0 # Bot's inbox timeout
        self.OAuth_timeout = time.time()

        logging.basicConfig(filename='teaBot.log', level=logging.WARNING)

        self.r = praw.Reddit(user_agent=self.useragent)
        self.o = OAuth2Util.OAuth2Util(self.r, configfile='config/oauth.txt')

        # Now that we're all OAuth'd up, override PRAW's time limits
        self.r.config.cache_timeout = -1
        self.cache_timeout = 6
        self.r.config.api_request_delay = 1.0

        if sr_list == '':
            sr_list = self.get_my_subreddits()

        self.printlog('TeaBot v' + self.version + ' started')

        self.subreddits = []

        # Get subreddits
        for sr_name in sr_list:
            self.subreddits.append(subInfo(self.r, self.r.get_subreddit(sr_name)))
            self.get_all_perms(self.subreddits[-1])

        self.url_verifier = re.compile(r'(https?://(?:www.)?reddit.com/r/\w{3,}/comments/([A-Za-z\d]{6})/[^\s]+/([A-Za-z\d]{7})?)')

    def stop(self):
        for subreddit in self.subreddits:
            subreddit.mmdb.close()

    def rounds(self):
        refresh_period = 3600 - 30 # Just a few seconds less than an hour

        if (time.time() - self.OAuth_timeout) >= refresh_period:
            self.OAuth_timeout = time.time()
            self.o.refresh()

        self.check_pms()

        for subreddit in self.subreddits:
            self.check_modmail(subreddit)

    def get_my_subreddits(self):
        sr_list = []
        response = self.r.request('https://api.reddit.com/subreddits/mine/moderator/').json()

        for subreddit in response['data']['children']:
            sr_list.append(subreddit['data']['display_name'])

        return sr_list

    def get_all_perms(self, subreddit, override=False):
        """
        Refreshes subreddit's cached moderator permissions if more than an hour has passed
        API will return permissions of:
        wiki, posts, access, mail, config, flair, or just: all
        """
        seconds_in_an_hour = 3600

        if (time.time() - subreddit.cache_timeout['moderators']) > seconds_in_an_hour or override:
            subreddit.cache_timeout['moderators'] = time.time()

            response = self.r.request('https://api.reddit.com/r/' + subreddit.praw.display_name + '/about/moderators/').json()

            for user in response['data']['children']:
                subreddit.permissions_cache[user['name']] = user['mod_permissions']

    def check_perms(self, subreddit, message, required_perms):
        """
        Raises ModPermissionError if the user does not have the correct permission
        """
        self.get_all_perms(subreddit)

        try:
            perms = subreddit.permissions_cache[message.author.name]
        except KeyError:
            self.get_all_perms(subreddit, override=True)
            perms = subreddit.permissions_cache[message.author.name]

        if 'all' in perms:
            return

        for perm in required_perms:
            if perm not in perms:
                raise ModPermissionError(message.author.name + ' does not have ' + perm)

    def check_pms(self):
        if (time.time() - self.inbox_timeout) > self.cache_timeout:
            self.inbox_timeout = time.time()

            for message in self.r.get_unread(limit=10):     
                if message.new == True:
                    message.mark_as_read()

    def check_modmail(self, subreddit):
        if (time.time() - subreddit.cache_timeout['modmail']) > self.cache_timeout:
            subreddit.cache_timeout['modmail'] = time.time()

            for modmail in subreddit.praw.get_mod_mail(limit=30):
                #Perform checks on top level modmail            
                if modmail.new == True:
                    subreddit.mmdb.addMail(modmail) # Add modmail to dB

                    modmail.mark_as_read()

                    if modmail.distinguished == 'moderator':
                        self.message_commands(modmail, subreddit)

                #Perform checks on modmail replies
                for reply in modmail.replies:
                    if reply.new == True:
                        subreddit.mmdb.addMail(reply) # Add modmail reply to dB

                        reply.mark_as_read()

                        if reply.distinguished == 'moderator':
                            self.message_commands(reply, subreddit)

    def message_commands(self, message, subreddit):
        command_finder = re.compile(r'^!([^\s].*)$(?:\n{0,2})((?:^>.*\n{0,2})+)?', re.MULTILINE)

        #Used for shadowbanning
        automod_jobs = []

        #Used for stickying lock reason comments
        stylesheet_jobs = []

        matches = re.findall(command_finder, unescape(message.body))

        for group in matches:
            command_line = shlex.split(group[0])
            command = command_line[0].lower()

            try:
                comment = group[1]
            except IndexError:
                comment = ''

            try:
                arguments = command_line[1:]
            except IndexError:
                arguments = ''

            try:
                if command == 'shadowban':
                    resp = self.do_shadowban(subreddit, message, arguments)

                    if resp:
                        automod_jobs.append(resp)                    
                elif command == 'ban':
                    self.do_ban(subreddit, message, arguments)
                elif command == 'lock':
                    resp = self.do_lock(subreddit, message, arguments, comment)

                    if resp:
                        stylesheet_jobs.append(resp)
                elif command == 'sticky':
                    self.do_sticky(subreddit, message, arguments, comment)
                #elif command == 'summary':
                    #self.do_summary(subreddit, message, arguments)
                elif command == 'spam':
                    self.do_spam(message, arguments)
                elif command == 'search':
                    self.do_search(subreddit, message, arguments)
                elif command == 'version':
                    self.do_version(message)
                else:
                    message.reply('**Unknown Command:**\n\n    !' + command[0])
            except ModPermissionError:
                message.reply('**Error:**\n\nYou have insufficient permissions to perform this command')
            except UserNotFoundError:
                message.reply('**Error**:\n\nUser not found')
            except Exception as e:
                message.reply('**Error**:\n\nAn unknown error occured, you may want to check the syntax of the command')
                self.printlog('Unhandled exception thrown while executing:\n' + group[0])
                traceback.print_exc()

        if len(automod_jobs) > 0: #If necessary apply all recent changes to automoderator configuration page
            self.apply_automod_jobs(subreddit, message, automod_jobs)
        if len(stylesheet_jobs) > 0:
            self.apply_stylesheet_jobs(subreddit, message, stylesheet_jobs)

    def printlog(self, logmessage):
        logging.info('[' + time.ctime(int(time.time())) + '] ' + logmessage)
        print('[' + time.ctime(int(time.time())) + '] ' + logmessage)

    def get_user(self, username):
        try:
            return self.r.get_redditor(username)

        except HTTPError as e:
            if e.response.status_code == 404:
                raise UserNotFoundError
            elif e.response.status_code in [502, 503, 504]:
                self.printlog('No response from server')
                return None
            else:
                raise e

    def do_version(self, message):
        message.reply('**TeaBot v' + self.version + '**')
        self.printlog('Gave out version info')

    def do_search(self, subreddit, message, arguments):
        self.printlog(str(message.author) + ' searching for ' + str(arguments))
        response = ''

        foundMail = subreddit.mmdb.findMail(arguments) 

        for modmail in foundMail:
            if modmail.id != message.id:
                try:
                    response += '1. [**' + str(modmail.author.name) + '**: ' + modmail.subject + '](http://reddit.com/message/messages/' + modmail.id + ')\n'
                except AttributeError:
                    response += '1. [**' + str(modmail.author.display_name) + '**: ' + modmail.subject + '](http://reddit.com/message/messages/' + modmail.id + ')\n' 

        if response == '':
            message.reply('**No matching results found**')
        else:
            message.reply('**Results:**\n\n' + response)

    def do_spam(self, message, arguments):
        user = self.get_user(arguments[0])

        spam_thread = self.r.submit('spam', 'overview for ' + user.name, url='http://reddit.com/user/' + user.name)
        message.reply('User [**' + user.name + '**](http://reddit.com/user/' + user.name + ') has been flagged in /r/spam [here](' + spam_thread.permalink + ').\n\nIf the account is still up after a few minutes you may need to [contact the admins](http://reddit.com/message/compose?subject=Spam - /u/' + user.name + '&to=/r/reddit.com).')

    def do_shadowban(self, subreddit, message, arguments):
        self.check_perms(subreddit, message, ['access'])
        user = self.get_user(arguments[0])

        reason = ' '.join(arguments[1:])

        n = puni.Note(user.name, reason, message.author.name, 'm,' + message.id, 'botban')
        subreddit.un.add_note(n)

        self.printlog(user.name + ' pending shadowban')

        return ['shadowban', user.name]

    def do_ban(self, subreddit, message, arguments):
        self.check_perms(subreddit, message, ['access'])
        user = self.get_user(arguments[0])

        reason = ' '.join(arguments[1:])
        subreddit.praw.add_ban(user.name)

        n = puni.Note(user.name, reason, message.author, 'm,' + message.id, 'permban')
        subreddit.un.add_note(n)

        if reason == '':
            message.reply('User [**' + user.name + '**](' + user._url + ') has been banned')
        else:
            message.reply('User [**' + user.name + '**](' + user._url + ') has been banned with the note: *' + reason + '*')

    def do_lock(self, subreddit, message, arguments, comment):
        self.check_perms(subreddit, message, ['posts'])

        pattern = re.compile(r'^http://(www\.)?')
        permalink = re.sub(pattern, 'https://www.', arguments[0])

        try:
            locked_thread = praw.objects.Submission.from_url(self.r, permalink)
        except Exception as e:
            message.reply('**Error:**\n\nMalformed URL: ' + arguments[0] + '\n\nAcceptable format: http://www.reddit.com/r/' + subreddit.praw.display_name + '/comments/linkid/')
            self.printlog('Malformed URL for thread lock: ' + arguments[0])
            raise CommandSyntaxError('Malformed thread URL')

        locked_thread.set_flair('Locked')

        if comment:
            new_comment = locked_thread.add_comment(comment)
            new_comment.distinguish()
            
            message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
            
            return ['lock_sticky', new_comment.id]
        else:
            message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nPlease post a comment explaining why it has been locked.')
                
        self.printlog('Locked ' + thread_id)

    def do_sticky(self, subreddit, message, arguments):
        self.check_perms(subreddit, message, ['posts'])

        if len(arguments) > 1:
            try:
                comment_matches = re.search(self.comment_finder, message.body)

                if comment_matches != None:
                    body_text = comment_matches.groups(0)[0]
                    url_matches = re.search(self.url_verifier, arguments[1])

                    if url_matches == None:
                        title = ' '.join(arguments[1:])

                        stickied_thread = self.r.submit(subreddit.praw, title, text=body_text)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\n')

                        self.printlog('Successfully stickied thread: ' + title)

                    else:
                        permalink = url_matches.groups(0)[0]

                        stickied_thread = praw.objects.Submission.from_url(self.r, permalink)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        new_comment = stickied_thread.add_comment(comment_matches.groups(0)[0])
                        new_comment.distinguish()

                        message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
                        
                        self.printlog('Successfully stickied thread: ' + stickied_thread.title)

                else:
                    message.reply('You must provide text for the sumission. The format for a sticky is:\n\n    !sticky title|link\n    ---\n    Post Body\n    ---')

            except Exception as e:
                self.printlog('Error while sticky-ing thread: ' + str(e))

        else:
            message.reply('**Syntax Error**:\n\n    !sticky title|link\n\n>Post Body\n\n>More body')

    def apply_automod_jobs(self, subreddit, message, automod_jobs):
        if (time.time() - subreddit.cache_timeout['automoderator_wiki']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - subreddit.cache_timeout['automoderator_wiki']))
        
        subreddit.cache_timeout['automoderator_wiki'] = time.time()

        automod_config = self.r.get_wiki_page(subreddit.praw, 'config/automoderator')
        new_content = unescape(automod_config.content_md)

        for x in range(len(automod_jobs)):
            if automod_jobs[x][0] == 'shadowban':
                new_content = new_content.replace('"do_not_remove"', '"do_not_remove", "' + automod_jobs[x][1] + '"')

        try:
            if len(automod_jobs) == 1:
                if automod_jobs[0][0] == 'shadowban':
                    reason = message.author.name + ': Shadowbanning ' + automod_jobs[0][1]
                    message.reply('User [**' + automod_jobs[0][1] + '**](http://reddit.com/user/' + automod_jobs[0][1] + ') has been shadowbanned.')
            else:
                reason = message.author.name + ': Multiple reasons'

            try:
                self.r.edit_wiki_page(subreddit.praw, 'config/automoderator', new_content, reason)
            
            except HTTPError as e:
                if e.response.status_code == 415:
                    j = json.loads(g.response._content.decode('utf-8'))

                    if j['reason'] == 'SPECIAL_ERRORS':
                        reason = j['special_errors']
                        message.reply('AutoModerator threw the following error:\n\n' + reason)

            self.printlog('Updated AutoModerator wiki page')

        except Exception as e:
            self.printlog('Error while updating AutoModerator wiki page: ' + str(e))

    def apply_stylesheet_jobs(self, subreddit, message, stylesheet_jobs):
        if (time.time() - subreddit.cache_timeout['stylesheet']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - subreddit.cache_timeout['stylesheet']))

        subreddit.cache_timeout['stylesheet'] = time.time()

        stylesheet = self.r.get_stylesheet(subreddit.praw)
        new_content = unescape(stylesheet['stylesheet'])

        for x in range(len(stylesheet_jobs)):
            if stylesheet_jobs[x][0] == 'lock_sticky':
                new_content = new_content.replace('.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,', '.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,\n.comments-page .sitetable.nestedlisting>.thing.id-t1_' + stylesheet_jobs[x][1] + ',')
        
        try:
            self.r.set_stylesheet(subreddit.praw, new_content)
            self.printlog('Updated stylesheet for stickied lock reason')
        except Exception as e:
            self.printlog('Error while updating stylesheet: ' + str(e))
