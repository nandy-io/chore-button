"""
Main module for daemon
"""

import os
import time
import json
import redis
import requests

import klotio

class Daemon(object):
    """
    Main class for daemon
    """

    def __init__(self):

        self.sleep = float(os.environ['SLEEP'])

        self.redis = redis.Redis(host=os.environ['REDIS_HOST'], port=int(os.environ['REDIS_PORT']))
        self.channel = os.environ['REDIS_CHANNEL']

        self.chore_api = os.environ['CHORE_API']

        self.pubsub = None

        self.logger = klotio.logger("nandy-io-chore-button-daemon")

        self.logger.debug("init", extra={
            "init": {
                "sleep": self.sleep,
                "redis": {
                    "connection": str(self.redis),
                    "channel": self.channel
                },
                "chore_api": self.chore_api
            }
        })

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

        self.logger.debug("get_message", extra={"get_message": message})

        if not message or not isinstance(message.get("data"), (str, bytes)):
            return

        data = json.loads(message['data'])

        self.logger.info("data", extra={"data": data})

        if data["type"] == "rising" and data.get("node"):
            for routine in requests.get(f"{self.chore_api}/routine?status=opened").json()["routines"]:
                if data["node"] == self.node(routine):
                    self.logger.info("next")
                    requests.patch(f"{self.chore_api}/routine/{routine['id']}/next").raise_for_status()

    def run(self):
        """
        Runs the daemon
        """

        self.subscribe()

        while True:
            self.process()
            time.sleep(self.sleep)
