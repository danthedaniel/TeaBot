import praw

username = ''
password = ''
version = 'v0.4.3'
subreddit = ''

ts = 'time.ctime(int(time.time()))'

r = praw.Reddit(user_agent=username + ' for ' + subreddit + '/' + version + ' by teaearlgraycold')