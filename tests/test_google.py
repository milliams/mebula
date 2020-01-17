import googleapiclient.discovery  # type: ignore
import googleapiclient.errors  # type: ignore
import pytest  # type: ignore

from mebula.google import (
    mock_google,
    extract_path_parameters,
    parse_filter,
    FilterInstance,
    GoogleComputeInstance,
)


def test_google_empty():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        assert compute.instances().list(project="foo", zone="bar").execute() == {}


def test_google_get_missing():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        with pytest.raises(googleapiclient.errors.HttpError) as e:
            compute.instances().get(project="p", zone="z", instance="none").execute()
        assert e.value.resp.status == "404"


def test_google_one_round_trip():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        compute.instances().insert(
            project="foo", zone="bar", body={"name": "foo", "tags": {}}
        ).execute()
        instances = compute.instances().list(project="foo", zone="bar").execute()
        assert "items" in instances
        assert len(instances["items"]) == 1
        assert instances["items"][0]["name"] == "foo"

        i = compute.instances().get(project="foo", zone="bar", instance="foo").execute()
        assert instances["items"][0] == i


def test_google_list_filter():
    with mock_google():
        compute = googleapiclient.discovery.build("compute", "v1")
        collection = compute.instances()
        collection.insert(project="p", zone="z", body={"name": "foo1"}).execute()
        collection.insert(project="p", zone="z", body={"name": "foo2"}).execute()
        instances = collection.list(project="p", zone="z", filter="name=foo2").execute()
        assert instances["items"][0]["name"] == "foo2"


def test_extract_path_parameters():
    path = "/compute/v1/projects/prfoo/zones/zbar/instances"
    template = "/compute/v1/projects/{project}/zones/{zone}/instances"

    expected = {"project": "prfoo", "zone": "zbar"}

    assert extract_path_parameters(path, template) == expected


def test_parse_filter_simple_match_tree():
    p = parse_filter("name=instance")

    term = p.children[0]
    assert term.data == "compare"

    key = term.children[0]
    assert key == "name"

    operator = term.children[1]
    assert operator.data == "equals"

    value = term.children[2]
    assert value.data == "value"
    assert value.children[0] == "instance"

    instance = GoogleComputeInstance("z", {"name": "instance"})
    assert FilterInstance(instance).transform(p)


@pytest.mark.parametrize(
    "filter_text",
    [
        "name:instance-1",
        "zone:( europe-west1-d )",
        "zone:( europe-west1-d, other-zone )",
        "zone:( europe-west1-d other-zone )",
        "name=wordpress-dev",
        "name:'Compute Engine default service account'",
        "name != example-instance",
        "tags.items~^production$",
        "name~^es",
        "scheduling.automaticRestart = false",
        "zone :*",
        "- zone:*",
    ],
)
def test_parse_filter_simple(filter_text):
    print(filter_text)
    p = parse_filter(filter_text)
    instance = GoogleComputeInstance("z", {"name": "instance"})
    FilterInstance(instance).transform(p)


@pytest.mark.parametrize(
    "filter_text",
    [
        "NOT name:instance-1",
        "labels.env=test AND labels.version=alpha",
        "tags.items~^production$ AND tags.items~^european$",
        "network:mynetwork AND name=mynetwork-deny-icmp",
        "NOT tags:* AND timestamp.datetime < '2018-10-01'",
        "(scheduling.automaticRestart = true) (cpuPlatform = 'Intel Skylake')",
        "cpuPlatform = 'Intel Skylake' OR (cpuPlatform = 'Intel Broadwell' AND scheduling.automaticRestart = true)",
        "(cpuPlatform = 'Intel Skylake' OR cpuPlatform = 'Intel Broadwell') AND scheduling.automaticRestart = true",
        "cpuPlatform = 'Intel Skylake' OR cpuPlatform = 'Intel Broadwell' AND scheduling.automaticRestart = true",
        "NOT network=default",
        "a=a AND b=b AND c=c",
        "NOT a=a AND b=b",
    ],
)
def test_parse_filter_logical(filter_text):
    parse_filter(filter_text)


@pytest.mark.parametrize(
    "filter_text",
    [
        # "createTime.date('%Y-%m-%d', Z)='2016-05-11'",
        "email ~ [0-9]*-compute@.*",
        "bindings.members:serviceAccount:terraform@foo.iam.gserviceaccount.com",
    ],
)
def test_parse_filter(filter_text):
    parse_filter(filter_text)
