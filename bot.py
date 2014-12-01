import praw

username = ''
password = ''

modteam = ''
modteampw = ''

version = 'v0.7.4'
subreddit = ''
useragent = 'LittleTeaBot for ' + subreddit + '/' + version + ' by teaearlgraycold'

ts = 'time.ctime(int(time.time()))'

r = praw.Reddit(user_agent=useragent)
