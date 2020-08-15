import unittest
import unittest.mock
import klotio_unittest

import os
import json

import service


class MockRedis(object):

    def __init__(self, host, port):

        self.host = host
        self.port = port
        self.channel = None
        self.messages = []

    def pubsub(self):

        return self

    def subscribe(self, channel):

        self.channel = channel

    def get_message(self):

        return self.messages.pop(0)


class TestService(klotio_unittest.TestCase):

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_CHANNEL": "stuff",
        "CHORE_API": "http://boast.com",
        "SLEEP": "0.7"
    })
    @unittest.mock.patch("redis.Redis", klotio_unittest.MockRedis)
    @unittest.mock.patch("klotio.logger", klotio_unittest.MockLogger)
    def setUp(self):

        self.daemon = service.Daemon()

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_CHANNEL": "stuff",
        "CHORE_API": "http://boast.com",
        "SLEEP": "0.7"
    })
    @unittest.mock.patch("redis.Redis", klotio_unittest.MockRedis)
    @unittest.mock.patch("klotio.logger", klotio_unittest.MockLogger)
    def test___init___(self):

        daemon = service.Daemon()

        self.assertEqual(daemon.redis.host, "most.com")
        self.assertEqual(daemon.redis.port, 667)
        self.assertEqual(daemon.channel, "stuff")
        self.assertEqual(daemon.chore_api, "http://boast.com")
        self.assertEqual(daemon.sleep, 0.7)

        self.assertEqual(daemon.logger.name, "nandy-io-chore-button-daemon")

        self.assertLogged(daemon.logger, "debug", "init", extra={
            "init": {
                "sleep": 0.7,
                "chore_api": "http://boast.com",
                "redis": {
                    "connection": "MockRedis<host=most.com,port=667>",
                    "channel": "stuff"
                }
            }
        })

    def test_subscribe(self):

        self.daemon.subscribe()

        self.assertEqual(self.daemon.redis, self.daemon.pubsub)
        self.assertEqual(self.daemon.redis.channel, "stuff")

    @unittest.mock.patch("requests.get")
    def test_node(self, mock_get):

        mock_get.return_value.json.return_value = {
            "person": {
                "id": 1,
                "chore-button.nandy.io": {
                    "node": "dump"
                }
            }
        }

        self.assertEqual("bump", self.daemon.node({
            "person_id": 1,
            "chore-button.nandy.io": {
                "node": "bump"
            }
        }))
        mock_get.assert_not_called()

        self.assertEqual("dump", self.daemon.node({
            "person_id": 1,
            "data": {}
        }))
        mock_get.assert_has_calls([
            unittest.mock.call("http://boast.com/person/1"),
            unittest.mock.call().json()
        ])

        mock_get.return_value.json.return_value = {
            "person": {
                "id": 1,
                "data": {}
            }
        }
        self.assertIsNone(self.daemon.node({
            "person_id": 1,
            "data": {}
        }))

    @unittest.mock.patch("requests.get")
    @unittest.mock.patch("requests.patch")
    def test_process(self, mock_patch, mock_get):

        self.daemon.subscribe()

        mock_get.return_value.json.return_value = {
            "routines": [
                {
                    "id": 1,
                    "chore-button.nandy.io": {
                        "node": "bump"
                    }
                },
                {
                    "id": 2,
                    "chore-button.nandy.io": {
                        "node": "dump"
                    }
                }
            ]
        }

        self.daemon.redis.messages = [
            None,
            {"data": 1},
            {
                "data": json.dumps({
                    "type": "rising",
                    "node": "bump"
                })
            },
            {
                "data": json.dumps({
                    "type": "rising",
                    "node": "stump"
                })
            }
        ]

        self.daemon.process()
        self.daemon.process()

        self.assertLogged(self.daemon.logger, "debug", "get_message", extra={
            "get_message": {
                "data": 1
            }
        })

        self.daemon.process()
        mock_get.assert_has_calls([
            unittest.mock.call("http://boast.com/routine?status=opened"),
            unittest.mock.call().json()
        ])
        mock_patch.assert_has_calls([
            unittest.mock.call("http://boast.com/routine/1/next"),
            unittest.mock.call().raise_for_status()
        ])

        self.assertLogged(self.daemon.logger, "info", "data", extra={
            "data": {
                "type": "rising",
                "node": "bump"
            }
        })

        self.assertLogged(self.daemon.logger, "info", "next")

    @unittest.mock.patch("requests.get")
    @unittest.mock.patch("requests.patch")
    @unittest.mock.patch("service.time.sleep")
    def test_run(self, mock_sleep, mock_patch, mock_get):

        mock_get.return_value.json.return_value = {
            "routines": [
                {
                    "id": 1,
                    "chore-button.nandy.io": {
                        "node": "bump"
                    }
                }
            ]
        }

        self.daemon.redis.messages = [
            {
                "data": json.dumps({
                    "type": "rising",
                    "node": "bump"
                })
            },
            {
                "data": json.dumps({
                    "type": "rising",
                    "node": "stump"
                })
            }
        ]

        mock_sleep.side_effect = [Exception("whoops")]

        self.assertRaisesRegex(Exception, "whoops", self.daemon.run)

        self.assertEqual(self.daemon.redis, self.daemon.pubsub)
        self.assertEqual(self.daemon.redis.channel, "stuff")

        mock_patch.assert_has_calls([
            unittest.mock.call("http://boast.com/routine/1/next"),
            unittest.mock.call().raise_for_status()
        ])

        mock_sleep.assert_called_with(0.7)
