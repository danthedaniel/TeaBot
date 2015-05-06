import praw
import re
import puni

from xml.sax.saxutils import unescape
from requests.exceptions import HTTPError

from .teaBot import subInfo

from puni import exceptions

class Command:
    def __init__(self, subreddit, message):
        self.subreddit = subreddit
        self.message = message

        self.automod_jobs = []
        self.stylesheet_jobs = []

        self.self.message_commands()

    def message_commands(self):
        command_finder = re.compile(r'^!([^\s].*)$(?:\n{0,2})((?:^>.*\n{0,2})+)?', re.MULTILINE)

        matches = re.findall(command_finder, unescape(self.message.body))

        for group in matches:
            command_line = group[0].split()
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
                    self.do_shadowban(arguments)
                elif command == 'ban':
                    self.do_ban(arguments)
                elif command == 'lock':
                    self.do_lock(arguments, comment)
                elif command == 'sticky':
                    self.do_sticky(arguments, comment)
                #elif command == 'summary':
                    #self.do_summary(arguments)
                elif command == 'spam':
                    self.do_spam(arguments)
                elif command == 'reset':
                    self.do_reset()
                else:
                    self.message.reply('**Unknown Command:**\n\n    !' + command[0])
            except UserNotFound as e:
                self.message.reply('**Error**:\n\nUser "' + str(e) + '" not found')
            except PuniPermissionError:
                self.message.reply('**Error**:\n\nCould not access UserNotes, check permissions')
            except HTTPError as e:
                if e.response.status_code == 403:
                    self.message.reply('**Error**:\n\nInsufficient permissions to execute command')
                else:
                    raise e
            except Exception as e:
                print('Unhandled exception thrown while executing:\n' + group[0])

        if len(automod_jobs) > 0: #If necessary apply all recent changes to automoderator configuration page
            self.apply_automod_jobs()
        if len(stylesheet_jobs) > 0:
            self.apply_stylesheet_jobs()

    def get_user(self, username):
        try:
            return self.r.get_redditor(username)

        except HTTPError as e:
            if e.response.status_code == 404:
                raise UserNotFound(username)
            elif e.response.status_code in [502, 503, 504]:
                return get_user(username)
            else:
                raise e

    def do_reset(self):
        self.subreddit.reset_usernotes()
        self.subreddit.reset_timeouts()

        self.message.reply('TeaBot reset successfully')

    def do_spam(self, arguements):
        user = self.get_user(self.message, arguments[0])
        spam_thread = self.r.submit('spam', 'overview for ' + user.name, url=user._url)
        self.message.reply('User [**' + user.name + '**](' + user._url + ') has been flagged in /r/spam [here](' + spam_thread.permalink + ').\n\nIf the account is still up after a few minutes you may need to [contact the admins](http://reddit.com/self.message/compose?subject=Spam%20-%20/u/' + user.name + '&to=/r/reddit.com).')

    def do_shadowban(self, arguments):
        user = self.get_user(self.message, arguments[0])

        if len(arguments) > 1:
            reason = ' '.join(arguments[1:])
        else:
            reason = 'SB&'

        n = puni.Note(user.name, reason, self.message.author.name, 'm,' + self.message.id, 'botban')
        self.subreddit.un.add_note(n)

        print(user.name + ' pending shadowban')

        self.automod_jobs.append(['shadowban', user.name])

    def do_ban(self, arguments):
        user = self.get_user(arguments[0])

        if len(arguments) > 1:
            reason = ' '.join(arguments[1:])
        else:
            reason = 'B&'

        if len(arguments) > 0:
            self.subreddit.praw.add_ban(user.name)

            n = puni.Note(user.name, reason, self.message.author, 'm,' + self.message.id, 'permban')
            self.subreddit.un.add_note(n)

            if reason == '':
                self.message.reply('User [**' + user.name + '**](' + user._url + ') has been banned')
            else:
                self.message.reply('User [**' + user.name + '**](' + user._url + ') has been banned with the note: *' + reason + '*')

        else:
            self.message.reply('**Syntax Error**:\n\n    !Ban username')

    def do_lock(self, arguments, comment):
        if len(comment_line) >= 2:
            try:
                locked_thread = praw.objects.Submission.from_url(self.r, permalink)
            except Exception as e:
                self.message.reply('**Error:**\n\nMalformed URL: ' + arguments[0] + '\n\nAcceptable format: http://www.reddit.com/r/' + self.subreddit.praw.display_name + '/comments/linkid/')
                print('Malformed URL for thread lock: ' + arguments[0])

                raise CommandSyntaxError('Malformed thread URL')

            locked_thread.set_flair('Locked')

            if comment_matches != None:
                new_comment = locked_thread.add_comment(comment)
                new_comment.distinguish()

                self.message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
            else:
                self.message.reply('[**' + locked_thread.title + '**](' + locked_thread.permalink + ') has been locked.\n\nPlease post a comment explaining why it has been locked.')
                
                self.stylesheet_jobs.append(['lock_sticky', new_comment.id])

            print('Locked ' + thread_id)

        else:
            self.message.reply('**Syntax Error**:\n\n    !lock threadURL')
            raise CommandSyntaxError('No thread URL provided')

    def do_sticky(self, arguments):
        if len(arguments) >= 2:
            try:
                comment_matches = re.search(self.comment_finder, self.message.body)

                if comment_matches != None:
                    body_text = comment_matches.groups(0)[0]
                    url_matches = re.search(self.url_verifier, arguments[1])

                    if url_matches == None:
                        title = ' '.join(arguments[1:])

                        stickied_thread = self.r.submit(self.subreddit.praw, title, text=body_text)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        self.message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\n')

                        print('Successfully stickied thread: ' + title)

                    else:
                        permalink = url_matches.groups(0)[0]

                        stickied_thread = praw.objects.Submission.from_url(self.r, permalink)
                        stickied_thread.set_flair('Official Thread')
                        stickied_thread.sticky()

                        new_comment = stickied_thread.add_comment(comment_matches.groups(0)[0])
                        new_comment.distinguish()

                        self.message.reply('[**' + stickied_thread.title + '**](' + stickied_thread.permalink + ') has been stickied.\n\nTo view the comment automatically made in the thread [click here](' + new_comment.permalink + ').')
                        
                        print('Successfully stickied thread: ' + stickied_thread.title)

                else:
                    self.message.reply('You must provide text for the sumission. The format for a sticky is:\n\n    !sticky title|link\n    ---\n    Post Body\n    ---')

            except Exception as e:
                print('Error while sticky-ing thread: ' + str(e))

        else:
            self.message.reply('**Syntax Error**:\n\n    !sticky title|link\n    ---\n    Post Body\n    ---')

    def apply_automod_jobs(self):
        if (time.time() - self.subreddit.cache_timeout['automoderator_wiki']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - self.subreddit.cache_timeout['automoderator_wiki']))
        
        self.subreddit.cache_timeout['automoderator_wiki'] = time.time()

        automod_config = self.r.get_wiki_page(self.subreddit.praw, 'config/automoderator')
        new_content = unescape(automod_config.content_md)

        for x in range(len(automod_jobs)):
            if automod_jobs[x][0] == 'shadowban':
                new_content = new_content.replace('"do_not_remove"', '"do_not_remove", "' + automod_jobs[x][1] + '"')

        try:
            if len(automod_jobs) == 1:
                if automod_jobs[0][0] == 'shadowban':
                    reason = self.message.author.name + ': Shadowbanning ' + automod_jobs[0][1]
                    self.message.reply('User [**' + automod_jobs[0][1] + '**](http://reddit.com/user/' + automod_jobs[0][1] + ') has been shadowbanned.')
            else:
                reason = self.message.author.name + ': Multiple reasons'

            try:
                self.r.edit_wiki_page(self.subreddit.praw, 'config/automoderator', new_content, reason)
            
            except HTTPError as e:
                if e.response.status_code == 415:
                    j = json.loads(g.response._content.decode('utf-8'))

                    if j['reason'] == 'SPECIAL_ERRORS':
                        reason = j['special_errors']
                        self.message.reply('AutoModerator threw the following error:\n\n' + reason)

            print('Updated AutoModerator wiki page')

        except Exception as e:
            print('Error while updating AutoModerator wiki page: ' + str(e))

    def apply_stylesheet_jobs(self):
        if (time.time() - self.subreddit.cache_timeout['stylesheet']) < self.r.config.cache_timeout + 1:
            time.sleep(int(time.time() - self.subreddit.cache_timeout['stylesheet']))

        self.subreddit.cache_timeout['stylesheet'] = time.time()

        stylesheet = self.r.get_stylesheet(self.subreddit.praw)
        new_content = unescape(stylesheet['stylesheet'])

        for x in range(len(stylesheet_jobs)):
            if stylesheet_jobs[x][0] == 'lock_sticky':
                new_content = new_content.replace('.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,', '.comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere,\n.comments-page .sitetable.nestedlisting>.thing.id-t1_' + stylesheet_jobs[x][1] + ',')
        
        try:
            self.r.set_stylesheet(self.subreddit.praw, new_content)
            print('Updated stylesheet for stickied lock reason')
        except Exception as e:
            print('Error while updating stylesheet: ' + str(e))