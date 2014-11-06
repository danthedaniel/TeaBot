import time    #Allows the program to use the sleep() command
import re      #Allows the program to use Regular Expressions
import praw    #A wrapper for the reddit API. Provides all of the reddit-related methods
import json

import sys     #Used solely for sys.exit()
import logging #Used for error reporting/debugging

import urllib  #Used to encode strings for use in URLs
from HTMLParser import HTMLParser

import bot     #Stores bot config

cache_timouts = {'modmail': 0, 'inbox': 0, 'automoderator_wiki': 0, 'usernotes_wiki': 0}

#Subreddit parameter is required to check for moderators
def check_pms(subreddit):
	global cache_timouts

	parser = HTMLParser()

	if (time.time() - cache_timouts['inbox']) > bot.r.config.cache_timeout + 1:
		cache_timouts['inbox'] = time.time()

		for message in bot.r.get_unread(limit=None):		
			#Perform checks on top level message			
			if message.new == True:
				message.mark_as_read()

				if str(message.author) == 'AutoModerator':
					unesc_body = parser.unescape(message.body)

					bot.r.send_message('/r/' + str(subreddit), 'AutoModerator Response', unesc_body)

				elif message.author in subreddit.get_moderators():
					message_commands(message, subreddit, False)

def check_modmail(subreddit):
	global cache_timouts

	parser = HTMLParser()

	sub_prefix = re.compile(ur'^[\[\()]?eli[5f]\s?[:-\]\)]?\s?', re.IGNORECASE)
	report_check = re.compile(ur'report', re.IGNORECASE)

	if (time.time() - cache_timouts['modmail']) > bot.r.config.cache_timeout + 1:
		cache_timouts['modmail'] = time.time()

		for modmail in subreddit.get_mod_mail(limit=6):		
			#Perform checks on top level modmail			
			if modmail.new == True:
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
					message_commands(modmail, subreddit, True)

			#Perform checks on modmail replies
			for reply in modmail.replies:
				if reply.new == True:
					reply.mark_as_read()

					if reply.distinguished == 'moderator':
						message_commands(reply, subreddit, True)

def message_commands(message, subreddit, ban=False):
	global cache_timouts

	parser = HTMLParser()

	update_automod = False
	wiki_additions = ''

	command_finder = re.compile(ur'^!([^\s].*)$', re.MULTILINE)
	matches = re.findall(command_finder, message.body)

	for group in matches:
		command = group.split(' ')

		if ban:
			if command[0].lower() == 'shadowban':
				try:
					wiki_additions += ', ' + command[1]

					reason = ' '.join(command[2:])

					if len(command) == 2:
						message.reply('User **' + command[1] + '** has been shadowbanned.')
						update_automod = True
					else:
						message.reply('User **' + command[1] + '** has been shadowbanned for *' + reason + '*.')
						update_automod = True

					print('[' + eval(bot.ts) + '] ' + command[1] + ' pending shadowban')
				except:
					logging.info('[' + eval(bot.ts) + '] Error while responding to shadowban command for ' + command[1])

			elif command[0].lower() == 'ban':
				if len(command) == 2:
					try:
						user = bot.r.get_redditor(command[1])
						subreddit.add_ban(user)

						message.reply('User **' + command[1] + '** has been banned')
					except Exception,e:
						print('[' + eval(bot.ts) + '] Error while banning ' + command[1] + ': ' + str(e))
						logging.info('[' + eval(bot.ts) + '] Error while banning ' + command[1] + ': ' + str(e))
				else:
					message.reply('**Syntax Error**:\n\n    !Ban username')

		elif ban == False:
			print('[' + eval(bot.ts) + '] ' + str(message.author) + ' attempted to shadowban/ban when disallowed')
			logging.info('[' + eval(bot.ts) + '] ' + str(message.author) + ' attempted to shadowban/ban when disallowed')
			bot.r.send_message('/r/' + str(subreddit), 'Illegal Action', str(message.author) + ' has attempted to shadowban/ban via PM')

		elif command[0].lower() == 'summary':
			if len(command) == 2:
				try:
					if (time.time() - cache_timouts['usernotes_wiki']) < bot.r.config.cache_timeout + 1:
						time.sleep(int(time.time() - cache_timouts['usernotes_wiki']) + 1)
					
					cache_timouts['usernotes_wiki'] = time.time()

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

					content = []

					try: #Shadowban/whitelist check
						if (time.time() - cache_timouts['automoderator_wiki']) < bot.r.config.cache_timeout + 1:
							time.sleep(int(time.time() - cache_timouts['automoderator_wiki']) + 1)
						
						cache_timouts['automoderator_wiki'] = time.time()

						automod_config = bot.r.get_wiki_page(subreddit, 'automoderator')
						unesc_wiki = parser.unescape(automod_config.content_md)

						wiki_lines = unesc_wiki.split('\n')

						shadowban_line = wiki_lines.index('    #$ELI5BOT$ SHADOWBANS') + 1
						shadowbans = wiki_lines[shadowban_line]

						user_pattern = re.compile(ur'([-_A-Za-z0-9]{3,20})[,\]]')
						usernames = re.findall(user_pattern, shadowbans)

						if lower(command[1]) in [x.lower() for x in usernames]:
							bot_reply += '**Shadowbanned**: True\n\n'
						else:
							bot_reply += '**Shadowbanned**: False\n\n'

						whitelist_line = wiki_lines.index('    #$ELI5BOT$ WHITELIST') + 2
						whitelists = wiki_lines[shadowban_line]

						usernames = re.findall(user_pattern, whitelists)

						if lower(command[1]) in [x.lower() for x in usernames]:
							bot_reply += '**Troll Whitelisted**: True\n\n'
						else:
							bot_reply += '**Troll Whitelisted**: False\n\n'

					except ValueError:
						print('[' + eval(bot.ts) + '] Malformed AutoMod wiki')
						logging.info('[' + eval(bot.ts) + '] Malformed AutoMod wiki (shadowbans/whitelist)')

					try: #Comments and submissions
						user = bot.r.get_redditor(command[1])

						for comment in user.get_comments(limit=100):
							if comment.subreddit == subreddit:
								content.append(comment)

							if len(content) > 30:
								break

						for submitted in user.get_submitted(limit=20):
							if submitted.subreddit == subreddit:
								content.append(submitted)						

						content.sort(key=lambda x: x.score, reverse=False)

						#Cut down to bottom 10 content
						while len(content) > 12:
							del content[12]

						bot_reply += '\n\n[**User Page**](http://reddit.com/user/' + command[1] + ')\n\n'

						bot_reply += 'Link | Body/Title | Score\n---|---|----\n'

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
									bot_reply += '[Comment](' + content_object.permalink + ') | ' + temp_comment + ' | ' + str(content_object.score) + '\n'
								else:
									bot_reply += '[**Comment**](' + content_object.permalink + ') | ' + temp_comment + ' | ' + str(content_object.score) + '\n'

							if type(content_object) == praw.objects.Submission:
								if content_object.banned_by == None:
									bot_reply += '[Submission](' + content_object.permalink + ') | ' + content_object.title + ' | ' + str(content_object.score) + '\n'
								else:
									bot_reply += '[**Submission**](' + content_object.permalink + ') | ' + content_object.title + ' | ' + str(content_object.score) + '\n'

					except:
						logging.info('[' + eval(bot.ts) + '] Error while trying to read user comments')

					message.reply(bot_reply)
					print('[' + eval(bot.ts) + '] Summary on ' + command[1] + ' provided')

				except Exception,e:
					message.reply('**Error**:\n\nError while providing summary')
					logging.info('[' + eval(bot.ts) + '] Error while trying to give summary on ' + command[1] + ': ' + str(e))

			else:
				message.reply('**Syntax Error**:\n\n    !Summary username')

		else:
			message.reply('**Unknown Command:**\n\n    !' + command[0])

		#End of command parsing

	if update_automod: #If necessary apply all recent changes to automoderator configuration page
		try:
			if (time.time() - cache_timouts['automoderator_wiki']) < bot.r.config.cache_timeout + 1:
				time.sleep(int(time.time() - cache_timouts['automoderator_wiki']) + 1)
			
			cache_timouts['automoderator_wiki'] = time.time()

			automod_config = bot.r.get_wiki_page(subreddit, 'automoderator')
			unesc_wiki = parser.unescape(automod_config.content_md)
			new_content = unesc_wiki.replace('do_not_remove', 'do_not_remove' + wiki_additions)

			bot.r.edit_wiki_page(subreddit, 'automoderator', new_content, str(message.author) + ': Shadowbanning ' + wiki_additions[2:])

			bot.r.send_message('AutoModerator', subreddit.display_name, 'update')

			print('[' + eval(bot.ts) + '] Updated AutoModerator wiki page')
		except Exception,e:
			logging.info('[' + eval(bot.ts) + '] Error while updating AutoModerator wiki page: ' + str(e))
			print('[' + eval(bot.ts) + '] Error while updating AutoModerator wiki page: ' + str(e))

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
		subreddit = bot.r.get_subreddit(bot.subreddit)
		
		logging.info('[' + eval(bot.ts) + '] Successfully obtained subreddit information for ' + bot.subreddit)
		print('[' + eval(bot.ts) + '] Connected to ' + bot.subreddit)
	except:
		logging.info('[' + eval(bot.ts) + '] Error while obtaining subreddit information for ' + bot.subreddit)
		sys.exit('Subreddit info fetch error')
	
	while True:
		try:
			check_modmail(subreddit)
		except Exception,e:
			logging.info('[' + eval(bot.ts) + '] Error in modmail section: ' + str(e))
			print('[' + eval(bot.ts) + '] Error in modmail section: ' + str(e))

		try:
			check_pms(subreddit)
		except Exception,e:
			logging.info('[' + eval(bot.ts) + '] Error in PM section: ' + str(e))
			print('[' + eval(bot.ts) + '] Error in PM section: ' + str(e))

		time.sleep(1)

	
if __name__ == '__main__':
	main()
