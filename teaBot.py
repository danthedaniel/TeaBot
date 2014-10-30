import time    #Allows the program to use the sleep() command
import re      #Allows the program to use Regular Expressions
import praw    #A wrapper for the reddit API. Provides all of the reddit-related methods
import json

import sys     #Used solely for sys.exit()
import logging #Used for error reporting/debugging

import urllib  #Used to encode strings for use in URLs
from HTMLParser import HTMLParser

import bot     #Stores bot config

cache_timouts = {'modmail': 0, 'new': 0}

def check_modmail(subreddit):
	global cache_timouts

	parser = HTMLParser()

	sub_prefix = re.compile(ur'^[\[\()]?eli[5f]\s?[:-\]\)]?\s?', re.IGNORECASE)
	report_check = re.compile(ur'report', re.IGNORECASE)

	if (time.time() - cache_timouts['modmail']) > bot.r.config.cache_timeout + 1:
		cache_timouts['modmail'] = time.time()

		for modmail in subreddit.get_mod_mail(limit=6):
			#if str(modmail.author) == 'teaearlgraycold':
				#import pdb; pdb.set_trace()
			
			#Perform checks on top level modmail			
			if modmail.new == True:
				print('[' + eval(bot.ts) + '] Found new message')
				modmail.mark_as_read()

				if report_check.search(modmail.subject) == None and sub_prefix.search(modmail.subject) != None:
					#Make certain that the text can be put into a url/markdown code safely
					unesc_subject = parser.unescape(modmail.subject)
					unesc_body = parser.unescape(modmail.body)
					
					safe_subject = urllib.quote_plus(unesc_subject.encode('utf-8'))
					safe_body = urllib.quote_plus(unesc_body.encode('utf-8'))
					
					modmail.reply('It appears that you have accidentally posted a question in modmail rather than create a new submission.\n\n[Click Here](http://www.reddit.com/r/explainlikeimfive/submit?selftext=true&title=' + safe_subject + '&text=' + safe_body +') to turn this modmail into a submission.\n\nPlease [check our rules for posting](http://reddit.com/r/explainlikeimfive/wiki/rules) while you are at it and make sure your submission is a good fit for ELI5.')
					logging.info('[' + eval(bot.ts) + '] Sent modmail to ' + str(modmail.author) + ' about accidental ELI5 thread in modmail')
					print('[' + eval(bot.ts) + '] Sent modmail to ' + str(modmail.author) + ' about accidental ELI5 thread in modmail')

				if modmail.distinguished == 'moderator':
					print('[' + eval(bot.ts) + '] Found mod message')
					modmail_commands(modmail, subreddit)

			#Perform checks on modmail replies
			for reply in modmail.replies:
				if reply.new == True:
					print('[' + eval(bot.ts) + '] Found new message')
					reply.mark_as_read()

					if reply.distinguished == 'moderator':
						print('[' + eval(bot.ts) + '] Found mod message')
						modmail_commands(reply, subreddit)

def modmail_commands(message, subreddit):
	parser = HTMLParser()

	update_automod = False
	wiki_additions = ''

	command_finder = re.compile(ur'^!(ShadowBan|Ban|Summary) ([-_A-Za-z0-9]{3,20})\s?[\'"]?(.*?)[\'"]?$', re.MULTILINE | re.IGNORECASE)
	matches = re.findall(command_finder, message.body)

	if matches != None:
		print('[' + eval(bot.ts) + '] Found matches')
		for command in matches:
			print('[' + eval(bot.ts) + '] Running command')
			if command[0].lower() == 'shadowban':
				print('[' + eval(bot.ts) + '] Found a shadowban command')
				#try:
				wiki_additions += ', ' + command[1]

				if command[2] == '':
					message.reply('User ' + command[1] + ' has been shadowbanned.')
					update_automod = True
				else:
					message.reply('User **' + command[1] + '** has been shadowbanned for *' + command[2] + '*.')
					update_automod = True

				print('[' + eval(bot.ts) + '] ' + command[1] + ' ShadowBanned')
				#except:
					#logging.info('[' + eval(bot.ts) + '] Error while responding to shadowban command for ' + command[1])

			elif command[0].lower() == 'ban':
				if command[2] == '':
					message.reply('The Ban command is not yet implemented.\n\n**Debug:**\n\n    User: ' + command[1])
				else:
					message.reply('The Ban command is not yet implemented.\n\n**Debug:**\n\n    User: ' + command[1] + '\n    Reason: ' + command [2])

			elif command[0].lower() == 'summary':
				if command[2] == '':
					#try:
					usernotes = bot.r.get_wiki_page(subreddit, 'usernotes')
					unesc_usernotes = parser.unescape(usernotes.content_md)
					json_notes = json.loads(unesc_usernotes)

					moderators = json_notes['constants']['users']
					warnings = json_notes['constants']['warnings']

					bot_reply = ''

					try: #Usernotes
						notes = json_notes['users'][command[1]]['ns']

						bot_reply += '**User Report: ' + command[1] + '**\n---\n\nWarning | Reason | Moderator\n---|---|----\n'

						for note in notes:
							bot_reply += warnings[note['w']] + ' | ' + note['n'] + ' | ' + moderators[note['m']] + '\n'
					except KeyError:
						print('[' + eval(bot.ts) + '] Could not find user ' + command[1] + ' in usernotes')

					comments = []

					#try: #Comments
					user = bot.r.get_redditor(command[1])

					for comment in user.get_comments(limit=100):
						if comment.subreddit == subreddit:
							comments.append(comment)

						if len(comments) > 30:
							break

					comments.sort(key=lambda x: x.score, reverse=False)

					#Cut down to bottom 10 comments
					while len(comments) > 10:
						del comments[10]

					bot_reply += '\n\nLink | Comment | Score\n---|---|----\n'

					for comment in comments:
						temp_comment = comment.body.replace('\n', ' ')

						#Cut down comments to 200 characters, while extending over the 200 char limit
						#to preserve markdown links
						if len(temp_comment) > 200:
							i = 200
							increment = -1

							found = False

							while i > -1 and (i + 1) < len(temp_comment):
								if temp_comment[i] == ')':
									found = True
									break

								if temp_comment[i] == '(':
									if temp_comment[i - 1] == ']':
										increment = 1
									else:
										break

								i += increment

							i += 1
							
							if i < 200 or found == False:
								i = 200

							temp_comment = temp_comment[:i]

							if (i + 1) > len(temp_comment):
								temp_comment += '...'

						bot_reply += '[Comment](' + comment.permalink + ') | ' + temp_comment + ' | ' + str(comment.score) + '\n'

					#except:
						#logging.info('[' + eval(bot.ts) + '] Error while trying to read user comments')

					message.reply(bot_reply)
					print('[' + eval(bot.ts) + '] Summary on ' + command[1] + ' provided')

					#except:
						#message.reply('**Error**:\n\nError while providing summary')
						#logging.info('[' + eval(bot.ts) + '] Error while trying to give summary on ' + command[1])

				else:
					message.reply('**Syntax Error**:\n\n    !Summary username')

			else:
				message.reply('**Unknown Command:**\n\n    !' + command[0])

			#End of command parsing

		if update_automod: #If necessary apply all recent changes to automoderator configuration page
			try:
				automod_config = bot.r.get_wiki_page(subreddit, 'automoderator')
				unesc_wiki = parser.unescape(automod_config.content_md)
				new_content = unesc_wiki.replace('do_not_remove', 'do_not_remove' + wiki_additions)

				bot.r.edit_wiki_page(subreddit, 'automoderator', new_content, str(message.author) + ': Shadowbanning ' + wiki_additions[2:])

				bot.r.send_message('AutoModerator', subreddit.display_name, 'update')

				print('[' + eval(bot.ts) + '] Updated AutoModerator wiki page')
			except:
				logging.info('[' + eval(bot.ts) + '] Error while updating AutoModerator wiki page')
				print('[' + eval(bot.ts) + '] Error while updating AutoModerator wiki page')

def main():
	logging.basicConfig(filename='teaBot.log',level=logging.DEBUG)
	
	logging.info('[' + eval(bot.ts) + '] ' + bot.username + ' ' + bot.version + ' started')
	
	try:
		#Logs into the reddit account
		bot.r.login(bot.username, bot.password)
		logging.info('[' + eval(bot.ts) + '] Successfully logged into reddit account')
		print('[' + eval(bot.ts) + '] ' + bot.username + ' for ' + bot.subreddit + '/' + bot.version + ' started')
	except:
		logging.info('[' + eval(bot.ts) + '] Error while trying to log into reddit account')
		sys.exit('Reddit login error')
	
	try:
		#Connects the bot to explainlikeimfive
		eli_five = bot.r.get_subreddit(bot.subreddit)
		
		logging.info('[' + eval(bot.ts) + '] Successfully obtained subreddit information for ' + bot.subreddit)
		print('[' + eval(bot.ts) + '] Connected to ' + bot.subreddit)
	except:
		logging.info('[' + eval(bot.ts) + '] Error while obtaining subreddit information for ' + bot.subreddit)
		sys.exit('Subreddit info fetch error')
	
	while True:
		#try:
		check_modmail(eli_five)
		#except:
			#logging.info('[' + eval(bot.ts) + '] Error in modmail section')
			#print('[' + eval(bot.ts) + '] Error caught by main while loop')

		time.sleep(1)

	
if __name__ == '__main__':
	main()
