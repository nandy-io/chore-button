"""
Main module for daemon
"""

import os
import time
import json
import redis
import requests
import traceback

class Daemon(object):
    """
    Main class for daemon
    """

    def __init__(self):

        self.sleep = float(os.environ['SLEEP'])

        self.redis = redis.StrictRedis(host=os.environ['REDIS_HOST'], port=int(os.environ['REDIS_PORT']))
        self.channel = os.environ['REDIS_CHANNEL']

        self.chore = f"{os.environ['CHORE_API']}/routine"

        self.pubsub = None

    def subscribe(self):
        """
        Subscribes to the channel on Redis
        """

        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(self.channel) 

    def process(self):
        """
        Processes a message from the channel if later than the daemons start time
        """

        message = self.pubsub.get_message()

        if not message or not isinstance(message["data"], str):
            return

        data = json.loads(message['data'])

        if data["type"] == "rising" and data.get("node"):
            for routine in requests.get(f"{self.chore}?status=opened").json()["routines"]:
                if "button" in routine["data"] and data["node"] == routine["data"]["button"].get("node"):
                    requests.patch(f"{self.chore}/{routine['id']}/next").raise_for_status()

    def run(self):
        """
        Runs the daemon
        """

        self.subscribe()

        while True:
            try:
                self.process()
                time.sleep(self.sleep)
            except Exception as exception:
                print(str(exception))
                print(traceback.format_exc())
