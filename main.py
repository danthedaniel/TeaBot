import sys     #Used solely for sys.exit()
import logging
import time
import teaBot

#import traceback

def main():
    logging.basicConfig(filename='teaBot.log',level=logging.WARNING)

    #try:
    bot = teaBot.TeaBot('teaBot.cfg')
    #except Exception as e:
        #print('Fatal error while trying to initiate bot: ' + str(e))
        #sys.exit('Now exiting teaBot')
    
    while True:
        try:
            bot.check_modmail()
        except Exception as e:
            #print(traceback.format_exc())
            bot.printlog('Error in modmail section: ' + str(e))

        try:
            bot.check_pms()
        except Exception as e:
            #print(traceback.format_exc())
            bot.printlog('Error in PM section: ' + str(e))

        time.sleep(1)
    
if __name__ == '__main__':
    main()
