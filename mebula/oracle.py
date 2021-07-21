# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import contextlib
import datetime
import functools
import ipaddress
import random
import string
import unittest.mock
from collections import defaultdict
from typing import Dict, List

try:
    import oci  # type: ignore
except ImportError:
    raise ImportError(
        "The mebula 'oracle' module requires the pip package ``mebula[oracle]``"
    )


class OracleState:
    def __init__(self):
        self.instances: Dict[str, List[oci.core.models.Instance]] = defaultdict(list)
        self.vnic_attachments: List[oci.core.models.VnicAttachment] = []
        self.vnics: List[oci.core.models.Vnic] = []


def oracle_arg_check(f):
    """
    A decorator which calls a mocked version of an OCI function to use
    it to check the arguments passed.
    """

    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        getattr(args[0].client, f.__name__)(unittest.mock.Mock(), *args[1:], **kwargs)
        return f(*args, **kwargs)

    return wrapper


class OracleComputeClient:
    """
    A mocked version of oci.core.ComputeClient
    """

    def __init__(self, config: dict, state: OracleState, **kwargs):
        self._state = state
        self.client = oci.core.compute_client.ComputeClient

    @oracle_arg_check
    def list_instances(self, compartment_id: str, **kwargs) -> oci.response.Response:
        ins = self._state.instances[compartment_id]
        filters = {"availability_domain", "display_name", "lifecycle_state"}
        for f in filters:
            if f in kwargs:
                ins = [i for i in ins if getattr(i, f) == kwargs[f]]

        if "sort_by" in kwargs:
            if "sort_order" in kwargs:
                reverse = kwargs["sort_order"] == "DESC"
            else:
                reverse = None
            if kwargs["sort_by"] == "TIMECREATED":
                reverse = reverse if reverse is not None else True
                ins = sorted(ins, key=lambda i: i.time_created, reverse=reverse)
            elif kwargs["sort_by"] == "DISPLAYNAME":
                reverse = reverse if reverse is not None else False
                ins = sorted(ins, key=lambda i: i.display_name, reverse=reverse)

        return oci.response.Response(200, None, ins, None)

    @oracle_arg_check
    def launch_instance(
        self, launch_instance_details: oci.core.models.LaunchInstanceDetails, **kwargs
    ):
        instance = oci.core.models.Instance(
            id="ocid1.instance.oc1.."
            + "".join(random.choices(string.ascii_lowercase, k=10)),
            compartment_id=launch_instance_details.compartment_id,
            availability_domain=launch_instance_details.availability_domain,
            display_name=launch_instance_details.display_name,
            freeform_tags=launch_instance_details.freeform_tags,
            lifecycle_state="RUNNING",
            time_created=datetime.datetime.now(),
        )
        self._state.instances[launch_instance_details.compartment_id].append(instance)

        # For now we'll make a single static network and grab IPs from it
        # In future this should come from a VPC and subnet
        fake_network = ipaddress.IPv4Network("10.0.0.0/24")
        ip = ipaddress.IPv4Address(
            random.randrange(
                int(fake_network.network_address + 1),
                int(fake_network.broadcast_address - 1),
            ),
        )
        vnic = oci.core.models.Vnic(
            compartment_id=launch_instance_details.compartment_id,
            id="ocid1.vnic.oc1.."
            + "".join(random.choices(string.ascii_lowercase, k=10)),
            private_ip=str(ip),
        )

        self._state.vnics.append(vnic)

        vnic_attachment = oci.core.models.VnicAttachment(
            compartment_id=launch_instance_details.compartment_id,
            instance_id=instance.id,
            vnic_id=vnic.id,
        )

        self._state.vnic_attachments.append(vnic_attachment)

    @oracle_arg_check
    def list_vnic_attachments(self, compartment_id: str, **kwargs):
        attachments = [
            a
            for a in self._state.vnic_attachments
            if a.compartment_id == compartment_id
            and a.instance_id == kwargs["instance_id"]
        ]
        return oci.response.Response(200, None, attachments, None)

    @oracle_arg_check
    def list_shapes(self, compartment_id: str, **kwargs):
        shapes = [
            {
                "baseline_ocpu_utilizations": None,
                "gpu_description": "NVIDIA\u00ae Tesla\u00ae P100",
                "gpus": 1,
                "is_live_migration_supported": False,
                "local_disk_description": None,
                "local_disks": 0,
                "local_disks_total_size_in_gbs": None,
                "max_vnic_attachment_options": None,
                "max_vnic_attachments": 12,
                "memory_in_gbs": 72.0,
                "memory_options": None,
                "min_total_baseline_ocpus_required": None,
                "networking_bandwidth_in_gbps": 8.0,
                "networking_bandwidth_options": None,
                "ocpu_options": None,
                "ocpus": 12.0,
                "processor_description": "2.0 GHz Intel\u00ae Xeon\u00ae Platinum 8167M (Skylake)",
                "shape": "VM.GPU2.1",
            },
        ]
        shapes = [oci.core.models.Shape(**s) for s in shapes]
        return oci.response.Response(200, None, shapes, None)


class OracleVirtualNetworkClient:
    """
    A mocked version of oci.core.VirtualNetworkClient
    """

    def __init__(self, config: dict, state: OracleState, **kwargs):
        self._state = state
        self.client = oci.core.virtual_network_client.VirtualNetworkClient

    @oracle_arg_check
    def get_vnic(self, vnic_id: str, **kwargs):
        vnics = [v for v in self._state.vnics if v.id == vnic_id]
        return oci.response.Response(200, None, vnics[0], None)


@contextlib.contextmanager
def mock_oracle():
    state = OracleState()
    with unittest.mock.patch(
        "oci.core.ComputeClient",
        new=functools.partial(OracleComputeClient, state=state),
    ), unittest.mock.patch(
        "oci.core.VirtualNetworkClient",
        new=functools.partial(OracleVirtualNetworkClient, state=state),
    ):
        yield
