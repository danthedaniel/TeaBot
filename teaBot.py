import time    #Allows the program to use the sleep() command
import datetime#Makes it easy to compute the deltaT in days
import re      #Allows the program to use Regular Expressions
import praw    #A wrapper for the reddit API. Provides all of the reddit-related methods
import json

import logging #Used for error reporting/debugging
import ConfigParser

import urllib  #Used to encode strings for use in URLs
from HTMLParser import HTMLParser

class TeaBot:
    def __init__(self, config_file):
        config = ConfigParser.RawConfigParser()
        config.read(config_file)

        self.username  = config.get('teaBot credentials', 'username')
        self.password  = config.get('teaBot credentials', 'password')

        self.modteam   = config.get('ModTeam credentials', 'username')
        self.modteampw = config.get('ModTeam credentials', 'password')

        version   = config.get('General', 'version')
        sr_name   = config.get('General', 'subreddit')
        useragent = config.get('General', 'useragent')

        del config

        self.cache_timeouts = {'modmail': 0, 'inbox': 0, 'automoderator_wiki': 0, 'usernotes_wiki': 0, 'stylesheet': 0}
        self.message_backlog = []

        logging.basicConfig(filename='teaBot.log',level=logging.DEBUG)

        self.r = praw.Reddit(user_agent=useragent)
        self.r.login(self.username, self.password)

        self.subreddit = self.r.get_subreddit(sr_name)

        self.printlog('LittleteaBot for ' + sr_name + '/' + version + ' started')

    #Subreddit parameter is required to check for moderators
    def check_pms(self):
        parser = HTMLParser()

        if (time.time() - self.cache_timeouts['inbox']) > self.r.config.cache_timeout + 1:
            self.cache_timeouts['inbox'] = time.time()

            for message in self.r.get_unread(limit=None):     
                if message.new == True:
                    message.mark_as_read()

                    if message.author.name == 'AutoModerator':
                        unesc_body = parser.unescape(message.body)

                        if message.subject == 'AutoModerator conditions updated':
                            update_message = self.message_backlog[-1].reply(unesc_body)
                            #update_message.collapse()
                            del self.message_backlog[-1]
                            
                        else:
                            self.r.send_message('/r/' + self.subreddit.display_name, 'AutoModerator Message', unesc_body)

                    #elif message.author in self.subreddit.get_moderators():
                        #self.message_commands(message, self.subreddit)

    def check_modmail(self):
        parser = HTMLParser()

        sub_prefix = re.compile(ur'^[\[\()]?eli[5f]\s?[:-\]\)]?\s?', re.IGNORECASE)
        report_check = re.compile(ur'report', re.IGNORECASE)

        if (time.time() - self.cache_timeouts['modmail']) > self.r.config.cache_timeout + 1:
            self.cache_timeouts['modmail'] = time.time()

            for modmail in self.subreddit.get_mod_mail(limit=6):        
                #Perform checks on top level modmail            
                if modmail.new == True:
                    modmail.mark_as_read()

                    if report_check.search(modmail.subject) == None and sub_prefix.search(modmail.subject) != None and len(modmail.subject) > 6:
                        #Make certain that the text can be put into a url/markdown code safely
                        unesc_subject = parser.unescape(modmail.subject)
                        unesc_body = parser.unescape(modmail.body)
                        
                        safe_subject = urllib.quote_plus(unesc_subject.encode('utf-8'))
                        safe_body = urllib.quote_plus(unesc_body.encode('utf-8'))
                        
                        modmail.reply('It appears that you have accidentally posted a question in modmail rather than create a new submission.\n\n[Click Here](http://www.reddit.com/r/' + self.subreddit.display_name + '/submit?selftext=true&title=' + safe_subject + '&text=' + safe_body +') to turn this modmail into a submission.\n\nPlease [check our rules for posting](http://reddit.com/r/' + self.subreddit.display_name + '/wiki/rules) while you are at it and make sure your submission is a good fit for ELI5.')
                        self.printlog('Sent modmail to ' + modmail.author.name + ' about accidental ELI5 thread in modmail')

                    if modmail.distinguished == 'moderator':
                        self.message_commands(modmail)

                #Perform checks on modmail replies
                for reply in modmail.replies:
                    if reply.new == True:
                        reply.mark_as_read()

                        if reply.distinguished == 'moderator':
                            self.message_commands(reply)

    def message_commands(self, message):
        parser = HTMLParser()

        url_verifier = re.compile(ur'(https?://(?:www.)?reddit.com/r/' + self.subreddit.display_name + ur'/comments/([A-Za-z\d]{6})/[^\s]+/([A-Za-z\d]{7})?)')
        comment_finder = re.compile(ur'---\n\n?([\S\s]*?)\n\n?---') #For cutting lock/sticky messages out of commands

        #Used for shadowbanning and locking
        automod_jobs = []
        automod_jobs.append([]) #Type
        automod_jobs.append([]) #Data

        #Used for stickying lock reason comments
        stylesheet_jobs = []
        stylesheet_jobs.append([]) #Type
        stylesheet_jobs.append([]) #Data

        #Currently only adds shadowban not for username given - can not do anything else
        usernotes_jobs = []
        usernotes_jobs.append([]) #Username
        usernotes_jobs.append([]) #Reason - optional
        usernotes_jobs.append([]) #Link - optional needs to be pre-formatted

        command_finder = re.compile(ur'^!([^\s].*)$', re.MULTILINE)
        matches = re.findall(command_finder, message.body)

        for group in matches:
            command = group.split(' ')

            if command[0].lower() == 'shadowban':
                self.do_shadowban(self, message, command, automod_jobs, usernotes_jobs, url_verifier)
            elif command[0].lower() == 'ban':
                self.do_ban(self, message, command)
            elif command[0].lower() == 'lock':
                self.dolock(self, message, command, automod_jobs, stylesheet_jobs, url_verifier, comment_finder)
            elif command[0].lower() == 'sticky':
                self.do_sticky(self, message, command, url_verifier, comment_finder)
            elif command[0].lower() == 'summary':
                self.do_summary(self, message, command, parser)
            else:
                message.reply('**Unknown Command:**\n\n    !' + command[0])

            #End of command parsing

        if len(automod_jobs[0]) > 0: #If necessary apply all recent changes to automoderator configuration page
            self.apply_automod_jobs(self, message, automod_jobs, parser)
        if len(usernotes_jobs[0]) > 0:
            self.apply_usernotes_jobs(self, message, usernotes_jobs, parser)
        if len(stylesheet_jobs[0]) > 0:
            self.apply_stylesheet_jobs(self, message, stylesheet_jobs, parser)

    def printlog(self, logmessage):
        logging.info('[' + time.ctime(int(time.time())) + '] ' + logmessage)
        print('[' + time.ctime(int(time.time())) + '] ' + logmessage)
        
    def do_shadowban(self, message, command, automod_jobs, usernotes_jobs, url_verifier):
        try:
            automod_jobs[0].append('shadowban')
            automod_jobs[1].append(command[1]) #username for automod wiki editing

            shadowban_reason = ' '.join(command[2:])
            link_code = 'm,' + message.id

            usernotes_jobs[0].append(command[1]) #username to add to usernotes
            usernotes_jobs[1].append(shadowban_reason)

            if len(command) == 2:
                message.reply('User [**' + command[1] + '**](http://reddit.com/user/' + command[1] + ') has been shadowbanned.')
                usernotes_jobs[2].append(link_code)
            else:
                url_matches = re.search(url_verifier, shadowban_reason)

                if url_matches != None:
                    permalink  = url_matches.groups(0)[0]
                    thread_id  = url_matches.groups(0)[1]

                    link_code = 'l,' + thread_id

                    try:
                        comment_id = url_matches.groups(0)[2]

                        link_code += ',' + comment_id

                    except IndexError:
                        pass

                usernotes_jobs[2].append(link_code)

                if link_code == '':
                    message.reply('User [**' + command[1] + '**](http://reddit.com/user/' + command[1] + ') has been shadowbanned for *' + shadowban_reason + '*')
                else:
                    message.reply('User [**' + command[1] + '**](http://reddit.com/user/' + command[1] + ') has been shadowbanned for *' + shadowban_reason + '*')

            self.printlog(command[1] + ' pending shadowban')

        except:
            self.printlog('Error while responding to shadowban command for ' + command[1])

    def do_ban(self, message, command):
        if len(command) == 2:
            try:
                user = self.r.get_redditor(command[1])
                self.subreddit.add_ban(user)

                message.reply('User **' + command[1] + '** has been banned')
            except Exception,e:
                self.printlog('Error while banning ' + command[1] + ': ' + str(e))
        else:
            message.reply('**Syntax Error**:\n\n    !Ban username')
            
    def do_lock(self, message, command, automod_jobs, stylesheet_jobs,  url_verifier, comment_finder):

        if len(command) >= 2:
            url_matches = re.search(url_verifier, command[1])

            if url_matches != None:
                permalink = url_matches.groups(0)[0]
                thread_id = url_matches.groups(0)[1]

                automod_jobs[0].append('lock')
                automod_jobs[1].append(thread_id)

                try:
                    modteam = praw.Reddit(user_agent=self.useragent)
                    modteam.login(self.modteam, self.modteampw)

                    locked_thread = praw.objects.Submission.from_url(modteam, permalink)
                    locked_thread.set_flair('Locked')

                    comment_matches = re.search(comment_finder, message.body)

                    if comment_matches != None:
                        body_text = comment_matches.groups(0)[0]
                        message_appendix = '\n\n---\n\n[Here\'s a more general explanation on why threads get locked](http://www.reddit.com/r/explainlikeimfive/comments/1secxi/eli5_why_are_some_threads_locked/)'

                        new_comment = locked_thread.add_comment(body_text + message_appendix)
                        new_comment.distinguish()

                        stylesheet_jobs[0].append('lock_sticky')
                        stylesheet_jobs[1].append(new_comment.id)

                        message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
                    else:
                        message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nPlease post a comment explaining why it has been locked.')
                        
                    self.printlog('Locked ' + thread_id)

                    del modteam

                except Exception,e:
                    self.printlog('Error while locking ' + thread_id + ': ' + str(e))

            else:
                message.reply('**Error:**\n\nMalformed URL: ' + command[1] + '\n\nAcceptable format: http://www.reddit.com/r/' + self.subreddit.display_name + '/comments/linkid/title')
                self.printlog('Malformed URL for thread lock by ' + message.author.name + ': ' + command[1])

        else:
            message.reply('**Syntax Error**:\n\n    !lock threadURL')

    def do_sticky(self, message, command, url_verifier, comment_finder):
    
        if len(command) >= 2:
            try:
                #modteam = praw.Reddit(user_agent=self.useragent)
                #modteam.login(self.modteam, self.modteampw)
                
                comment_matches = re.search(comment_finder, message.body)

                if comment_matches != None:
                    body_text = comment_matches.groups(0)[0]
                    url_matches = re.search(url_verifier, command[1])

                    if url_matches == None:
                        title = ' '.join(command[1:])

                        stickied_thread = self.r.submit(self.subreddit, title, text=body_text)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\n')

                        self.printlog('Successfully stickied thread: ' + title)

                    else:
                        permalink = url_matches.groups(0)[0]

                        stickied_thread = praw.objects.Submission.from_url(modteam, permalink)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        new_comment = stickied_thread.add_comment(comment_matches.groups(0)[0])
                        new_comment.distinguish()

                        message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
                        
                        self.printlog('Successfully stickied thread: ' + stickied_thread.title)

                else:
                    message.reply('You must provide text for the sumission. The format for a sticky is:\n\n    !sticky title|link\n    ---\n    Post Body\n    ---')

                del modteam

            except Exception,e:
                self.printlog('Error while sticky-ing thread: ' + str(e))

        else:
            message.reply('**Syntax Error**:\n\n    !sticky title|link\n    ---\n    Post Body\n    ---')

    def do_summary(self, message, command, parser):
        if len(command) > 1:
            try:
                if (time.time() - self.cache_timeouts['usernotes_wiki']) < self.r.config.cache_timeout + 1:
                    time.sleep(int(time.time() - self.cache_timeouts['usernotes_wiki']) + 1)
                
                self.cache_timeouts['usernotes_wiki'] = time.time()

                usernotes = self.r.get_wiki_page(self.subreddit, 'usernotes')
                unesc_usernotes = parser.unescape(usernotes.content_md)
                json_notes = json.loads(unesc_usernotes)

                moderators = json_notes['constants']['users']
                warnings = json_notes['constants']['warnings']

                bot_reply = ''

                user = self.r.get_redditor(command[1])

                deltaT = int(time.time() - user.created_utc)
                bot_reply += '**User Report:** [/u/' + user.name + '](http://reddit.com/user/' + user.name + ') - Age: ' + str(datetime.timedelta(0, deltaT)) + '\n\n'

                try: #Usernotes
                    notes = json_notes['users'][user.name]['ns']

                    bot_reply += '---\n\nWarning | Reason | Moderator\n---|---|----\n'

                    for note in notes:
                        permalink = ''
                        
                        if note['l'] != '':
                            try:
                                ids = note['l'].split(',')

                                if ids[0] == 'l':
                                    permalink = 'http://www.reddit.com/r/' + self.subreddit.display_name + '/comments/' + ids[1] + '/'
                                    permalink += 'a/' + ids[2]

                                elif ids[0] == 'm':
                                    permalink = 'http://www.reddit.com/message/messages/' + ids[1]

                            except IndexError:
                                pass

                        if permalink == '':
                            bot_reply += warnings[note['w']] + ' | ' + note['n'] + ' | ' + moderators[note['m']] + '\n'
                        else:
                            bot_reply += warnings[note['w']] + ' | [' + note['n'] + '](' + permalink + ') | ' + moderators[note['m']] + '\n'

                except KeyError:
                    self.printlog('Could not find user ' + user.name + ' in usernotes')

                content = []

                try: #Comments and submissions
                    for comment in user.get_comments(limit=100):
                        if comment.subreddit == self.subreddit:
                            content.append(comment)

                        if len(content) > 30:
                            break

                    for submitted in user.get_submitted(limit=20):
                        if submitted.subreddit == self.subreddit:
                            content.append(submitted)                        

                    content.sort(key=lambda x: x.score, reverse=False)

                    #Cut down to bottom 12 content
                    while len(content) > 12:
                        del content[12]

                    bot_reply += '\nLink | Body/Title | Score\n---|---|----\n'

                    for content_object in content:
                        if type(content_object) == praw.objects.Comment:
                            temp_comment = content_object.body.replace('\n', ' ')

                            #Cut down comments to 200 characters, while extending over the 200 char limit
                            #to preserve markdown links
                            if len(temp_comment) > 200:
                                i = 200
                                increment = -1

                                link = False

                                while i > -1 and (i + 1) < len(temp_comment):
                                    if temp_comment[i] == ')':
                                        link = True
                                        break

                                    if temp_comment[i] == '(':
                                        if temp_comment[i - 1] == ']':
                                            increment = 1
                                        else:
                                            break

                                    i += increment

                                i += 1
                                
                                if i < 200 or link == False:
                                    i = 200

                                temp_comment = temp_comment[:i]

                                if i >= len(temp_comment):
                                    temp_comment += '...'

                            if content_object.banned_by == None:
                                bot_reply += '[Comment](' + content_object.permalink + '?context=3) | ' + temp_comment + ' | ' + str(content_object.score) + '\n'
                            else:
                                bot_reply += '[**Comment**](' + content_object.permalink + '?context=3) | ' + temp_comment + ' | ' + str(content_object.score) + '\n'

                        if type(content_object) == praw.objects.Submission:
                            if content_object.banned_by == None:
                                bot_reply += '[Submission](' + content_object.permalink + ') | ' + content_object.title + ' | ' + str(content_object.score) + '\n'
                            else:
                                bot_reply += '[**Submission**](' + content_object.permalink + ') | ' + content_object.title + ' | ' + str(content_object.score) + '\n'

                except Exception,e:
                    self.printlog('Error while trying to read user comments:' + str(e))

                message.reply(bot_reply)
                self.printlog('Summary on ' + user.name + ' provided')

            except Exception,e:
                message.reply('**Error**:\n\nError while providing summary')
                self.printlog('Error while trying to give summary on ' + command[1] + ': ' + str(e))

        else:
            message.reply('**Syntax Error**:\n\n    !Summary username')            
    
    def apply_automod_jobs(self, message, automod_jobs, parser):
        if (time.time() - self.cache_timeouts['automoderator_wiki']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - self.cache_timeouts['automoderator_wiki']))
        
        self.cache_timeouts['automoderator_wiki'] = time.time()

        automod_config = self.r.get_wiki_page(self.subreddit, 'automoderator')
        new_content = parser.unescape(automod_config.content_md)

        for x in range(len(automod_jobs[0])):
            if automod_jobs[0][x] == 'shadowban':
                new_content = new_content.replace('do_not_remove', 'do_not_remove, ' + automod_jobs[1][x])

            elif automod_jobs[0][x] == 'lock':
                new_content = new_content.replace('do_not_touch', 'do_not_touch, ' + automod_jobs[1][x])

        try:
            if len(automod_jobs[0]) == 1:
                if automod_jobs[0][0] == 'shadowban':
                    reason = message.author.name + ': Shadowbanning ' + automod_jobs[1][0] + ' for ' + shadowban_reason

                elif automod_jobs[0][0] == 'lock':
                    reason = message.author.name + ': Locking ' + automod_jobs[1][0]

            else:
                reason = message.author.name + ': Multiple reasons'

            self.r.edit_wiki_page(self.subreddit, 'automoderator', new_content, reason)
            self.r.send_message('AutoModerator', self.subreddit.display_name, 'update')

            self.message_backlog.append(message)

            self.printlog('Updated AutoModerator wiki page')

        except Exception,e:
            self.printlog('Error while updating AutoModerator wiki page: ' + str(e))

    def apply_usernotes_jobs(self, message, usernotes_jobs, parser):
        if (time.time() - self.cache_timeouts['usernotes_wiki']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - self.cache_timeouts['usernotes_wiki']))
        
        self.cache_timeouts['usernotes_wiki'] = time.time()

        usernotes_page = self.r.get_wiki_page(self.subreddit, 'usernotes')
        content = parser.unescape(usernotes_page.content_md)

        notes = json.loads(content)

        moderators = notes['constants']['users']
        mod_name = message.author.name

        try:
            mod_index = moderators.index(mod_name)
        except ValueError:
            notes['constants']['users'].append(mod_name)
            mod_index = moderators.index(mod_name)

        for x in range(len(usernotes_jobs[0])):
            try:
                username = self.r.get_redditor(usernotes_jobs[0][x]).name
            except:
                username = usernotes_jobs[0][x]

            if usernotes_jobs[1][x] == '':
                reason = 'Shadowbanned'
            else:
                reason = 'Shadowbanned for ' + usernotes_jobs[1][x]

            time_of_ban = int(1000*time.time())

            new_JSON_object = json.loads('{"n":"' + reason + '","t":' + str(time_of_ban) + ',"m":' + str(mod_index) + ',"l":"' + usernotes_jobs[2][x] + '","w":1}')

            try:
                notes['users'][username]['ns'].insert(0, new_JSON_object)
            except KeyError:
                notes['users'][username] = {}
                notes['users'][username]['ns'] = []
                notes['users'][username]['ns'].append(new_JSON_object)

        if len(usernotes_jobs[0]) == 1:
            edit_reason = message.author.name + ': "create new note on ' + usernotes_jobs[0][x] + '" via ' + self.username
        else:
            edit_reason = message.author.name + ': "create new note on multiple users" via ' + self.username

        new_content = json.dumps(notes)
        self.r.edit_wiki_page(self.subreddit, 'usernotes', new_content, edit_reason)

        self.printlog('Added shadowban notice to usernotes for ' + username)

    def apply_stylesheet_jobs(self, message, stylesheet_jobs, parser):
        if (time.time() - self.cache_timeouts['stylesheet']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - self.cache_timeouts['stylesheet']))

        self.cache_timeouts['stylesheet'] = time.time()

        stylesheet = self.r.get_stylesheet(self.subreddit)
        new_content = parser.unescape(stylesheet['stylesheet'])

        for x in range(len(stylesheet_jobs[0])):
            if stylesheet_jobs[0][x] == 'lock_sticky':
                new_content = new_content.replace('.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,', '.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,\n.comments-page .sitetable.nestedlisting>.thing.id-t1_' + stylesheet_jobs[1][x] + ',')
        
        try:
            self.r.set_stylesheet(self.subreddit, new_content)
            self.printlog('Updated stylesheet for stickied lock reason')
        except Exception,e:
            self.printlog('Error while updating stylesheet: ' + str(e))
                
