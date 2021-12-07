##########################################################################
# Copyright (c) 2010-2021 Robert Bosch GmbH
# This program and the accompanying materials are made available under the
# terms of the Eclipse Public License 2.0 which is available at
# http://www.eclipse.org/legal/epl-2.0.
#
# SPDX-License-Identifier: EPL-2.0
##########################################################################

"""
CAN Communication Channel using Vector hardware
***********************************************

:module: cc_vector_can

:synopsis: CChannel implementation for CAN(fd) using Vector API from python-can

.. currentmodule:: cc_vector_can

"""

import logging
from typing import Union

import can
import can.bus
import can.interfaces.vector
from can.interfaces.vector.canlib import get_channel_configs

from pykiso import CChannel, Message

log = logging.getLogger(__name__)


class CCVectorCan(CChannel):
    """CAN FD channel-adapter."""

    def __init__(
        self,
        bustype: str = "vector",
        poll_interval: float = 0.01,
        rx_queue_size: int = 524288,
        serial: int = None,
        channel: int = 3,
        bitrate: int = 500000,
        data_bitrate: int = 2000000,
        fd: bool = True,
        app_name: str = None,
        can_filters: list = None,
        is_extended_id: bool = False,
        **kwargs,
    ):
        """Initialize can channel settings.

        :param bustype: python-can interface modules used
        :param poll_interval: Poll interval in seconds.
        :param rx_queue_size: Number of messages in receive queue
        :param serial: Vector Box's serial number. Can be replaced by the
            "AUTO" flag to trigger the Vector Box automatic detection.
        :param channel: The channel indexes to create this bus with
        :param bitrate: Bitrate in bits/s.
        :param app_name: Name of application in Hardware Config.
            If set to None, the channel should be a global channel index.
        :param data_bitrate: Which bitrate to use for data phase in CAN FD.
        :param fd: If CAN-FD frames should be supported.
        :param can_filters: A iterable of dictionaries each containing
            a “can_id”, a “can_mask”, and an optional “extended” key.
        :param is_extended_id: This flag controls the size of the arbitration_id field.

        """
        super().__init__(**kwargs)
        self.bustype = bustype
        self.poll_interval = poll_interval
        self.rx_queue_size = rx_queue_size
        if str(serial).upper() == "AUTO":
            self.serial = detect_serial_number()
        else:
            self.serial = serial if not isinstance(serial, str) else int(serial)
        self.channel = channel
        self.app_name = app_name
        self.bitrate = bitrate
        self.data_bitrate = data_bitrate
        self.is_extended_id = is_extended_id
        self.fd = fd
        self.can_filters = can_filters
        self.remote_id = None
        self.bus = None

    def _cc_open(self) -> None:
        """Open a can bus channel and set filters for reception."""
        log.info(f"CAN bus channel open: {self.channel}")
        self.bus = can.interface.Bus(
            bustype=self.bustype,
            poll_interval=self.poll_interval,
            rx_queue_size=self.rx_queue_size,
            serial=self.serial,
            app_name=self.app_name,
            channel=self.channel,
            bitrate=self.bitrate,
            data_bitrate=self.data_bitrate,
            fd=self.fd,
            can_filters=self.can_filters,
        )

    def _cc_close(self) -> None:
        """Close the current can bus channel."""
        log.info(f"CAN bus channel closed: {self.channel}")
        self.bus.shutdown()
        self.bus = None

    def _cc_send(self, msg, remote_id: int = None, raw: bool = False) -> None:
        """Send a CAN message at the configured id.

        If remote_id parameter is not given take configured ones, in addition if
        raw is set to True take the msg parameter as it is otherwise parse it using
        test entity protocol format.

        :param msg: data to send
        :param remote_id: destination can id used
        :param raw: boolean use to select test entity protocol format

        """
        _data = msg

        if remote_id is None:
            remote_id = self.remote_id

        if not raw:
            _data = msg.serialize()

        can_msg = can.Message(
            arbitration_id=remote_id,
            data=_data,
            is_extended_id=self.is_extended_id,
            is_fd=self.fd,
        )
        self.bus.send(can_msg)

        log.debug(f"sent CAN Message: {can_msg}")

    def _cc_receive(
        self, timeout=0.0001, raw: bool = False
    ) -> Union[Message, bytes, None]:
        """Receive a can message using configured filters.

        If raw parameter is set to True return received message as it is (bytes)
        otherwise test entity protocol format is used and Message class type is returned.

        :param timeout: timeout applied on reception
        :param raw: boolean use to select test entity protocol format

        :return: tuple containing the received data and the source can id
        """
        try:  # Catch bus errors & rcv.data errors when no messages where received
            received_msg = self.bus.recv(timeout=timeout)

            if received_msg is not None:
                frame_id = received_msg.arbitration_id
                payload = received_msg.data

                if not raw:
                    payload = Message.parse_packet(payload)

                log.debug(f"received CAN Message: {frame_id}, {payload}")

                return payload, frame_id
            else:
                return None, None
        except BaseException:
            log.exception(f"encountered error while receiving message via {self}")
            return None, None


def detect_serial_number() -> int:
    """Provide the serial number of the currently available Vector Box to be used.

    If several Vector Boxes are detected, the one with the lowest serial number is selected.
    If no Vector Box is connected, a ConnectionRefused error is thrown.

    :return: the Vector Box serial number
    :raises ConnectionRefusedError: raised if no Vector box is currently available
    """
    # Get all channels configuration
    channel_configs = get_channel_configs()
    # Getting all serial numbers
    serial_numbers = set()
    for channel_config in channel_configs:
        serial_number = channel_config.serialNumber
        if serial_number != 0:
            serial_numbers.add(channel_config.serialNumber)
    if serial_numbers:
        # if several devices are discovered, the first Vector Box is chosen
        serial_number = min(serial_numbers)
        log.info(f"Using Vector Box with serial number {serial_number}")
        return serial_number
    else:
        raise ConnectionRefusedError("No Vector box is currently available")