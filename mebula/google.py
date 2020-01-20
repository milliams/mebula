import collections.abc
import contextlib
import functools
import json
import unittest.mock
import urllib.request
from collections import namedtuple
from typing import Any, Dict
from urllib.parse import urlparse, parse_qs

import googleapiclient.discovery  # type: ignore
from googleapiclient.http import HttpMock  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore

from .dict_filter import filter_dicts


class GoogleState:
    def __init__(self):
        self.instances = []


@functools.lru_cache(maxsize=128)
def google_api_client(serviceName: str, version: str, *args, **kwargs):
    url = f"https://www.googleapis.com/discovery/v1/apis/{serviceName}/{version}/rest"
    data = urllib.request.urlopen(url).read().decode()
    return googleapiclient.discovery.build_from_document(data, http=HttpMock())


class GoogleComputeInstances:
    """
    A reimplementation of the Google cloud server-side for the ``instances`` resource
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
        print("inserting", body)
        return self.state.instances.append(GoogleComputeInstance(zone, body))


class GoogleComputeInstance(collections.abc.Mapping):
    """
    A dictionary version of the Instance resource
    """

    def __init__(self, zone, body):
        # Should match google_api_client("compute", "v1").instances()._schema.get("Instance")
        self.data = {}
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

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)

    def __str__(self):
        return str(self.data)


def extract_path_parameters(path: str, template: str) -> Dict[str, str]:
    parameters = {}
    for p, t in zip(path.split("/"), template.split("/")):
        if t.startswith("{") and t.endswith("}"):
            var_name = t[1:-1]
            parameters[var_name] = p
    return parameters


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

    collection_map = {"compute": {"instances": GoogleComputeInstances}}

    try:
        resource_class = collection_map[api][resource]
    except KeyError:
        raise NotImplementedError(
            f"Resource collection {api}.{resource} is not implemented"
        )

    resource_object = resource_class(state)

    try:
        resource_method = getattr(resource_object, method)
    except AttributeError:
        raise NotImplementedError(
            f"Method {api}.{resource}.{method} is not implemented"
        )
    return resource_method(**all_parameters)


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
