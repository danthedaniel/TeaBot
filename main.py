import os
import sys
import logging
import time
import teaBot
import traceback

def main():
    logging.basicConfig(filename='teaBot.log',level=logging.WARNING)

    bot = teaBot.TeaBot(os.path.join(os.path.abspath('./config/'), 'teaBot.cfg'))
    
    while True:
        try:
            bot.rounds()
            time.sleep(1)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(traceback.format_exc())
            bot.printlog('Unhandled exception: ' + str(e))

    bot.stop()
    
if __name__ == '__main__':
    main()
