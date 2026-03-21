# carconnectivity-plugin-Influxdb

CarConnectivity plugin for writing data into an InfluxDB.

## Configuration

Add the following to your `carconnectivity.json` configuration file:

```json
{
    "carConnectivity": {
        "plugins": [
            {
                "type": "influxdb",
                "config": {
                    "url": "http://localhost:8086",
                    "token": "your-influxdb-token",
                    "org": "your-org",
                    "bucket": "your-bucket"
                }
            }
        ]
    }
}
```

### Config Parameters

| Parameter | Required | Default | Description |
|-----------|----------|---------|-------------|
| `url` | Yes | - | URL of the InfluxDB server (e.g. `http://localhost:8086`) |
| `token` | Yes | - | InfluxDB API token for authentication |
| `org` | Yes | - | InfluxDB organisation name |
| `bucket` | Yes | - | InfluxDB bucket to write data into |
| `measurement` | No | `carconnectivity` | InfluxDB measurement name |
| `tag_filter_regex` | No | `None` | Regular expression to filter which attributes are written. Attributes whose path matches this regex will be excluded from being written to InfluxDB. |
| `only_write_changes` | No | `false` | If `true`, only write data when the value actually changes (VALUE_CHANGED); by default every update is written |
| `log_level` | No | `ERROR` | Log level for the plugin (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

## Installation

```bash
pip install carconnectivity-plugin-influxdb
```