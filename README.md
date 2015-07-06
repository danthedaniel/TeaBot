TeaBot
====================

Bot that reads and executes commands from modmail. Some manual configuration in AM wiki and Stylesheet required.

Does not accept mod invites - you must create your own instance at this time.

###Setup

In the teaBot.cfg file you first need to enter your bot's credentials, and then the subreddit(s) you want it to monitor. More than one subreddit can be added by seperating each subreddit name with a comma.

    [teaBot credentials]
    username=mybot
    password=mypassword

    [General]
    version=0.9.2
    subreddits=subreddit1,subreddit2,subreddit3
    useragent=LittleTeaBot/%(version)s by teaearlgraycold
    
Python-wise you should only need:

* Python 3.X
* PRAW

Just run the `main.py` file.
    
The bot must be a moderator on each subreddit it monitors, and must be given at least `mail` and `wiki` to shadowban, but should also be given `config`, `posts`, and `flair` if you want it to be able to lock and sticky threads. `access` would also be necessary if you want to use the !ban command.

To prevent issues with parsing and re-building the AutoModerator wiki page (/wiki/automoderator), TeaBot just uses a simply find-replace method to add shadowbans and locks to the wiki page. In order to allow for this add `"do_not_remove"` to your list of shadowbans (no quotation marks, please).

For thread locking you'll want a CSS class named "Locked" in order to show the thread locking flair to users.

For comment sticking in locked threads you will need to add this CSS code to your stylesheet:

    /*CSS3 sticky comments by /u/creesch */
    .comments-page .sitetable.nestedlisting {
        display: -webkit-flex;
        display: -ms-flexbox;
        display: flex;
        -webkit-flex-direction: column;
        -ms-flex-direction: column;
        flex-direction: column;
        -webkit-flex-wrap: nowrap;
        -ms-flex-wrap: nowrap;
        flex-wrap: nowrap;    
    }

    .comments-page .sitetable.nestedlisting>.thing.id-t1_addcommentidhere
    {
        -webkit-order: -1;
        -ms-flex-order: -1;
        order: -1;
        border: dotted 1px green !important;
        background-color: #C2E8B3;
    }

###Command Reference

https://www.reddit.com/r/teaearlgraycold/wiki/teabot
