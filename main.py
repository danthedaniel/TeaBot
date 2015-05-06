import time
import traceback

import teaBot

def main():
    config = open('teaBot.cfg', 'r')
    bot = teaBot.TeaBot(config)
    
    while True:
        try:
            bot.check_modmail()
        except Exception as e:
            print(traceback.format_exc())
            print('Error in modmail section: ' + str(e))

        try:
            bot.check_pms()
        except Exception as e:
            print(traceback.format_exc())
            print('Error in PM section: ' + str(e))

        time.sleep(0.5)
    
if __name__ == '__main__':
    main()