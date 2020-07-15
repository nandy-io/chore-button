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

        self.chore_api = os.environ['CHORE_API']

        self.pubsub = None

    def subscribe(self):
        """
        Subscribes to the channel on Redis
        """

        self.pubsub = self.redis.pubsub()
        self.pubsub.subscribe(self.channel)

    def node(self, routine):

        if "node" in routine.get("chore-button.nandy.io", {}):
            return routine["chore-button.nandy.io"]["node"]

        person = requests.get(f"{self.chore_api}/person/{routine['person_id']}").json()["person"]

        return person.get("chore-button.nandy.io", {}).get("node")

    def process(self):
        """
        Processes a message from the channel if later than the daemons start time
        """

        message = self.pubsub.get_message()

        if not message or isinstance(message["data"], int):
            return

        data = json.loads(message['data'])

        if data["type"] == "rising" and data.get("node"):
            for routine in requests.get(f"{self.chore_api}/routine?status=opened").json()["routines"]:
                if data["node"] == self.node(routine):
                    requests.patch(f"{self.chore_api}/routine/{routine['id']}/next").raise_for_status()

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
