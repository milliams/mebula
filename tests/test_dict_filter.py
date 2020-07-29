# SPDX-FileCopyrightText: © 2020 Matt Williams <matt@milliams.com>
# SPDX-License-Identifier: MIT

import pytest  # type: ignore

from mebula.dict_filter import parse_filter, match_dict


def test_parse_filter_simple_match_tree():
    pattern = "name=instance"
    p = parse_filter(pattern)

    assert p.data == "compare"  # type: ignore

    key = p.children[0]  # type: ignore
    assert key == "name"

    operator = p.children[1]  # type: ignore
    assert operator == "="

    value = p.children[2]  # type: ignore
    assert value == "instance"

    instance = {"name": "instance"}
    assert match_dict(pattern, instance)

    nonstance = {"name": "nonstance"}
    assert not match_dict(pattern, nonstance)


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
    instance = {"name": "instance"}
    assert isinstance(match_dict(filter_text, instance), bool)


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
    instance = {"name": "instance"}
    assert isinstance(match_dict(filter_text, instance), bool)


@pytest.mark.parametrize(
    "filter_text",
    [
        "cpuPlatform = 'Intel Skylake' OR cpuPlatform = 'Intel Broadwell' AND scheduling.automaticRestart = true",
    ],
)
def test_parse_filter_logical_ambiguous(filter_text):
    instance = {"name": "instance"}
    with pytest.raises(SyntaxError):
        match_dict(filter_text, instance)


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


@pytest.mark.parametrize(
    "filter_text",
    [
        "zone:( europe-west1-d )",
        "zone:( europe-west1-d, other-zone )",
        "zone:( europe-west1-d other-zone )",
        "zone:( other-zone europe-west1-d )",
        "zone:( other-zone, europe-west1-d )",
    ],
)
def test_compare_list(filter_text):
    print(filter_text)
    instance = {"zone": "europe-west1-d"}
    assert match_dict(filter_text, instance)


@pytest.mark.parametrize(
    "filter_text, match",
    [
        ("name :*", True),
        ("- name :*", False),
        ("- zone:*", True),
        ("zone:*", False),
        ("l1:*", True),
        ("l1.l2:*", True),
    ],
)
def test_is_defined(filter_text, match):
    print(filter_text)
    instance = {"name": "instance", "l1": {"l2": "foo"}}
    assert match_dict(filter_text, instance) is match
