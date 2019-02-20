# sumologic-netskope-collector
Solution to pull data from Netskope to Sumo Logic




## Installation

1. Getting a token from Netskope portal
    * Login to Netskope as the Tenant Admin. Netskope REST APIs use an auth token to make authorized calls to the API. The token can be obtained from the UI by following the below steps
    * Go to the API portion of the Netskope UI ( Settings > Tools > Rest API)
    * Copy the existing token to your clipboard Alternatively, you can generate a new token and copy that

2. Add a Hosted Collector and HTTP Source
    * To create a new Sumo Logic Hosted Collector, perform the steps in [Configure a Hosted Collector](https://help.sumologic.com/03Send-Data/Hosted-Collectors/Configure-a-Hosted-Collector).
    *  Add an  [HTTP Logs and Metrics Source](https://help.sumologic.com/03Send-Data/Sources/02Sources-for-Hosted-Collectors/HTTP-Source).
      Under Advanced you'll see options regarding timestamps and time zones and when you select Timestamp parsing specify the custom time stamp format as shown below:
      Format: epoch
      Timestamp locator:  `\"timestamp\": (.*),`

3. Configuring the sumologic-netskope collector
    Below instructions assume pip is already installed if not then, see the pip [docs](https://pip.pypa.io/en/stable/installing/) on how to download and install pip.


    *sumologic-netskope-collector* is compatible with python 3.7 and python 2.7. It has been tested on ubuntu 18.04 LTS and Debian 4.9.130.
    Login to a Linux machine and download and follow the below steps:

    * Install the collector using below command
      ``` pip install sumologic-netskope-collector```

    * Create a configuration file netskope.yaml in home directory using the sample.yaml file(in sumologic-netskope folder).
      Add the SUMO_ENDPOINT and TOKEN parameters obtained from step 1 and step 2 and replacing the "netskope domain" variable with your Netskope portal domain.

      ```
      SumoLogic:
        SUMO_ENDPOINT: <SUMO LOGIC HTTP URL>


      Netskope:
        TOKEN: <NETSKOPE API TOKEN>
        NETSKOPE_EVENT_ENDPOINT: <netskope domain>/api/v1/events
        NETSKOPE_ALERT_ENDPOINT: <netskope domain>/api/v1/alerts


      ```
    * Create a cron job  for running the collector every 5 minutes by using the crontab -e and adding the below line

        `*/5 * * * *  sumonetskopecollector   /dev/null 2>&1`



