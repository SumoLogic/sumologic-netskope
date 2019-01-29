# sumologic-netskope
Solution to pull data from Netskope to Sumo Logic


sudo apt install python3-pip

pip3 install -r ../requirements.txt

## Installation 

* Getting a token from Netskope portal
    * Login to Netskope as the Tenant Admin. Netskope REST APIs use an auth token to make authorized calls to the API. The token can be obtained from the UI by following the below steps
    * Go to the API portion of the Netskope UI ( Settings > Tools > Rest API)
    * Copy the existing token to your clipboard Alternatively, you can generate a new token and copy that

* Setting up the Sumologic Collector
    * Configure a Hosted Collector 
      Under Advanced you'll see options regarding timestamps and time zones and when you select Timestamp parsing specify the custom time stamp format as shown below: 
      Format: epoch 
      Timestamp locator:  `\"timestamp\": (.*),`
* Configuring the sumologic-netskope collector

    *sumologic-netskope-collector* is compatible with python 3.7 and python 2.7. It has been tested on ubuntu 18.04 LTS and Debian 4.9.130.
    Login to a Linux machine and download and follow the below steps:
        
    * Unzip the zip file provided by Sumo logic using the following command
          `unzip sumologic-netskope.zip`
    * Go to the sumologic-netskope folder and install the dependencies. The command below assumes pip is already installed in your machine.
        `pip install -r requirements.txt`
    * Create a configuration file netskope.yaml in home directory using the sample.yaml file(in sumologic-netskope folder). 
      Add the SUMO_ENDPOINT and TOKEN parameters obtained from step 1 and step 2
      
      ```
      SumoLogic:
        SUMO_ENDPOINT: <SUMO LOGIC HTTP URL>
        
      Netskope:
        TOKEN: <NETSKOPE API TOKEN>

      ```
    * Create a cron job  for running the collector every 5 minutes by using the crontab -e and adding the below line
        
        `*/5 * * * * /usr/bin/python3 <path to sumologic-netskope folder>/sumologic-netskope-collector/netskope.py   /dev/null 2>&1`



