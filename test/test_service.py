import unittest
import unittest.mock

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


class TestService(unittest.TestCase):

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_CHANNEL": "stuff",
        "CHORE_API": "http://boast.com",
        "SLEEP": "0.7"
    })
    @unittest.mock.patch("redis.StrictRedis", MockRedis)
    def setUp(self):

        self.daemon = service.Daemon()

    @unittest.mock.patch.dict(os.environ, {
        "REDIS_HOST": "most.com",
        "REDIS_PORT": "667",
        "REDIS_CHANNEL": "stuff",
        "CHORE_API": "http://boast.com",
        "SLEEP": "0.7"
    })
    @unittest.mock.patch("redis.StrictRedis", MockRedis)
    def test___init___(self):

        daemon = service.Daemon()

        self.assertEqual(daemon.redis.host, "most.com")
        self.assertEqual(daemon.redis.port, 667)
        self.assertEqual(daemon.channel, "stuff")
        self.assertEqual(daemon.chore_api, "http://boast.com")
        self.assertEqual(daemon.sleep, 0.7)

    def test_subscribe(self):

        self.daemon.subscribe()

        self.assertEqual(self.daemon.redis, self.daemon.pubsub)
        self.assertEqual(self.daemon.redis.channel, "stuff")

    @unittest.mock.patch("requests.get")
    def test_process(self, mock_get):

        mock_get.return_value.json.return_value = {
            "person": {
                "id": 1,
                "data": {
                    "button": {
                        "node": "dump"
                    }
                }
            }
        }

        self.assertEqual("bump", self.daemon.node({
            "id": 1,
            "data": {
                "button": {
                    "node": "bump"
                }
            }
        }))
        mock_get.assert_not_called()

        self.assertEqual("dump", self.daemon.node({
            "id": 1,
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
            "id": 1,
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
                    "data": {
                        "button": {
                            "node": "bump"
                        }
                    }
                },
                {
                    "id": 2,
                    "data": {
                        "button": {
                            "node": "dump"
                        }
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

        self.daemon.process()
        mock_get.assert_has_calls([
            unittest.mock.call("http://boast.com/routine?status=opened"),
            unittest.mock.call().json()
        ])
        mock_patch.assert_has_calls([
            unittest.mock.call("http://boast.com/routine/1/next"),
            unittest.mock.call().raise_for_status()
        ])

    @unittest.mock.patch("requests.get")
    @unittest.mock.patch("requests.patch")
    @unittest.mock.patch("service.time.sleep")
    @unittest.mock.patch("traceback.format_exc")
    @unittest.mock.patch('builtins.print')
    def test_run(self, mock_print, mock_traceback, mock_sleep, mock_patch, mock_get):

        mock_get.return_value.json.return_value = {
            "routines": [
                {
                    "id": 1,
                    "data": {
                        "button": {
                            "node": "bump"
                        }
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

        mock_sleep.side_effect = [Exception("whoops"), Exception("adaisy")]
        mock_traceback.side_effect = ["spirograph", Exception("doh")]

        self.assertRaisesRegex(Exception, "doh", self.daemon.run)

        self.assertEqual(self.daemon.redis, self.daemon.pubsub)
        self.assertEqual(self.daemon.redis.channel, "stuff")

        mock_patch.assert_has_calls([
            unittest.mock.call("http://boast.com/routine/1/next"),
            unittest.mock.call().raise_for_status()
        ])

        mock_sleep.assert_called_with(0.7)

        mock_print.assert_has_calls([
            unittest.mock.call("whoops"),
            unittest.mock.call("spirograph"),
            unittest.mock.call("adaisy")
        ])