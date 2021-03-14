
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

	This functionality alerts by telegram, if a city disappears or if someone founds in any of the islands where the user has at least one city
	or any user defined island or set of islands.
	
7. Login daily

	For those who do not want to spend a day without their account login. This feature also collects the ambrosia fountain if it is available.
	
8. Alert attacks

	It alerts by Telegram if you are going to be attacked. You can configure how often _ikabot_ checks for incoming attacks.

9. Donate automatically

	_Ikabot_ enters once a day and donates a percentage of the available wood from the selected cities to the luxury good or the forest.

10. Alert wine running out

	It warns you by Telegram when less than N hours are needed for a city to run out of wine. The number of hours is specified by the user.

11. Buy resources

	It allows you to choose what type of resource to buy and how much. It automatically purchases the different offers from the cheapest to the most expensive.
	
12. Sell resources

	It allows you to choose what type of resource to sell and how much. It does not matter how much storage you have, it automatically updates the offers as pĺayers buy from you. When it sells all the resources, it lets you know via Telegram.

13. Activate Vacation Mode

	Sets the account in vacation mode and closes _ikabot_.

14. Activate miracle

	It allows you to activate any miracle you have available as many times in a row as you want.

15. Train army

	It allows you to easily create large amounts of troops or fleets in one city. If there are not enough resources to train all of them, it will train all the units it can and when it finishes it will try to train the rest. It also allows you to build your army in multiple small steps so that you can use it as fast as possible.
	
16. See movements

	Let's you see movements coming to/from your cities. This includes attacks, transports, etc.

17. Construct building

	It allows you to contruct a building (WOW!, again).

18. Update Ikabot

	It tells you how to update _ikabot_

19. Import / Export cookie

	You can use this feature to insert your _ikabot_ cookie into your browser or other _ikabot_ instances running on a different machine.
	This will result in _ikabot_ not logging you out of your browser Ikariam session. Keep in mind that logging into Ikariam from another browser will invalidate all prevous cookies, and you will need to do this again if that happens.

20. Auto-Pirate

	This feature will run the 'Smugglers' piracy mission as many times as you need it to. It will also attempt to automatically solve the captcha should it be presented with one.
	
21. Investigate

	It allows you to investigate an available research.
	
22. Attack barbarians

	Now you can attack the barbarians in an automated way. You can send your troops in many rounds and it will automatically collect the resources.

24. Configure Proxy

	It lets you configure a proxy that will be used to all request except those sent to the lobby (during login).
	The proxy affects immediately all processes associated with the current ikariam username.

25. Update the Telegram data

	It allows you to set or change the Telegram data.

26. Kill tasks

	It allows you to end a currently-running ikabot task

27. Configure captcha resolver

	It allows you to configure your desired captcha resolver for the Auto-pirate task. The options you have to choose from are:

	1. Default 
	2. Custom
	3. 9kw.eu
	4. Telegram


### Discord
Join us in discord at:`https://discord.gg/3hyxPRj`

### Install

#### Pre-built Windows binary

You can use the pre-built _ikabot_ binary for Windows in the ikabot.zip file for a certain version [here](https://github.com/physics-sp/ikabot/releases)!

#### Using pip

```
python3 -m pip install --user ikabot
```
In Linux, you can access the main menu with `ikabot`, use `python3 -m ikabot` in Windows.

### Requirements

In order to install and use _ikabot_, **python3** and **pip** must be installed.  
Also, in Linux you might have to install **gcc** and **python3-dev**.

#### - Python3 on Windows

To install Python3 on Windows, visit the [official website](https://www.python.org/downloads/windows/), or install it in the Windows App Store.

#### - Python3 on Unix

It is probably installed by default in your system.  
To check if it is installed by default, just run `python3 --version`.  
If it is not installed, visit the [official website](https://www.python.org/) 

### - Notice

Python version 3.9 has proven to be unstable using _ikabot_ so it is recommended you use Python 3.8 or Python 3.7. 
This notice will be removed once it is confirmed that _ikabot_ works fine on Python 3.9

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


### Pre-defined input

You can run ikabot with command line arguments to make it automatically run a task with pre-determined input.  
An example of running the login daily function with predetermined input is:  
```bash
python3 -m ikabot [email] [password] [account number] 7 0
```
Interactivity is returned to the user as soon as the list of pre-determined input arguments is exhausted, allowing _ikabot_ to be run like so:  
```bash
python3 -m ikabot [email] [password]
```
**Take into account that running _ikabot_ with pre-determined input will leave your username and password in the command line history**  
