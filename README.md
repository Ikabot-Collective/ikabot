## ikabot ~ Ikariam Bot

_Ikabot is a program written in python that grants iqual and even more functionality than a premium account in ikariam, without spending ambrosia!_

### Features

0. Exit

	Closes the main menu, returning to the normal console. You can also use `ctrl-c`. When closing _ikabot_, all the actions that you configured will continue running in the background. You can list them with `ps aux | grep ikabot`.

1. Construction list

	The user selects a building, the number of levels to upload, _ikabot_ calculates if it has enough resources and uploads the selected number of levels. If you don't have enough resources, it can send them automatically from the cities that you specify.
	
2. Send resources
 
	It sends unlimited amount of resources from one city to another. It doesn't matter how many boats you have, _ikabot_ will send all the trips that were necessary. The destination city can be own by the user or by other.

3. Distribute resource

	It sends whatever resource you choose from the cities that produce it to cities that do not. The same amount is sent to all cities, unless a city has little free storage space. (Very useful to send wine)

4. Account status

	It shows information such as levels of the buildings, time until the wine runs out, resources among other things from all the cities.
	
5. Donate

	It allows you to donate (WOW!).
	
6. Search for new spaces

	This functionality alerts by telegram, if a city disappears or if someone founds in any of the islands where the user has at least one city.
	
7. Login daily

	For those who do not want to spend a day without their account login.
	
8. Alert attacks

	It alerts by telegram if you are going to be attacked.

9. Donate automatically

	It enters once a day and donateS all the available wood from all cities to the luxury good or the forest.

10. Alert wine running out

	It warns you by Telegram when less than N hours are needed for a city to run out of wine. The number of hours is specified by the user.

11. Buy resources

	It allows you to choose what type of resource to buy and how much. It automatically purchases the different offers from the cheapest to the most expensive.

12. Activate Vacation Mode

	Sets the account in vacation mode and closes _ikabot_.

13. Activate miracle

	It allows you to activate any miracle you have available.

14. Train troops

	It allows you to easily create large amounts of troops in one city. If there are not enough resources to train all of them, it will train all the troops it can and when it finishes it will try to train the rest. It also allows you to build your army in multiple small steps so that you can use it as fast as possible.

14. Update Ikabot

	It tells you how to update _ikabot_
	

When you set an action in _ikabot_, you can enter and play ikariam without any problems. The only drawback that you may have is that the session expires, this is normal and if it happens just re-enter.

### Install

```
sudo python3 -m pip install ikabot
```
with the `ikabot` command you access the main menu.

### Uninstall

```
sudo python3 -m pip uninstall ikabot
```
### Requirements

In order to install and use _ikabot_, python3 and pip must be installed. It must be run on **Linux**, it does not work on **Windows**.

#### - Python 3
It is probably installed by default in your system.

To check if it is installed by default, just run `python3 --version`.

If it is not installed, visit the [official website](https://www.python.org/) 

#### - Pip
It is a tool to install python packages.

To check if it is installed by default, just run `python3 -m pip -V`.

To install it, you must download the _get-pip.py_ file from [this page](https://pip.pypa.io/en/stable/installing/) and run `python3 get-pip.py`.

Or just excecute:
```
curl https://bootstrap.pypa.io/get-pip.py
sudo python3 get-pip.py
rm get-pip.py
```

### Telegram

Some features (such as alerting attacks) are communicated to you via Telegram messages.

This messages are only visible for you.

Setting this up is highly recommended, since it allows you to enjoy all the functionality of _ikabot_.

To configure this, you just need to enter two pieces of information:

1) The token of the bot you are going to use

	If you want to use the 'official' bot of _ikabot_, enter Telegram and search with the magnifying glass @DaHackerBot, talk to it and you will see that a /start is sent. Once this is done you can close Telegram.
	
	Then, when _ikabot_ asks you to enter the bot's token, use the following: `409993506: AAFwjxfazzx6ZqYusbmDJiARBTl_Zyb_Ue4`.
	
	If you want to use your own bot, you can create it with the following instructions: https://core.telegram.org/bots.

2) Your chat_id

	This identifier is unique to each Telegram user and you can get it by talking by telegram to @get_id_bot (the one with the bow in the photo).

When you want to use a functionality that requires Telegram, such as _Alert attacks_, _ikabot_ will ask you for the bot's token and your chat_id. Once entered, they will be saved in a file and will not be asked again.

**If you are concerned about privacy, set up your own bot, so that nobody has the bot's token**

### Advanced

If there is an ikabot process that we identified with `ps aux | grep ikabot`, we can get a description of what it does with `kill -SIGUSR1 <pid>`. The description will arrive via Telegram.

### Windows

_Ikabot_ does not work in Windows, although in the future it might work in the Ubuntu bash of Windows 10.
