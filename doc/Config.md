
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
                    "only_write_changes": false, // If true, only write data when the value actually changes; by default every update is written
                    "verify_ssl": true, // Set to false to disable SSL certificate verification (not recommended for production)
                    "ssl_ca_cert": "/path/to/ca-bundle.crt", // Path to a CA certificate bundle file or directory for SSL verification
                    "cert": "/path/to/client.crt", // Path to a client-side certificate file for mutual TLS; use a list ["/path/to/cert", "/path/to/key"] to specify separate cert and key files
                    "proxy": "http://proxy.example.com:8080", // Optional HTTP proxy URL
                    "auth_basic": false, // Set to true to use HTTP Basic Authentication instead of token auth (for InfluxDB 1.8 compatibility)
                    "username": "your-username", // Username for HTTP Basic Authentication (requires auth_basic: true)
                    "password": "your-password" // Password for HTTP Basic Authentication (requires auth_basic: true)
                }
            }
        ]
    }
}
```
> **Security note:** Avoid committing credentials such as `token`, `username`, or `password` directly into your config files. Consider using environment variable substitution or a secrets management solution supported by your deployment environment.

### Connector Options
Valid Options for connectors can be found here:
* [CarConnectivity-connector-skoda Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-skoda/tree/main/doc/Config.md)
* [CarConnectivity-connector-volkswagen Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-volkswagen/tree/main/doc/Config.md)
* [CarConnectivity-connector-seatcupra Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-seatcupra/tree/main/doc/Config.md)
* [CarConnectivity-connector-tronity Config Options](https://github.com/tillsteinbach/CarConnectivity-connector-tronity/tree/main/doc/Config.md)
