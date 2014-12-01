import praw

username = 'Explainlikeimfivebot'
password = '!m7h30r!g!n41G'

modteam = 'ELI5_ModTeam'
modteampw = 'michaelscott1'

version = 'v0.7.4'
subreddit = 'explainlikeimfive'
useragent = 'LittleTeaBot for ' + subreddit + '/' + version + ' by teaearlgraycold'

ts = 'time.ctime(int(time.time()))'

r = praw.Reddit(user_agent=useragent)
