
## ikabot ~ Ikariam Bot  
[![Downloads](https://pepy.tech/badge/ikabot)](https://pepy.tech/project/ikabot)

_Ikabot is a cross-platform program written in python that grants equal or even more functionality than a premium account in ikariam, without spending ambrosia!_

### Features

0. Exit

	Closes the main menu, returning to the normal console. You can also use `ctrl-c`. When closing _ikabot_, all the actions that you configured will continue running in the background. If you want to see which actions are running, simply run _ikabot_ and log into the account from which you initiated those actions. You will be able to see their PIDs and will be able to kill them using `kill -9 [pid]` on Unix or using Task Manager on Windows

1. Construction list

	The user selects a building, the number of levels to upload, _ikabot_ calculates if it has enough resources and uploads the selected number of levels. If you don't have enough resources, it can send them automatically from the cities that you specify.
	
2. Send resources
 
	It sends unlimited amount of resources from one city to another. It doesn't matter how many boats you have, _ikabot_ will send all the trips that were necessary. The destination city can be own by the user or by other.

3. Distribute resources

	It lets you distribute the type of resource in two possible ways: from the cities that produce it to cities that do not (very useful to send wine) and to distribute it evenly among all cities.
	
4. Account status

	It shows information such as levels of the buildings, time until the wine runs out, resources among other things from all the cities.
	
5. Donate

	It allows you to donate (WOW!).
	
6. Search for new spaces

	This functionality alerts by telegram, if a city disappears or if someone founds in any of the islands where the user has at least one city.
	
7. Login daily

	For those who do not want to spend a day without their account login.
	
8. Alert attacks

	It alerts by telegram if you are going to be attacked. You can configure how often _ikabot_ checks for incoming attacks.

9. Donate automatically

	_Ikabot_ enters once a day and donates ***ALL*** the available wood from ***ALL*** selected cities to the luxury good or the forest.

10. Alert wine running out

	It warns you by Telegram when less than N hours are needed for a city to run out of wine. The number of hours is specified by the user.

11. Buy resources

	It allows you to choose what type of resource to buy and how much. It automatically purchases the different offers from the cheapest to the most expensive.
	
12. Sell resources

	It allows you to choose what type of resource to sell and how much. It does not matter how much storage you have, it automatically updates the offers as pĺayers buy from you. When it sells all the resources, it let's you know via Telegram.

13. Activate Vacation Mode

	Sets the account in vacation mode and closes _ikabot_.

14. Activate miracle

	It allows you to activate any miracle you have available N times in a row.

15. Train army

	It allows you to easily create large amounts of troops or fleets in one city. If there are not enough resources to train all of them, it will train all the units it can and when it finishes it will try to train the rest. It also allows you to build your army in multiple small steps so that you can use it as fast as possible.
	

16. See movements

	Let's you see movements coming to/from your cities. This includes attacks, transports, etc.

17. Construct building

	It allows you to contruct a building (WOW!, again).

18. Update Ikabot

	It tells you how to update _ikabot_

19. Update the Telegram data

	It allows you to set or update your Telegram contact information.

When you set an action in _ikabot_, you can enter and play ikariam without any problems. The only drawback that you may have is that the session expires, this is normal and if it happens just re-enter.

### Discord
Join us in discord at:`https://discord.gg/3hyxPRj`

### Install

```
python3 -m pip install --user ikabot
```
In Linux, you can access the main menu with `ikabot`, use `python3 -m ikabot` in windows.

### Requirements

In order to install and use _ikabot_, **python3** and **pip** must be installed.  
Also, in Linux you might have to install **gcc** and **python3-dev**.

#### - Python3 on Windows

To install Python3 on Windows, visit the [official website](https://www.python.org/downloads/windows/), or install it in the Windows App Store.

#### - Python3 on Unix

It is probably installed by default in your system.  
To check if it is installed by default, just run `python3 --version`.  
If it is not installed, visit the [official website](https://www.python.org/) 

#### - Pip
It is a tool to install python packages.  
To check if it is installed by default, just run `python3 -m pip -V`.  
To install it, you must download the _get-pip.py_ file from [this page](https://pip.pypa.io/en/stable/installing/) and run `python3 get-pip.py`.  

Or, in Linux, you can just excecute:
```
curl https://bootstrap.pypa.io/get-pip.py
sudo python3 get-pip.py
rm get-pip.py
```

### Build from sources

If you want to have the lastest features, install from sources:
```
git clone https://github.com/physics-sp/ikabot
cd ikabot
python3 -m pip install --user -e .
```
Any change you make to that directory now will be reflected once you run _ikabot_ using the command `python3 -m ikabot`

### Uninstall

```
python3 -m pip uninstall ikabot
```

### Telegram

Some features (such as alerting attacks) are communicated to you via Telegram messages.  
This messages are only visible for you.  
Setting this up is highly recommended, since it allows you to enjoy all the functionality of _ikabot_.  
To configure this, you just need to enter two pieces of information:  

1) The token of the bot you are going to use

	If you want to use the 'official' bot of _ikabot_, enter Telegram and search with the magnifying glass @DaHackerBot, talk to it and you will see that a /start is sent. Once this is done you can close Telegram.
	
	Then, when _ikabot_ asks you to enter the bot's token, use the following: `409993506: AAFwjxfazzx6ZqYusbmDJiARBTl_Zyb_Ue4`.
	
	If you want to use your own bot, talk to @BotFather on Telegram and he will give you the token to a new bot once you give him the name of your new bot. Make sure to first talk to your new bot and type in /start before inserting it's token into _ikabot_.
	You can find more information about the bot creation process here : https://core.telegram.org/bots

2) Your chat_id

	This identifier is unique to each Telegram user and you can get it by talking by telegram to @get_id_bot (the one with the bow in the photo).

When you want to use a functionality that requires Telegram, such as _Alert attacks_, _ikabot_ will ask you for the bot's token and your chat_id. Once entered, they will be saved in a file and will not be asked again.

**If you are concerned about privacy, set up your own bot, so that only you have the bot's token**

#### Proxy

To make Ikabot use a proxy simply open the config.py file which is located in the ikabot directory and change the following lines:

`proxy = False` to `proxy = True`  
`https_proxy = "https://127.0.0.1:8080"` to `https_proxy = "https://{Your proxy server IP}:{Your proxy server port}"`  

Make sure that your proxy has HTTPS enabled.  

**Bare in mind that if another user is using the same proxy, you will have the same IP and you might get banned**

#### Automatization with Expect

You can use [Expect](https://en.wikipedia.org/wiki/Expect) to automate some actions on _ikabot_.  
There is an example [here](https://github.com/physics-sp/ikabot/wiki/Using-Expect-example:-distribute_wine_evenly.exp).  
In Linux, you can use cron to run it.  
**Take into account that writing your password in plaintext can be very dangerous**
