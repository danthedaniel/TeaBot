import sys     #Used solely for sys.exit()
import logging
import time

import teaBot

def main():
    logging.basicConfig(filename='teaBot.log',level=logging.DEBUG)

    try:
        bot = teaBot.TeaBot('teaBot.cfg')
    except Exception,e:
        print('Fatal error while trying to initiate bot: ' + str(e))
        sys.exit('Now exiting teaBot')
    
    while True:
        try:
            bot.check_modmail()
        except Exception,e:
            bot.printlog('Error in modmail section: ' + str(e))

        try:
            bot.check_pms()
        except Exception,e:
            bot.printlog('Error in PM section: ' + str(e))

        time.sleep(1)
    
if __name__ == '__main__':
    main()
