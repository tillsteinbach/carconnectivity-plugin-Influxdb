
# CarConnectivity Plugin for InfluxDB Config Options
The configuration for CarConnectivity is a .json file.
## General format
The general format is a `carConnectivity` section, followed by a list of connectors and plugins.
In the `carConnectivity` section you can set the global `log_level`.
Each connector or plugin needs a `type` attribute and a `config` section.
The `type` and config options specific to your connector or plugin can be found on their respective project page.
```json
{
    "carConnectivity": {
        "log_level": "error", // set the global log level, you can set individual log levels in the connectors and plugins
        "connectors": [
            {
                "type": "skoda", // Definition for a MySkoda account
                "config": {
                    "interval": 600, // Interval in which the server is checked in seconds
                    "username": "test@test.de", // Username of your MySkoda Account
                    "password": "testpassword123" // Password of your MySkoda Account
                }
            },
            {
                "type": "volkswagen", // Definition for a Volkswagen account
                "config": {
                    "interval": 300, // Interval in which the server is checked in seconds
                    "username": "test@test.de", // Username of your Volkswagen Account
                    "password": "testpassword123" // Username of your Volkswagen Account
                }
            }
        ],
        "plugins": [
            {
                "type": "influxdb", // Minimal definition for the InfluxDB Connection
                "config": {
                    "url": "http://localhost:8086", // URL of the InfluxDB server
                    "token": "your-influxdb-token", // InfluxDB API token
                    "org": "your-org", // InfluxDB organisation name
                    "bucket": "your-bucket" // InfluxDB bucket to write data into
                }
            }
        ]
    }
}
```
### InfluxDB Plugin Options
These are the valid options for the InfluxDB plugin
```json
{
    "carConnectivity": {
        "connectors": [],
        "plugins": [
            {
                "type": "influxdb", // Definition for the InfluxDB plugin
                "disabled": false, // You can disable plugins without removing them from the config completely
                "config": {
                    "log_level": "error", // The log level for the plugin. Otherwise uses the global log level
                    "url": "http://localhost:8086", // URL of the InfluxDB server
                    "token": "your-influxdb-token", // InfluxDB API token for authentication
                    "org": "your-org", // InfluxDB organisation name
                    "bucket": "your-bucket", // InfluxDB bucket to write data into
                    "measurement": "carconnectivity", // InfluxDB measurement name
                    "tag_filter_regex": "carconnectivity\\.0\\./garage/WVWAB312[0-9A-Z]+/.*", // Regex to exclude matching attribute paths
                    "only_write_changes": false // If true, only write data when the value actually changes; by default every update is written
                }
            }
        ]
    }
}
```

### Connector Options
Valid Options for connectors can be found here:
* [CarConnectivity-connector-skoda Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-skoda/tree/main/doc/Config.md)
* [CarConnectivity-connector-volkswagen Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-volkswagen/tree/main/doc/Config.md)
* [CarConnectivity-connector-seatcupra Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-seatcupra/tree/main/doc/Config.md)
* [CarConnectivity-connector-tronity Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-tronity/tree/main/doc/Config.md)
