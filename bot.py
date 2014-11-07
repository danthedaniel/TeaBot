import praw

username = ''
password = ''
<<<<<<< HEAD
version = 'v0.5.1'
=======
version = 'v0.5.0'
>>>>>>> origin/master
subreddit = ''

ts = 'time.ctime(int(time.time()))'

r = praw.Reddit(user_agent=username + ' for ' + subreddit + '/' + version + ' by teaearlgraycold')
