"""Module implements the plugin to write CarConnectivity data into an InfluxDB."""
from __future__ import annotations
from typing import TYPE_CHECKING

import threading
import logging
import re
from datetime import datetime, timezone
from enum import Enum

from influxdb_client import InfluxDBClient, HealthCheck
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.domain.write_precision import WritePrecision

from carconnectivity.errors import ConfigurationError
from carconnectivity.util import config_remove_credentials
from carconnectivity.observable import Observable
from carconnectivity import attributes
from carconnectivity.enums import ConnectionState
from carconnectivity.attributes import EnumAttribute

from carconnectivity_plugins.base.plugin import BasePlugin
from carconnectivity_plugins.influxdb._version import __version__

if TYPE_CHECKING:
    from typing import Any, Dict, Optional
    from re import Pattern
    from carconnectivity.carconnectivity import CarConnectivity

LOG: logging.Logger = logging.getLogger("carconnectivity.plugins.influxdb")


class Plugin(BasePlugin):  # pylint: disable=too-many-instance-attributes
    """
    Plugin class for InfluxDB connectivity.

    Listens for CarConnectivity attribute updates and writes them as data points
    into an InfluxDB v2 instance using the influxdb-client library.

    Args:
        plugin_id (str): Unique identifier for this plugin instance.
        car_connectivity (CarConnectivity): An instance of CarConnectivity.
        config (Dict): Configuration dictionary containing connection details.
    """
    # pylint: disable-next=too-many-branches, too-many-statements
    def __init__(self, plugin_id: str, car_connectivity: CarConnectivity, config: Dict, *args, initialization: Optional[Dict] = None, **kwargs) -> None:
        BasePlugin.__init__(self, plugin_id=plugin_id, car_connectivity=car_connectivity, config=config, log=LOG, *args, initialization=initialization,
                            **kwargs)

        self.connection_state: EnumAttribute[ConnectionState] = EnumAttribute(name="connection_state", parent=self, value_type=ConnectionState,
                                                                              value=ConnectionState.DISCONNECTED, tags={'plugin_custom'})

        self._stop_event = threading.Event()
        self._influxdb_client: Optional[InfluxDBClient] = None
        self._write_api = None

        LOG.info("Loading influxdb plugin with config %s", config_remove_credentials(config))

        if 'url' not in config or not config['url']:
            raise ConfigurationError('No InfluxDB URL specified in config ("url" missing)')
        self.active_config['url'] = config['url']

        if 'auth_basic' in config and config['auth_basic'] is not None:
            self.active_config['auth_basic'] = config['auth_basic']
        else:
            self.active_config['auth_basic'] = False

        if 'token' not in config or not config['token']:
            if not self.active_config['auth_basic']:
                raise ConfigurationError('No InfluxDB token specified in config ("token" missing)')
            self.active_config['token'] = None
        else:
            self.active_config['token'] = config['token']

        if 'org' in config and config['org']:
            self.active_config['org'] = config['org']
        else:
            self.active_config['org'] = 'carconnectivity'

        if 'bucket' in config and config['bucket']:
            self.active_config['bucket'] = config['bucket']
        else:
            self.active_config['bucket'] = 'carconnectivity'

        if 'measurement' in config and config['measurement']:
            self.active_config['measurement'] = config['measurement']
        else:
            self.active_config['measurement'] = 'carconnectivity'

        if 'tag_filter_regex' in config and config['tag_filter_regex'] is not None:
            try:
                self.active_config['tag_filter_regex'] = re.compile(config['tag_filter_regex'])
            except re.error as err:
                raise ConfigurationError(f'Invalid tag_filter_regex specified in config: {str(err)}') from err
        else:
            self.active_config['tag_filter_regex'] = None

        if 'only_write_changes' in config and config['only_write_changes'] is not None:
            self.active_config['only_write_changes'] = config['only_write_changes']
        else:
            self.active_config['only_write_changes'] = False

        if 'verify_ssl' in config and config['verify_ssl'] is not None:
            self.active_config['verify_ssl'] = config['verify_ssl']
        else:
            self.active_config['verify_ssl'] = None

        if 'ssl_ca_cert' in config and config['ssl_ca_cert']:
            self.active_config['ssl_ca_cert'] = config['ssl_ca_cert']
        else:
            self.active_config['ssl_ca_cert'] = None

        if 'cert' in config and config['cert']:
            cert = config['cert']
            if isinstance(cert, list):
                self.active_config['cert'] = tuple(cert)
            else:
                self.active_config['cert'] = cert
        else:
            self.active_config['cert'] = None

        if 'proxy' in config and config['proxy']:
            self.active_config['proxy'] = config['proxy']
        else:
            self.active_config['proxy'] = None

        if 'username' in config and config['username']:
            if not self.active_config['auth_basic']:
                raise ConfigurationError('Username specified in config but auth_basic is not enabled')
            self.active_config['username'] = config['username']
        else:
            self.active_config['username'] = None

        if 'password' in config and config['password']:
            if not self.active_config['auth_basic']:
                raise ConfigurationError('Password specified in config but auth_basic is not enabled')
            self.active_config['password'] = config['password']
        else:
            self.active_config['password'] = None

    def startup(self) -> None:
        LOG.info("Starting InfluxDB plugin")
        self._stop_event.clear()

        influxdb_kwargs: Dict[str, Any] = {
            'url': self.active_config['url'],
            'org': self.active_config['org'],
        }
        if self.active_config['token'] is not None:
            influxdb_kwargs['token'] = self.active_config['token']
        if self.active_config['verify_ssl'] is not None:
            influxdb_kwargs['verify_ssl'] = self.active_config['verify_ssl']
        if self.active_config['ssl_ca_cert'] is not None:
            influxdb_kwargs['ssl_ca_cert'] = self.active_config['ssl_ca_cert']
        if self.active_config['cert'] is not None:
            influxdb_kwargs['cert'] = self.active_config['cert']
        if self.active_config['proxy'] is not None:
            influxdb_kwargs['proxy'] = self.active_config['proxy']
        if self.active_config['auth_basic']:
            influxdb_kwargs['auth_basic'] = self.active_config['auth_basic']
        if self.active_config['username'] is not None:
            influxdb_kwargs['username'] = self.active_config['username']
        if self.active_config['password'] is not None:
            influxdb_kwargs['password'] = self.active_config['password']

        self._influxdb_client = InfluxDBClient(**influxdb_kwargs)
        self._write_api = self._influxdb_client.write_api(write_options=SYNCHRONOUS)

        # Register observer for carconnectivity events.
        # By default write on every update; when only_write_changes is set, write only on VALUE_CHANGED.
        if self.active_config['only_write_changes']:
            observer_flags: Observable.ObserverEvent = (Observable.ObserverEvent.VALUE_CHANGED
                                                        | Observable.ObserverEvent.ENABLED
                                                        | Observable.ObserverEvent.DISABLED)
        else:
            observer_flags = (Observable.ObserverEvent.UPDATED
                              | Observable.ObserverEvent.ENABLED
                              | Observable.ObserverEvent.DISABLED)
        self.car_connectivity.add_observer(self._on_carconnectivity_event, observer_flags, priority=Observable.ObserverPriority.USER_MID)

        health: HealthCheck = self._influxdb_client.health()  # Test connection to InfluxDB
        if health.status != 'pass':
            LOG.error('InfluxDB health check failed: %s', health.message)
            self.healthy._set_value(value=False)  # pylint: disable=protected-access
            self.connection_state._set_value(value=ConnectionState.DISCONNECTED)  # pylint: disable=protected-access
        else:
            self.connection_state._set_value(value=ConnectionState.CONNECTED)  # pylint: disable=protected-access
            self.healthy._set_value(value=True)  # pylint: disable=protected-access

        health_check_thread = threading.Thread(target=self._health_check_loop, daemon=True)
        health_check_thread.start()
        LOG.debug("Starting InfluxDB plugin done")

    def _health_check_loop(self) -> None:
        """Background thread that periodically checks InfluxDB health."""
        while not self._stop_event.is_set():
            try:
                if self._influxdb_client is not None:
                    health: HealthCheck = self._influxdb_client.health()
                    is_healthy = health.status == 'pass'
                    was_healthy = self.healthy.value
                    self.healthy._set_value(value=is_healthy)  # pylint: disable=protected-access
                    if is_healthy:
                        self.connection_state._set_value(value=ConnectionState.CONNECTED)  # pylint: disable=protected-access
                    else:
                        self.connection_state._set_value(value=ConnectionState.DISCONNECTED)  # pylint: disable=protected-access
                    if is_healthy and not was_healthy:
                        LOG.info('InfluxDB connection restored')
                    elif not is_healthy and was_healthy:
                        LOG.warning('InfluxDB connection lost: %s', health.message)
            except Exception as err:  # pylint: disable=broad-except
                LOG.error('Error during InfluxDB health check: %s', err)
                if self.healthy.value:
                    self.healthy._set_value(value=False)  # pylint: disable=protected-access
                    self.connection_state._set_value(value=ConnectionState.DISCONNECTED)  # pylint: disable=protected-access
            self._stop_event.wait(60)

    def _on_carconnectivity_event(self, element, flags) -> None:
        """
        Callback for car connectivity events.

        By default writes a data point on every update. When only_write_changes is set,
        only writes on VALUE_CHANGED events.

        Args:
            element (Observable): The element that triggered the event.
            flags (Observable.ObserverEvent): The event flags.

        Returns:
            None
        """
        if not isinstance(element, attributes.GenericAttribute):
            return

        if not self.healthy.value:
            return

        # Only write data points for value events, not enable/disable events
        if not ((flags & Observable.ObserverEvent.VALUE_CHANGED) or (flags & Observable.ObserverEvent.UPDATED)):
            return

        if not element.enabled:
            return

        path: str = element.get_absolute_path()

        # Apply tag filter regex if configured
        tag_filter_regex: Optional[Pattern] = self.active_config['tag_filter_regex']
        if tag_filter_regex is not None and tag_filter_regex.search(path):
            LOG.debug('Filtered out %s by tag_filter_regex', path)
            return

        value = element.value
        if value is None:
            return

        converted_value = self._convert_value(value)
        if converted_value is None:
            return

        # Determine the timestamp: prefer last_updated, fall back to now
        if element.last_updated is not None:
            record_time: datetime = element.last_updated
            if record_time.tzinfo is None:
                record_time = record_time.replace(tzinfo=timezone.utc)
        else:
            record_time = datetime.now(tz=timezone.utc)

        # Build tags from the path segments
        path_parts = [p for p in path.strip('/').split('/') if p]
        tags: Dict[str, str] = {}
        if len(path_parts) > 1:
            tags['path'] = '/'.join(path_parts[:-1])
        field_name: str = path_parts[-1] if path_parts else 'value'

        record = {
            "measurement": self.active_config['measurement'],
            "tags": tags,
            "fields": {field_name: converted_value},
            "time": record_time,
        }

        try:
            self._write_api.write(
                bucket=self.active_config['bucket'],
                org=self.active_config['org'],
                record=record,
                write_precision=WritePrecision.MS,
            )
            LOG.debug('Written data point for %s: %s=%s', path, field_name, converted_value)
            if not self.healthy.value:
                self.healthy._set_value(value=True)  # pylint: disable=protected-access
        except Exception as err:  # pylint: disable=broad-except
            LOG.error('Failed to write data point for %s to InfluxDB: %s', path, err)
            self.healthy._set_value(value=False)  # pylint: disable=protected-access

    def _convert_value(self, value) -> Optional[bool | int | float | str]:  # pylint: disable=too-many-return-statements
        """
        Convert a carconnectivity attribute value to a type that InfluxDB can store.

        InfluxDB supports int, float, str, and bool field values.

        Args:
            value: The value to convert.

        Returns:
            The converted value as bool, int, float, or str, or None if the value cannot be converted.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            return value
        if isinstance(value, str):
            return value
        if isinstance(value, Enum):
            return str(value.value)
        if isinstance(value, datetime):
            return str(value.isoformat())
        if isinstance(value, list):
            return ', '.join([str(item.value) if isinstance(item, Enum) else str(item) for item in value])
        if isinstance(value, dict):
            return ', '.join([f'{key}: {item.value if isinstance(item, Enum) else item}' for key, item in value.items()])
        return str(value)

    def shutdown(self) -> None:
        """
        Shuts down the plugin by removing the observer and closing the InfluxDB client.
        """
        self._stop_event.set()
        self.car_connectivity.remove_observer(self._on_carconnectivity_event)
        self.connection_state._set_value(value=ConnectionState.DISCONNECTED)  # pylint: disable=protected-access
        if self._write_api is not None:
            self._write_api.close()
            self._write_api = None
        if self._influxdb_client is not None:
            self._influxdb_client.close()
            self._influxdb_client = None
        return super().shutdown()

    def get_version(self) -> str:
        return __version__

    def get_features(self) -> dict[str, tuple[bool, str]]:
        return {}

    def get_type(self) -> str:
        return "carconnectivity-plugin-influxdb"

    def get_name(self) -> str:
        return "InfluxDB Plugin"
