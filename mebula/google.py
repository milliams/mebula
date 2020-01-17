import collections.abc
import contextlib
import functools
import json
import operator
import unittest.mock
import urllib.request
from collections import namedtuple
from typing import Any, Dict, List
from urllib.parse import urlparse, parse_qs

import googleapiclient.discovery  # type: ignore
import lark  # type: ignore
from googleapiclient.http import HttpMock  # type: ignore
from googleapiclient.errors import HttpError  # type: ignore


class GoogleState:
    def __init__(self):
        self.instances = []


@functools.lru_cache(maxsize=128)
def google_api_client(serviceName: str, version: str, *args, **kwargs):
    url = f"https://www.googleapis.com/discovery/v1/apis/{serviceName}/{version}/rest"
    data = urllib.request.urlopen(url).read().decode()
    return googleapiclient.discovery.build_from_document(data, http=HttpMock())


def parse_filter(filter_text: str) -> lark.Tree:
    """
    https://cloud.google.com/sdk/gcloud/reference/topic/filters
    """
    grammar = """
    start: _expression

    _expression: term
               | parenthesised
               | logical_binary
               | logical_unary

    logical_unary: unary_logical_operator _expression
    ?logical_binary: _expression binary_logical_operator _expression (binary_logical_operator _expression)*

    ?parenthesised: "(" _expression ")"

    unary_logical_operator: "NOT"      -> not
    binary_logical_operator: "AND"     -> and
                           | "OR"      -> or
                           | WS_INLINE -> and

    list_comparator: ":("   -> pattern
                   | "=("   -> equals
    value_comparator: ":"   -> pattern
                    | "="   -> equals
                    | "!="  -> not_equals
                    | "<"   -> less_than
                    | "<="  -> less_than_equals
                    | ">"   -> greater_than
                    | ">="  -> greater_than_equals
                    | "~"   -> matches
                    | "!~"  -> not_matches

    term: "- " key ":" "*"                                  -> not_defined
        | key ":" "*"                                       -> is_defined
        | key value_comparator value                        -> compare
        | key list_comparator value ((WS | ",") value)? ")" -> compare_list

    key: CNAME("."CNAME)*
    value: NUMBER
         | CHARACTER_SEQUENCE
         | STRING

    STRING : /[ubf]?r?("(?!"").*?(?<!\\\\)(\\\\\\\\)*?"|'(?!'').*?(?<!\\\\)(\\\\\\\\)*?')/i

    CHARACTER_SEQUENCE: (LETTER | NUMBER | "-" | "^" | ":" | "[" | "]" | "@" | "."
                      | "*" | "!" | "£" | "$" | "%" | "*" | "|" | "\\\\" | "/" | "_"
                      | "+" | "=" | "{" | "}" | ":" | ";" | "~" | "#" | "<" | ">" | "?")+

    %import common.LETTER
    %import common.NUMBER
    %import common.CNAME
    %import common.WS_INLINE
    %import common.WS
    %ignore WS_INLINE
    """
    parser = lark.Lark(grammar)
    return parser.parse(filter_text)


class FilterInstance(lark.Transformer):
    def __init__(self, instance: "GoogleComputeInstance"):
        super().__init__()
        self.instance = instance

    def start(self, tree: List[lark.Tree]):
        return all(tree)

    def compare_list(self, tree: List[lark.Tree]):
        raise NotImplementedError

    def compare(self, tree: List[lark.Tree]):
        key = tree[0].children[0]  # TODO dotted names
        operator_name = tree[1].data
        value = tree[2].children[0]
        operator_f = {
            # "pattern": None,
            "less_than": operator.lt,
            "less_than_equals": operator.le,
            "equals": operator.eq,
            "not_equals": operator.ne,
            "greater_than_equals": operator.ge,
            "greater_than": operator.gt,
            # "matches": None,
            # "not_matches": None,
        }[operator_name]
        return operator_f(self.instance[key], value)

    def is_defined(self, tree: List[lark.Tree]):
        raise NotImplementedError

    def not_defined(self, tree: List[lark.Tree]):
        raise NotImplementedError

    def logical_unary(self, tree: List[lark.Tree]):
        raise NotImplementedError

    def logical_binary(self, tree: List[lark.Tree]):
        # TODO Error on multiple operators if they don't match
        raise NotImplementedError


class GoogleComputeInstances:
    """
    A reimplementation of the Google cloud server-side for the ``instances`` resource
    """

    def __init__(self, state: GoogleState):
        self.state = state

    def list(self, project: str, zone: str, filter=None, alt="", body=None):
        if filter is not None:
            instances = list(self._filter_instances(self.state.instances, filter[0]))
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

    @staticmethod
    def _filter_instances(instances, filter=""):
        tree = parse_filter(filter)
        for i in instances:
            if FilterInstance(i).transform(tree):
                yield i

    def insert(self, project: str, zone: str, body, alt=""):
        print("inserting", body)
        return self.state.instances.append(GoogleComputeInstance(body))


class GoogleComputeInstance(collections.abc.Mapping):
    """
    A dictionary version of the Instance resource
    """

    def __init__(self, body):
        # Should match google_api_client("compute", "v1").instances()._schema.get("Instance")
        self.data = {}
        self.data["name"] = body["name"]
        self.data["tags"] = body.get("tags", {})
        self.data["status"] = "RUNNING"

    def __getitem__(self, key):
        return self.data[key]

    def __iter__(self):
        return iter(self.data)

    def __len__(self):
        return len(self.data)


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
