import praw
import re
import html
import shlex
import urllib
import logging
import traceback
import configparser
from xml.sax.saxutils import unescape

import time
import datetime

import puni
import mmdb
import teaBotExceptions

from requests.exceptions import HTTPError

class sub_info:
    def __init__(self, r, subreddit):
        self.cache_timeout = {'modmail': 0, 'automoderator_wiki': 0, 'stylesheet': 0}
        self.praw = subreddit
        self.un = puni.UserNotes(r, subreddit)
        self.mmdb = mmdb.ModmaildB(r, subreddit)

    def __str__(self):
        return self.praw.display_name

    def reset_timeouts(self):
        self.cache_timeout = {'modmail': 0, 'automoderator_wiki': 0, 'stylesheet': 0}

class TeaBot:
    def __init__(self, config_file):
        config = configparser.RawConfigParser()
        config.read(config_file)

        self.username  = config.get('teaBot credentials', 'username')
        self.password  = config.get('teaBot credentials', 'password')

        version        = config.get('General', 'version')
        sr_list        = config.get('General', 'subreddits').split(',')
        self.useragent = config.get('General', 'useragent')

        del config

        self.inbox_timeout = 0

        logging.basicConfig(filename='teaBot.log',level=logging.DEBUG)

        self.r = praw.Reddit(user_agent=self.useragent)
        self.r.login(self.username, self.password)

        self.printlog('TeaBot v' + version + ' started')

        self.subreddits = []

        #Get subreddits
        for sr_name in sr_list:
            self.subreddits.append(sub_info(self.r, self.r.get_subreddit(sr_name)))

        self.url_verifier = re.compile(r'(https?://(?:www.)?reddit.com/r/\w{3,}/comments/([A-Za-z\d]{6})/[^\s]+/([A-Za-z\d]{7})?)')

    def check_pms(self):
        if (time.time() - self.inbox_timeout) > 35:
            self.inbox_timeout = time.time()

            for message in self.r.get_unread(limit=10):     
                if message.new == True:
                    message.mark_as_read()

    def check_modmail(self):
        for subreddit in self.subreddits:
            # print(str(time.time() - subreddit.cache_timeout['modmail']))

            if (time.time() - subreddit.cache_timeout['modmail']) > 35:
                subreddit.cache_timeout['modmail'] = time.time()

                for modmail in subreddit.praw.get_mod_mail(limit=10):        
                    #Perform checks on top level modmail            
                    if modmail.new == True:
                        modmail.mark_as_read()
                        subreddit.mmdb.addMail(modmail) # Add modmail to dB

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
                else:
                    message.reply('**Unknown Command:**\n\n    !' + command[0])
            except Exception as e:
                self.printlog('Unhandled exception thrown while executing:\n' + group[0])
                traceback.print_exc()

        if len(automod_jobs) > 0: #If necessary apply all recent changes to automoderator configuration page
            self.apply_automod_jobs(subreddit, message, automod_jobs)
        if len(stylesheet_jobs) > 0:
            self.apply_stylesheet_jobs(subreddit, message, stylesheet_jobs)

    def printlog(self, logmessage):
        logging.info('[' + time.ctime(int(time.time())) + '] ' + logmessage)
        print('[' + time.ctime(int(time.time())) + '] ' + logmessage)

    def get_user(self, message, username):
        try:
            return self.r.get_redditor(username)

        except HTTPError as e:
            if e.response.status_code == 404:
                message.reply('**Error**:\n\nUser "' + username + '" not found')
                return None
            elif e.response.status_code in [502, 503, 504]:
                self.printlog('No response from server')
                return None
            else:
                raise e

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
        user = self.get_user(message, arguments[0])

        if (user != None):
            spam_thread = self.r.submit('spam', 'overview for ' + user.name, url=user._url)
            message.reply('User [**' + user.name + '**](' + user._url + ') has been flagged in /r/spam [here](' + spam_thread.permalink + ').\n\nIf the account is still up after a few minutes you may need to [contact the admins](http://reddit.com/message/compose?subject=Spam - /u/' + user.name + '&to=/r/reddit.com).')

    def do_shadowban(self, subreddit, message, arguments):
        user = self.get_user(message, arguments[0])

        assert(user != None)

        reason = ' '.join(arguments[1:])

        n = puni.Note(user.name,reason,message.author.name,'m,' + message.id,'botban')
        subreddit.un.add_note(n)

        self.printlog(user.name + ' pending shadowban')

        return ['shadowban', user.name]

    def do_ban(self, subreddit, message, arguments):
        user = self.get_user(arguments[0])

        if (user != None):
            if len(arguments) > 1:
                reason = ' '.join(arguments[1:])
                subreddit.praw.add_ban(user.name)

                n = puni.Note(user.name,reason,message.author,'m,' + message.id,'permban')
                subreddit.un.add_note(n)

                if reason == '':
                    message.reply('User [**' + user.name + '**](' + user._url + ') has been banned')
                else:
                    message.reply('User [**' + user.name + '**](' + user._url + ') has been banned with the note: *' + reason + '*')

            else:
                message.reply('**Syntax Error**:\n\n    !Ban username')

    def do_lock(self, subreddit, message, arguments, comment):
        if len(comment_line) >= 2:
            try:
                locked_thread = praw.objects.Submission.from_url(self.r, permalink)
            except Exception as e:
                message.reply('**Error:**\n\nMalformed URL: ' + arguments[0] + '\n\nAcceptable format: http://www.reddit.com/r/' + subreddit.praw.display_name + '/comments/linkid/')
                self.printlog('Malformed URL for thread lock: ' + arguments[0])

                raise CommandSyntaxError('Malformed thread URL')

            locked_thread.set_flair('Locked')

            if comment_matches != None:
                new_comment = locked_thread.add_comment(comment)
                new_comment.distinguish()

                message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
            else:
                message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nPlease post a comment explaining why it has been locked.')
                
                return ['lock_sticky', new_comment.id]

            self.printlog('Locked ' + thread_id)

        else:
            message.reply('**Syntax Error**:\n\n    !lock threadURL')
            raise CommandSyntaxError('No thread URL provided')

    def do_sticky(self, subreddit, message, arguments):
        if len(arguments) >= 2:
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
