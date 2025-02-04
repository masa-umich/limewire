import json
from datetime import datetime


class Logger:
    """A class to log latency data for each packet Limewire processes."""

    def __init__(self):
        self._log: dict[str, list[dict[str, str | float]]] = {}

    def log(self, key: str, data: dict[str, str | float]):
        """Add a piece of data to the log.

        This function adds a timestamp to `data`, then adds it
        to the list corresponding to `key` within the Logger's
        internal log.

        For example, if you call log() like this:

        ```
        logger = Logger()
        logger.log("telemetry", {"latency": 0.05})
        ```

        The internal log object will look like this:

        {
            "telemetry": [
                ...
                {
                    "latency": 0.05
                    "timestamp": "<timestamp-goes-here>",
                }
            ]
        }

        Args:
            key: The message type under which to add the log. For now,
                the only valid key is "telemetry", although this is
                not enforced within this function to support the other
                message types in the future.
            data: A dictionary containing whatever data will be logged
                under the current timestamp. This dictionary should have
                strings as keys and data as values.
        """

        data["timestamp"] = str(datetime.now())

        if key not in self._log:
            self._log[key] = []
        self._log[key].append(data)

    def write_log(self):
        """Write the log to a JSON file in the current directory."""
        filename = f"limewire_{datetime.now()}.json"
        filename = filename.replace(" ", "_").replace(":", "-")
        with open(filename, "w") as f:
            json.dump(self._log, f, indent=4)

    def get_data(self, log_key: str, data_key: str) -> list[str | float]:
        """Return data associated with a key as a list.

        For example, say the internal log object looks like this:

        {
            "telemetry": [
                ...
                {
                    "latency": 0.05
                    "timestamp": "<timestamp-goes-here>",
                }
                ...
            ]
        }

        If you call `get_data("telemetry", "latency")`, you will receive a
        list that looks like [..., 0.05, ...].
        """
        return [data[data_key] for data in self._log[log_key]]
