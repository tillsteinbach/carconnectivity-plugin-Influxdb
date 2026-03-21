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
                    "token": "your-influxdb-token"
                }
            }
        ]
    }
}
```

The only required parameter is `url`. The `token` is required unless `auth_basic` is set to `true`.
By default, `org` and `bucket` are set to `carconnectivity`.

For all available configuration parameters, see [Config.md](doc/Config.md).

## Installation

```bash
pip install carconnectivity-plugin-influxdb
```