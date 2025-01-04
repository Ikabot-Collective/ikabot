# allertLowWine update

How to use it:

First you need to downdload the file ".py" on the machine you are running ikabot.
Using the option existing in ikabot to add custom module you add the path to the python file to ikabot. 
After that you can use the module 

Wine Transfer Automation Module

This module automates the management and transfer of wine resources between cities in the Ikariam game. It ensures that cities do not run out of wine by alerting the user and initiating resource transfers when necessary.

Features

Wine Consumption Monitoring
Monitors wine consumption per hour in all cities.
Alerts the user when wine will run out within a specified number of hours.

Automatic Wine Transfers
Automatically identifies donor cities with surplus wine and transfers wine to cities in need.
Utilizes optimal routes to ensure efficient resource transportation.
Integration with Fleet Management
Detects ongoing wine transport missions to prevent duplicate transfers.
Supports multiple transfers and manages ship availability dynamically.
Telegram Notifications
Sends alerts about low wine levels and successful transfers.
Includes detailed information about routes and transport status.

Setup

Requirements

Python 3.7+

Ikabot dependencies (as per your Ikabot installation)

Copy the module into your Ikabot custom modules directory.
Ensure your Ikabot instance is configured for Telegram notifications.
Configuration
Edit the module parameters as needed for your game settings, such as the default transfer amount and the threshold for alerts.

Usage

Run the module using Ikabot's interface or command line.
Follow the prompts to configure the alert threshold and automatic transfer settings.
Monitor your Telegram for notifications and alerts.

How It Works
The module iterates over all cities to:

Check wine consumption and available stock.
Calculate the time until depletion.
If a city is identified as running low on wine:
Searches for wine-producing cities with surplus wine.
Creates transfer routes using the executeRoutes function.
The executeRoutes function handles:
Dividing resources across multiple shipments if required.
Waiting for ships to become available if none are free.
Notifications are sent via Telegram to report:
Low wine levels.
Successful transfers and routes executed.

Example Telegram Output

pid:xxxxx
In city_name, the wine will run out in 14D 16H
Automatically sent xxxx wine from Doner_City_Name to Citi_Name.
Routes executed: [(Doner_City_Name -> City_Name, xxxx wine)]

Future Enhancements
Add support for other resource types.
Optimize route planning based on distance and ship availability.
Improve user interaction via a graphical interface.

Contributing
Contributions are welcome! Please fork the repository and submit a pull request with your improvements.