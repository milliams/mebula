import pytest  # type: ignore

from mebula.dict_filter import parse_filter, FilterInstance


def test_parse_filter_simple_match_tree():
    p = parse_filter("name=instance")

    term = p.children[0]
    assert term.data == "compare"

    key = term.children[0]
    assert key == "name"

    operator = term.children[1]
    assert operator == "="

    value = term.children[2]
    assert value.data == "value"
    assert value.children[0] == "instance"

    instance = {"name": "instance"}
    assert FilterInstance(instance).transform(p)

    nonstance = {"name": "nonstance"}
    assert not FilterInstance(nonstance).transform(p)


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
    instance = {"name": "instance"}
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
        "NOT network=default",
        "a=a AND b=b AND c=c",
        "NOT a=a AND b=b",
    ],
)
def test_parse_filter_logical(filter_text):
    print(filter_text)
    p = parse_filter(filter_text)
    instance = {"name": "instance"}
    FilterInstance(instance).transform(p)


@pytest.mark.parametrize(
    "filter_text",
    [
        "cpuPlatform = 'Intel Skylake' OR cpuPlatform = 'Intel Broadwell' AND scheduling.automaticRestart = true",
    ],
)
def test_parse_filter_logical_ambiguous(filter_text):
    p = parse_filter(filter_text)
    instance = {"name": "instance"}
    with pytest.raises(Exception):
        FilterInstance(instance).transform(p)


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