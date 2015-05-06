import re
import praw

def compress_url(link):
    comments = re.compile(r'/comments/([A-Za-z\d]{6})/[^\s]+/([A-Za-z\d]{7})?')
    messages = re.compile(r'/message/messages/([A-Za-z\d]{6})')
    
    matches = re.findall(comments, link)
    
    if len(matches) == 0:
        matches = re.findall(messages, link)
        
        if len(matches) == 0:
            return ''
        else:
            return 'm,' + matches[0]
    else:
        if matches[0][1] == '':
            return 'l,' + matches[0][0]
        else:
            return 'l,' + matches[0][0] + ',' + matches[0][1]

def expand_url(note, subreddit):
    if note.link == '':
        return None
    else:
        parts = self.note.split(',')
        
        if parts[0] == 'm':
            return 'https://reddit.com/message/messages/' + parts[1]
        if parts[0] == 'l':
            if len(parts) > 2:
                return 'https://reddit.com/r/' + subreddit.display_name + '/comments/' + parts[1] + '/-/' + parts[2]
            else:
                return 'https://reddit.com/r/' + subreddit.display_name + '/comments/' + parts[1]
        else:
            return None