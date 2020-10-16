# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import collections.abc
import contextlib
import functools
import ipaddress
import json
import random
import string
import unittest.mock
import urllib.request
from collections import namedtuple
from typing import Any, Dict
from urllib.parse import urlparse, parse_qs

try:
    import googleapiclient.discovery  # type: ignore
    from googleapiclient.http import HttpMock  # type: ignore
    from googleapiclient.errors import HttpError  # type: ignore
except ImportError:
    raise ImportError(
        "The mebula 'google' module requires the pip package ``mebula[google]``"
    )

from .dict_filter import filter_dicts


class GoogleState:
    def __init__(self):
        self.instances = []
        self.machine_types = [
            {
                "id": "3001",
                "creationTimestamp": "1969-12-31T16:00:00.000-08:00",
                "name": "n1-standard-1",
                "description": "1 vCPU, 3.75 GB RAM",
                "guestCpus": 1,
                "memoryMb": 3840,
                "imageSpaceGb": 10,
                "maximumPersistentDisks": 128,
                "maximumPersistentDisksSizeGb": "263168",
                "isSharedCpu": False,
                "kind": "compute#machineType",
            },
            {
                "id": "3002",
                "creationTimestamp": "1969-12-31T16:00:00.000-08:00",
                "name": "n1-standard-2",
                "description": "2 vCPUs, 7.5 GB RAM",
                "guestCpus": 2,
                "memoryMb": 7680,
                "imageSpaceGb": 10,
                "maximumPersistentDisks": 128,
                "maximumPersistentDisksSizeGb": "263168",
                "isSharedCpu": False,
                "kind": "compute#machineType",
            },
        ]


@functools.lru_cache(maxsize=128)
def google_api_client(serviceName: str, version: str, *args, **kwargs):
    url = f"https://www.googleapis.com/discovery/v1/apis/{serviceName}/{version}/rest"
    data = urllib.request.urlopen(url).read().decode()
    return googleapiclient.discovery.build_from_document(data, http=HttpMock())


class GoogleComputeInstances:
    """
    A reimplementation of the Google cloud server-side for the ``instances`` resource

    Should have all of google_api_client("compute", "v1").instances()._resourceDesc["methods"]
    """

    def __init__(self, state: GoogleState):
        self.state = state

    def list(self, project: str, zone: str, filter=None, alt="", body=None):
        if filter is not None:
            instances = list(filter_dicts(filter[0], self.state.instances))
        else:
            instances = self.state.instances
        return {"items": instances} if instances else {}

    def get(self, project: str, zone: str, instance: str, alt="", body=None):
        instances = [i for i in self.state.instances if i["name"] == instance]
        if instances:
            return instances[0]
        else:
            Response = namedtuple("Response", ["status", "reason"])
            reason = f"Instance {instance} not found in {project}/{zone}"
            resp = Response(status="404", reason=reason)
            raise HttpError(resp, b"{}", uri="<NotImplemented>")

    def insert(self, project: str, zone: str, body, alt=""):
        return self.state.instances.append(GoogleComputeInstance(zone, body))


class GoogleComputeInstance(collections.abc.Mapping):
    """
    A dictionary version of the Instance resource
    """

    def __init__(self, zone, body):
        # Should match google_api_client("compute", "v1").instances()._schema.get("Instance")
        self.data: Dict[str, Any] = {}
        self.data["id"] = "".join(random.choices(string.ascii_lowercase, k=10))
        self.data["name"] = body["name"]
        self.data["tags"] = body.get("tags", {})
        self.data["status"] = "RUNNING"
        self.data["scheduling"] = body.get(
            "scheduling",
            {
                "onHostMaintenance": "MIGRATE",
                "automaticRestart": True,
                "preemptible": False,
                "nodeAffinities": [],
            },
        )
        self.data["zone"] = zone

        # For now we'll make a single static network and grab IPs from it
        # In future this should come from a VPC and subnet
        fake_network = ipaddress.IPv4Network("10.0.0.0/24")
        ip = ipaddress.IPv4Address(
            random.randrange(
                int(fake_network.network_address) + 1,
                int(fake_network.broadcast_address) - 1,
            )
        )
        self.data["networkInterfaces"] = [{"networkIP": str(ip)}]

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __str__(self):
        return str(self.data)


class GoogleComputeMachineTypes:
    """
    A reimplementation of the Google cloud server-side for the ``machineTypes`` resource

    Should have all of google_api_client("compute", "v1").machineTypes()._resourceDesc["methods"]
    """

    def __init__(self, state: GoogleState):
        self.state = state

    def list(self, project: str, zone: str, filter=None, alt="", body=None):
        if filter is not None:
            machine_types = list(filter_dicts(filter[0], self.state.machine_types))
        else:
            machine_types = self.state.machine_types
        return {"items": machine_types} if machine_types else {}

    def get(self, project: str, zone: str, machineType: str, alt="", body=None):
        machine_types = [
            i for i in self.state.machine_types if i["name"] == machineType
        ]
        if machine_types:
            return machine_types[0]
        else:
            Response = namedtuple("Response", ["status", "reason"])
            reason = f"Instance {machineType} not found in {project}/{zone}"
            resp = Response(status="404", reason=reason)
            raise HttpError(resp, b"{}", uri="<NotImplemented>")


def extract_path_parameters(path: str, template: str) -> Dict[str, str]:
    """
    Args:
        path: the path that request is being sent to
        template: the schema path

    Returns: a mapping of extracted path parameters

    Examples:
        >>> extract_path_parameters("/zone/foo/thing/blah", "/zone/{zone}/thing/{thing}")
        {'zone': 'foo', 'thing': 'blah'}

    """
    parameters = {}
    for p, t in zip(path.split("/"), template.split("/")):
        if t.startswith("{") and t.endswith("}"):
            var_name = t[1:-1]
            parameters[var_name] = p
    return parameters


def get_resource_class_method(api, resource, method):
    collection_map = {
        "compute": {
            "instances": GoogleComputeInstances,
            "machineTypes": GoogleComputeMachineTypes,
        }
    }

    try:
        resource_class = collection_map[api][resource]
    except KeyError:
        raise NotImplementedError(
            f"Resource collection {api}.{resource} is not implemented"
        )

    try:
        resource_method = getattr(resource_class, method)
    except AttributeError:
        raise NotImplementedError(
            f"Method {api}.{resource}.{method} is not implemented"
        )

    return resource_class, resource_method


def google_execute(
    request: googleapiclient.http.HttpRequest, state: GoogleState
) -> dict:
    api, resource, method = request.methodId.split(".")
    url = urlparse(request.uri)
    path = url.path
    query = parse_qs(url.query)
    body = json.loads(request.body) if request.body else {}

    api_version = path.split("/")[2]  # Hacky, I know
    r = getattr(google_api_client(api, api_version), resource)()
    base_path = urlparse(r._baseUrl).path
    method_schema = r._resourceDesc["methods"][method]
    method_path = method_schema["path"]
    path_template = base_path + method_path

    path_parameters = extract_path_parameters(path, path_template)

    all_parameters: Dict[str, Any] = {**path_parameters, **query, **{"body": body}}

    resource_class, resource_method = get_resource_class_method(api, resource, method)
    resource_object = resource_class(state)
    print(request.uri)
    return resource_method(resource_object, **all_parameters)


@contextlib.contextmanager
def mock_google():
    state = GoogleState()
    with unittest.mock.patch("googleapiclient.discovery.build", new=google_api_client):
        with unittest.mock.patch.object(
            googleapiclient.http.HttpRequest,
            "execute",
            new=functools.partialmethod(google_execute, state),
        ):
            yield
