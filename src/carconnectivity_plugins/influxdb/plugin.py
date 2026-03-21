"""Module implements the plugin to write CarConnectivity data into an InfluxDB."""
from __future__ import annotations
from typing import TYPE_CHECKING

import threading
import logging
import re
from datetime import datetime, timezone
from enum import Enum

from influxdb_client import InfluxDBClient
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
    from typing import Dict, Optional
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

        if 'token' not in config or not config['token']:
            raise ConfigurationError('No InfluxDB token specified in config ("token" missing)')
        self.active_config['token'] = config['token']

        if 'org' not in config or not config['org']:
            raise ConfigurationError('No InfluxDB organisation specified in config ("org" missing)')
        self.active_config['org'] = config['org']

        if 'bucket' not in config or not config['bucket']:
            raise ConfigurationError('No InfluxDB bucket specified in config ("bucket" missing)')
        self.active_config['bucket'] = config['bucket']

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

    def startup(self) -> None:
        LOG.info("Starting InfluxDB plugin")
        self._stop_event.clear()

        self._influxdb_client = InfluxDBClient(
            url=self.active_config['url'],
            token=self.active_config['token'],
            org=self.active_config['org'],
        )
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

        self.connection_state._set_value(value=ConnectionState.CONNECTED)  # pylint: disable=protected-access
        self.healthy._set_value(value=True)  # pylint: disable=protected-access
        LOG.debug("Starting InfluxDB plugin done")

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

        # Determine the timestamp: prefer last_changed, fall back to now
        if element.last_changed is not None:
            record_time: datetime = element.last_changed
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
                write_precision=WritePrecision.NANOSECONDS,
            )
            LOG.debug('Written data point for %s: %s=%s', path, field_name, converted_value)
        except Exception as err:  # pylint: disable=broad-except
            LOG.error('Failed to write data point for %s to InfluxDB: %s', path, err)

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
