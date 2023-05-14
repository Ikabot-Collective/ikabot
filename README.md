
# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="65" height="65"> Ikabot - (Ikariam Bot)
[![Downloads](https://pepy.tech/badge/ikabot)](https://pepy.tech/project/ikabot) ![stars](https://img.shields.io/github/stars/physics-sec/ikabot) ![licence](https://img.shields.io/github/license/physics-sec/ikabot)

Ikabot is a cross-platform program written in python that grants equal or even more functionality than a premium account in ikariam, without spending ambrosia!

<a href="https://discord.gg/3hyxPRj"><img src="https://img.shields.io/badge/Discord-5865F2?style=for-the-badge&logo=discord&logoColor=white"></a>

<img src="https://user-images.githubusercontent.com/54487782/236331003-001e7f1d-1a3c-43ae-a8b0-de148233af4c.png" width="50%" height="50%">

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Features

| # | Feature | Description |
|--|--|--|
| 0 | Exit | Closes the main menu, returning to the normal console. You can also use `ctrl-c`. When closing _ikabot_, all the actions that you configured will continue running in the background. If you want to see which actions are running, simply run _ikabot_ and log into the account from which you initiated those actions. You will be able to see their PIDs and will be able to kill them using `kill -9 [pid]` on Unix or using Task Manager on Windows |
| 1 | Construction list | The user selects a building, the number of levels to upload, _ikabot_ calculates if it has enough resources and uploads the selected number of levels. If you don't have enough resources, it can send them automatically from the cities that you specify. |
| 2 | Send resources |  It sends unlimited amount of resources from one city to another. It doesn't matter how many boats you have, _ikabot_ will send all the trips that were necessary. The destination city can be own by the user or by other. |
| 3 | Distribute resources | It lets you distribute the type of resource in two possible ways: from the cities that produce it to cities that do not (very useful to send wine) and to distribute it evenly among all cities. |
| 4 | Account status | It shows information such as levels of the buildings, time until the wine runs out, resources among other things from all the cities. |
| 5 | Donate | It allows you to donate (WOW!). |
| 6 | Search for new spaces | This functionality alerts by telegram, if a city disappears or if someone founds in any of the islands where the user has at least one city or any user defined island or set of islands. |
| 7 | Login Daily | For those who do not want to spend a day without their account login. This feature also collects the ambrosia fountain if it is available. |
| 8 | Alert attacks | It alerts by Telegram if you are going to be attacked. You can configure how often _ikabot_ checks for incoming attacks. |
| 9 | Donate automatically | _Ikabot_ enters once a day and donates a percentage of the available wood from the selected cities to the luxury good or the forest. |
| 10 | Alert wine running out | It warns you by Telegram when less than N hours are needed for a city to run out of wine. The number of hours is specified by the user. |
| 11 | Buy resources | It allows you to choose what type of resource to buy and how much. It automatically purchases the different offers from the cheapest to the most expensive. |
| 12 | Sell resources | It allows you to choose what type of resource to sell and how much. It does not matter how much storage you have, it automatically updates the offers as pĺayers buy from you. When it sells all the resources, it lets you know via Telegram. |
| 13 | Activate Vacation Mode | Sets the account in vacation mode and closes _ikabot_. |
| 14 | Activate miracle | It allows you to activate any miracle you have available as many times in a row as you want. |
| 15 | Train army | It allows you to easily create large amounts of troops or fleets in one city. If there are not enough resources to train all of them, it will train all the units it can and when it finishes it will try to train the rest. It also allows you to build your army in multiple small steps so that you can use it as fast as possible. |
| 16 | See movements | Let's you see movements coming to/from your cities. This includes attacks, transports, etc. |
| 17 | Construct building | It allows you to contruct a building (WOW!, again). |
| 18 | Update Ikabot | It tells you how to update _ikabot_ |
| 19 | Import / Export cookie | You can use this feature to insert your _ikabot_ cookie into your browser or other _ikabot_ instances running on a different machine. This will result in _ikabot_ not logging you out of your browser Ikariam session. Keep in mind that logging into Ikariam from another browser will invalidate all prevous cookies, and you will need to do this again if that happens. |
| 20 | Auto-Pirate | This feature will run the 'Smugglers' piracy mission as many times as you need it to. It will also attempt to automatically solve the captcha should it be presented with one. |
| 21 | Investigate | It allows you to investigate an available research. |
| 22 | Attack barbarians | Now you can attack the barbarians in an automated way. You can send your troops in many rounds and it will automatically collect the resources. |
| 24 | Configure Proxy | It lets you configure a proxy that will be used to all request except those sent to the lobby (during login). The proxy affects immediately all processes associated with the current ikariam username. |
| 25 | Update the Telegram data | It allows you to set or change the Telegram data. |
| 26 | Kill tasks | It allows you to end a currently-running ikabot task |
| 27 | Configure captcha resolver | It allows you to configure your desired captcha resolver for the Auto-pirate task. The options you have to choose from are: <ol><li>Default </li><li>Custom</li><li>9kw.eu</li><li>Telegram</li></ol> |

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Install

## Pre-built Windows binary

You can use the pre-built _ikabot_ binary for Windows in the ikabot.zip file for a certain version [here](https://github.com/physics-sp/ikabot/releases)!

## Using pip

```
python3 -m pip install --user ikabot
```
In Linux, you can access the main menu with `ikabot`, use `python3 -m ikabot` in Windows.

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Requirements

In order to install and use _ikabot_, **python3** and **pip** must be installed.  
Also, in Linux you might have to install **gcc** and **python3-dev**.

## - Python3 on Windows

To install Python3 on Windows, visit the [official website](https://www.python.org/downloads/windows/), or install it in the Windows App Store.

## - Python3 on Unix

It is probably installed by default in your system.  
To check if it is installed by default, just run `python3 --version`.  
If it is not installed, visit the [official website](https://www.python.org/) 

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Notice

## Pip
It is a tool to install python packages.  
To check if it is installed by default, just run `python3 -m pip -V`.  
To install it, you must download the _get-pip.py_ file from [this page](https://pip.pypa.io/en/stable/installing/) and run `python3 get-pip.py`.  

Or, in Linux, you can just excecute:
```
curl https://bootstrap.pypa.io/get-pip.py
sudo python3 get-pip.py
rm get-pip.py
```

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Build from sources

If you want to have the lastest features, install from sources:
```
git clone https://github.com/physics-sp/ikabot
cd ikabot
python3 -m pip install --user -e .
```
Any change you make to that directory now will be reflected once you run _ikabot_ using the command `python3 -m ikabot`

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Uninstall

```
python3 -m pip uninstall ikabot
```

# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Using docker

First, build the container
```
docker build -t <name> .
```
Then, run it using
```
docker run -it <name>
```
In order to keep the processes running, detach from the container using `CTRL-p + CTRL-q`. If you want to open the menu again, just attach to the running container. The menu wont show up again, but you can select the request number, because its still running.


# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Telegram

Some features (such as alerting attacks) are communicated to you via Telegram messages.  
Setting this up is highly recommended, since it allows you to enjoy all the functionality of _ikabot_.  
To configure this, you just need to enter the token of the Telegram bot you are going to use  

## Create your Telegram bot

You will need to create your own Telegram Bot. To do that, talk to `@BotFather` on Telegram, send `/newbot` and choose the name of your bot.  
Make sure to first talk to your new bot and type in `/start` before entering the token into _ikabot_.  
You can find more information about the bot creation process here : `https://core.telegram.org/bots#3-how-do-i-create-a-bot`

## Enter the Telegram bot's token

Once you have your new bot token, go to `Options / Settings`, then `Enter the Telegram data` and enter it.  
**Do not share this token with others!**


# <img src="https://user-images.githubusercontent.com/54487782/236309220-b257d870-6846-4740-a855-dba89deeacaf.png" width="30" height="30"> Pre-defined input

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
