ExplainLikeImFiveBot
====================

Bot that reads and executes commands from modmail. Some manual configuration in AM wiki and Stylesheet required.

Does not accept mod invites - you must create your own instance at this time.

###Setup

In the teaBot.cfg file you first need to enter your bot's credentials, and then the subreddit(s) you want it to monitor. More than one subreddit can be added by seperating each subreddit name with a comma.

    [teaBot credentials]
    username=mybot
    password=mypassword

    [General]
    version=0.8.0
    subreddits=subreddit1,subreddit2,subreddit3
    useragent=LittleTeaBot/%(version)s by teaearlgraycold
    
Python-wise you should only need:

* Python 2.7
* PRAW

Just run the `main.py` file.
    
The bot must be a moderator on each subreddit it is added to, and must be given at least `mail` and `wiki` to shadowban, but should also be given `config`, `posts`, and `flair` if you want it to be able to lock and sticky threads. `access` would also be necessary if you want to use the !ban command.

To prevent issues with parsing and re-building the AutoModerator wiki page (/wiki/automoderator), TeaBot just uses a simply find-replace method to add shadowbans and locks to the wiki page. In order to allow for this add `do_not_remove` to your list of shadowbans (no quotation marks, please).

For thread locking add `do_not_touch` to the list of locked IDs. You'll also want a CSS class named "Locked" in order to show the thread locking flair to users.

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

To use a command just type it on the beginning of any line in modmail.

For example:

>**from&nbsp;\<moderator>&nbsp;via&nbsp;/r/<subreddit>&nbsp;sent&nbsp;5&nbsp;minutes&nbsp;ago**

>This /u/creesch guy is literally the worst. Brand new account just trolling the hell out of everyone

---

>**to&nbsp;\<moderator>&nbsp;via&nbsp;/r/<subreddit>&nbsp;sent&nbsp;2&nbsp;minutes&nbsp;ago**

>No problem, TeaBot's got dis

>!shadowban creesch trolling super hard

---

>**from&nbsp;TeaBot&nbsp;via&nbsp;/r/<subreddit>&nbsp;sent&nbsp;2&nbsp;minutes&nbsp;ago**

>User **[creesch](http://reddit.com/user/creesch)** has been shadowbanned for *trolling super hard*

Arguments listed in tags <> are mandatory, arguments listed in brackets [] are optional

####Shadowban

    !shadowban <username> [reason]

This will:

1. Edit the AutoModerator config to include a shadowban for the given username
2. Update the AutoModerator config via PM to AM
3. Add a usernote to the user that states the given reason (if any) for the shadowban and links that note to the modmail discussion where the user was shadowbanned.

####Summary

    !summary <username>

This will read through a users past few pages of history and return up to 20 results for comments and submissions, sorted in ascending order by score. It will also include the usernotes associated with the username.

####Lock

    !lock <permalink>

    ---

    Lock note

    ---

or

    !lock <permalink>

Spacing is important!

This will:

1. Lock the thread via AutoModerator's config page
2. Update the AutoModerator configuration
3. Flair the provided permalink as locked
4. (Optional) Post a distinguished top level comment with the lock note provided. If no note is provided the user will be prompted to provide their own lock notice

####Sticky

    !sticky <title or permalink>

    ---

    Post body/note

    ---

or

    !sticky <permalink>

This will sticky an existing post or create a new sticky thread (un-stickying the existing one).
