import praw

username = ''
password = ''

modteam = ''
modteampw = ''

version = 'v0.7.3'
subreddit = ''
useragent = 'LittleTeaBot for ' + subreddit + '/' + version + ' by teaearlgraycold'

r = praw.Reddit(user_agent=useragent)
